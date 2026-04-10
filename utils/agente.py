"""
agente.py — Agente conversacional de cronograma.

Padrão: Evaluator-Optimizer (Anthropic).
  • Python faz os cálculos determinísticos (sem alucinação)
  • LLM interpreta intenção, propõe planos e explica decisões
  • Python valida → LLM refina (máx 3 iterações)

Fluxo geral:
  idle → router → classify intent
    criar_projeto  → entrevista guiada → planner → validator → proposta
    redistribuir   → detectar conflitos → planner → validator(3x) → proposta
    detectar/consultar → contexto → LLM → resposta direta

Estado da conversa (session_state["agente_estado"]):
  {"intencao": str|None, "dados_coletados": dict, "fase": str, "plano_proposto": dict|None}
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date, timedelta
from collections import defaultdict

import streamlit as st

from utils.ai import _call


# ─────────────────────────────────────────────────────────────────────────────
# 1. HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _parse_json_safe(raw: str) -> any:
    """Remove markdown fences e faz parse seguro do JSON."""
    raw = raw.strip()
    for fence in ("```json", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


def _venc_date(v) -> date:
    """Normaliza qualquer formato de vencimento para date."""
    if v is None:
        return date(2099, 12, 31)
    if isinstance(v, date):
        return v
    if hasattr(v, "date"):
        return v.date()
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v), fmt).date()
        except ValueError:
            continue
    return date(2099, 12, 31)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PYTHON TOOLS — determinísticas, sem LLM
# ─────────────────────────────────────────────────────────────────────────────

def buscar_historico_atividades(tipo_atividade: str) -> dict:
    """
    Busca horas médias de atividades do mesmo tipo no banco.
    Retorna {media, min, max, exemplos, total}.
    Defaults razoáveis quando não há histórico suficiente.
    """
    from utils.db import cursor, classificar_tipo_atividade

    _defaults = {
        "diagnostico": 30, "dados": 40, "predicoes": 80,
        "dashboard": 80, "implantacao": 15, "sustentacao": 10,
        "expansao": 40, "outros": 20,
    }
    try:
        with cursor() as cur:
            cur.execute(
                "SELECT nome, horas_estimadas FROM atividades WHERE horas_estimadas > 0"
            )
            rows = cur.fetchall()
    except Exception:
        m = _defaults.get(tipo_atividade, 40)
        return {"media": m, "min": m, "max": m, "exemplos": [], "total": 0}

    horas, exemplos = [], []
    for r in rows:
        if classificar_tipo_atividade(r["nome"]) == tipo_atividade:
            h = float(r["horas_estimadas"])
            horas.append(h)
            exemplos.append({"nome": r["nome"], "horas": h})

    if not horas:
        m = _defaults.get(tipo_atividade, 40)
        return {"media": m, "min": m, "max": m, "exemplos": [], "total": 0}

    return {
        "media": round(sum(horas) / len(horas), 0),
        "min":   min(horas),
        "max":   max(horas),
        "exemplos": exemplos[:5],
        "total": len(horas),
    }


def get_capacidade_disponivel(df, capacidade: dict, ferias: dict,
                               semana_ini: date, semana_fim: date) -> dict:
    """
    Retorna horas livres por pessoa no período.
    {pessoa: horas_livres_total_no_periodo}
    """
    import pandas as pd

    horas_usadas: dict[str, float] = defaultdict(float)
    if df is not None and not df.empty:
        mask = (
            (df["Semana"] >= pd.Timestamp(semana_ini)) &
            (df["Semana"] <= pd.Timestamp(semana_fim))
        )
        for _, row in df[mask].iterrows():
            horas_usadas[row["Responsável"]] += row["Horas"]

    semanas = []
    d = _monday(semana_ini)
    while d <= semana_fim:
        semanas.append(d)
        d += timedelta(weeks=1)
    n_semanas = max(len(semanas), 1)

    result = {}
    for pessoa, cap in capacidade.items():
        ferias_pessoa = [
            pd.Timestamp(s).date() if hasattr(s, "date") else s
            for s in ferias.get(pessoa, [])
        ]
        semanas_ferias = sum(1 for s in semanas if s in ferias_pessoa)
        semanas_uteis = max(n_semanas - semanas_ferias, 0)
        livre = max(0.0, cap * semanas_uteis - horas_usadas.get(pessoa, 0))
        result[pessoa] = round(livre, 1)

    return result


def get_conflitos_globais(df, capacidade: dict, ferias: dict,
                           projetos_meta: dict | None = None) -> list:
    """
    Detecta sobrecargas de capacidade e estouros de prazo.
    Retorna lista de dicts descritivos [{tipo, ...}].
    """
    import pandas as pd

    conflitos = []

    if df is not None and not df.empty:
        carga = (
            df.groupby(["Responsável", "Semana"])["Horas"]
            .sum()
            .reset_index()
        )
        for _, row in carga.iterrows():
            cap = capacidade.get(row["Responsável"], 36)
            if row["Horas"] > cap:
                conflitos.append({
                    "tipo":       "sobrecarga",
                    "pessoa":     row["Responsável"],
                    "semana":     row["Semana"].strftime("%d/%m/%Y"),
                    "horas":      round(float(row["Horas"]), 1),
                    "capacidade": cap,
                    "excesso":    round(float(row["Horas"]) - cap, 1),
                })

        if projetos_meta:
            for proj_nome, meta in projetos_meta.items():
                venc = _venc_date(meta.get("data_vencimento"))
                if venc.year >= 2099:
                    continue
                proj_df = df[df["Projeto"] == proj_nome]
                if proj_df.empty:
                    continue
                ultimo = proj_df["Semana"].max()
                if isinstance(ultimo, pd.Timestamp):
                    ultimo = ultimo.date()
                if ultimo > venc:
                    conflitos.append({
                        "tipo":            "estouro_prazo",
                        "projeto":         proj_nome,
                        "data_vencimento": venc.strftime("%d/%m/%Y"),
                        "ultima_atividade": ultimo.strftime("%d/%m/%Y") if hasattr(ultimo, "strftime") else str(ultimo),
                        "dias_atraso":     (ultimo - venc).days,
                    })

    return conflitos


def simular_schedule_paralelo(
    atividades: list,
    ancora: date,
    cap_por_pessoa: dict,
) -> dict:
    """
    Algoritmo EDF paralelo: projetos correm em paralelo, cada um consome
    a capacidade individual do seu responsável.
    atividades: [{nome, responsavel, tipo, horas, projeto, vencimento, ordem?}]
    Retorna: {idx: {semana_inicio, semana_fim, status, folga_dias}}
    """
    from utils.db import TIPO_ATIVIDADE_ORDEM, classificar_tipo_atividade

    ancora = _monday(ancora)

    # Agrupa por projeto, ordena por tipo → ordem original
    proj_filas: dict[str, list] = defaultdict(list)
    for i, atv in enumerate(atividades):
        t = classificar_tipo_atividade(atv.get("nome", ""))
        proj_filas[atv.get("projeto", "??")].append({
            **atv, "_idx": i,
            "_tipo_ord": TIPO_ATIVIDADE_ORDEM.get(t, 9),
        })

    for proj in proj_filas:
        proj_filas[proj].sort(key=lambda a: (a["_tipo_ord"], a.get("ordem", 999), a["_idx"]))

    def _proj_venc(p: str) -> date:
        return _venc_date(proj_filas[p][0].get("vencimento"))

    projetos_ord = sorted(proj_filas.keys(), key=_proj_venc)

    horas_rest = {
        atv["_idx"]: float(atv.get("horas", 0) or 0)
        for proj in proj_filas
        for atv in proj_filas[proj]
    }
    proj_ptr  = {p: 0 for p in projetos_ord}
    proj_done = {p: False for p in projetos_ord}
    ini_map: dict[int, date] = {}
    fim_map: dict[int, date] = {}

    semana = ancora
    for _ in range(500):
        # Coleta atividade ativa de cada projeto (1 por projeto por vez)
        ativos_por_resp: dict[str, list] = defaultdict(list)
        for p in projetos_ord:
            if proj_done[p]:
                continue
            idx = proj_ptr[p]
            if idx < len(proj_filas[p]):
                atv = proj_filas[p][idx]
                ativos_por_resp[atv.get("responsavel", "?")].append(atv)

        if not ativos_por_resp:
            break

        # Capacidade dividida por responsável entre projetos simultâneos
        for resp, resp_atvs in ativos_por_resp.items():
            cap = float(cap_por_pessoa.get(resp, 36))
            h_por_atv = cap / len(resp_atvs)
            for atv in resp_atvs:
                idx = atv["_idx"]
                if idx not in ini_map:
                    ini_map[idx] = semana
                horas_rest[idx] -= h_por_atv
                if horas_rest[idx] <= 0.5:
                    fim_map[idx] = semana
                    p = atv.get("projeto", "??")
                    proj_ptr[p] += 1
                    if proj_ptr[p] >= len(proj_filas[p]):
                        proj_done[p] = True

        semana += timedelta(weeks=1)

    resultado = {}
    for proj in proj_filas:
        for atv in proj_filas[proj]:
            idx = atv["_idx"]
            si = ini_map.get(idx, ancora)
            sf = fim_map.get(idx, semana)
            venc = _proj_venc(atv.get("projeto", "??"))
            diff = (venc - sf).days
            resultado[idx] = {
                "semana_inicio": si,
                "semana_fim":    sf,
                "status":        "ok" if diff >= 0 else "estouro",
                "folga_dias":    diff,
            }
    return resultado


def simular_mudancas(changes: list, df, capacidade: dict, ferias: dict) -> dict:
    """
    Dry-run de mudanças (novo responsável / novas datas) em atividades existentes.
    Returns: {ok: bool, violacoes: list[str]}
    """
    import pandas as pd

    violacoes: list[str] = []

    for c in changes:
        novo_resp = c.get("responsavel_novo") or c.get("novo_responsavel")
        semana_ini = c.get("semana_inicio_nova")
        semana_fim = c.get("semana_fim_nova")
        nom = c.get("atv_nome", str(c.get("atv_id", "?")))

        if novo_resp:
            if novo_resp not in capacidade:
                violacoes.append(f"Responsável '{novo_resp}' não cadastrado no sistema.")
                continue
            ferias_resp = [
                pd.Timestamp(s).date() if hasattr(s, "date") else s
                for s in ferias.get(novo_resp, [])
            ]
            if semana_ini and semana_fim and ferias_resp:
                d = _monday(semana_ini) if isinstance(semana_ini, date) else semana_ini
                while d <= semana_fim:
                    if d in ferias_resp:
                        violacoes.append(
                            f"{novo_resp} está de férias na semana "
                            f"{d.strftime('%d/%m/%Y')} (atividade: '{nom}')"
                        )
                    d += timedelta(weeks=1)

    return {"ok": len(violacoes) == 0, "violacoes": violacoes}


def aplicar_mudancas(changes: list) -> int:
    """
    Aplica lista de changes em atividades existentes.
    Campos aceitos: atv_id, responsavel_novo/novo_responsavel,
                    semana_inicio_nova, semana_fim_nova, ordem_nova.
    """
    from utils.db import cursor, _clear_cache

    count = 0
    with cursor() as cur:
        for c in changes:
            atv_id = c.get("atv_id")
            if not atv_id:
                continue
            sets, params = [], []
            r_novo = c.get("responsavel_novo") or c.get("novo_responsavel")
            if r_novo:
                sets.append("responsavel=%s");   params.append(r_novo)
            if c.get("semana_inicio_nova"):
                sets.append("semana_inicio=%s"); params.append(c["semana_inicio_nova"])
            if c.get("semana_fim_nova"):
                sets.append("semana_fim=%s");    params.append(c["semana_fim_nova"])
            if c.get("ordem_nova") is not None:
                sets.append("ordem=%s");          params.append(c["ordem_nova"])
            if sets:
                params.append(atv_id)
                cur.execute(
                    f"UPDATE atividades SET {', '.join(sets)} WHERE id=%s", params
                )
                count += 1
    _clear_cache()
    return count


def criar_projeto_com_atividades(
    projeto: dict,
    atividades: list,
    ancora: date,
    cap_por_pessoa: dict,
) -> int:
    """
    Cria projeto + atividades no banco.
    Se a atividade já tiver semana_inicio/semana_fim (vindas do plano),
    usa essas datas diretamente. Só roda o scheduler para as que não têm.
    Returns: projeto_id criado.
    """
    from utils.db import cursor, _clear_cache

    ancora = ancora or date.today()

    # Separa atividades que já têm datas calculadas das que precisam do scheduler
    sem_data = []
    for i, atv in enumerate(atividades):
        si = atv.get("semana_inicio")
        sf = atv.get("semana_fim")
        if si is None or sf is None:
            sem_data.append((i, {
                **atv,
                "projeto":    projeto.get("nome", ""),
                "vencimento": projeto.get("data_vencimento"),
                "ordem":      i,
            }))

    # Roda scheduler só para as que faltam datas
    schedule_extra: dict = {}
    if sem_data:
        schedule_extra = simular_schedule_paralelo(
            [s[1] for s in sem_data], ancora, cap_por_pessoa
        )
        # Remapeia índices do scheduler de volta para posições originais
        schedule_extra = {sem_data[k][0]: v for k, v in schedule_extra.items()}

    venc = projeto.get("data_vencimento")
    if isinstance(venc, str) and venc:
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                venc = datetime.strptime(venc, fmt).date()
                break
            except ValueError:
                pass

    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO projetos
              (nome, status, unidade, departamento, subarea, tipo_projeto, data_vencimento)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                projeto["nome"],
                projeto.get("status", "Ativo"),
                projeto.get("unidade", ""),
                projeto.get("departamento", ""),
                projeto.get("subarea", ""),
                projeto.get("tipo_projeto", ""),
                venc,
            ),
        )
        proj_id = cur.fetchone()["id"]

        for i, atv in enumerate(atividades):
            # Prioriza datas já presentes no plano; cai no scheduler como fallback
            si = atv.get("semana_inicio") or schedule_extra.get(i, {}).get("semana_inicio")
            sf = atv.get("semana_fim")    or schedule_extra.get(i, {}).get("semana_fim")
            # Normaliza para date puro (pode vir como datetime)
            if si is not None and hasattr(si, "date"):
                si = si.date()
            if sf is not None and hasattr(sf, "date"):
                sf = sf.date()
            cur.execute(
                """
                INSERT INTO atividades
                  (projeto_id, nome, responsavel, horas_estimadas,
                   semana_inicio, semana_fim, ordem)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    proj_id,
                    atv["nome"],
                    atv.get("responsavel", ""),
                    atv.get("horas_estimadas", 40),
                    si,
                    sf,
                    i + 1,
                ),
            )

    _clear_cache()
    return proj_id


# ─────────────────────────────────────────────────────────────────────────────
# 3. LLM CHAIN
# ─────────────────────────────────────────────────────────────────────────────

_INTENCOES = [
    "criar_projeto",
    "redistribuir",
    "reagendar",
    "detectar_conflitos",
    "consultar",
]

_SYS_ROUTER = """Classifique a intenção do usuário em UMA categoria:
- criar_projeto: quer criar um novo projeto ou demanda
- redistribuir: quer mudar o responsável de atividades
- reagendar: quer mudar datas de atividades
- detectar_conflitos: quer ver sobrecargas, atrasos ou conflitos
- consultar: pergunta sobre o estado do cronograma

Retorne APENAS a categoria, sem texto adicional."""

_SYS_EXTRATOR = """Extraia informações de mensagens sobre projetos e retorne JSON.
Campos possíveis:
- nome_projeto: string
- data_vencimento: string YYYY-MM-DD (converta "setembro" → "2026-09-30", "dezembro" → "2026-12-31", etc.)
- unidade: string (hospital/unidade, ex: CMC, HMVSC, HOEB, CMA)
- departamento: string
- tipo_projeto: string
- atividades: lista [{nome, tipo, responsavel, horas_estimadas}]
  onde tipo ∈ {diagnostico, dados, predicoes, dashboard, implantacao, sustentacao, expansao, outros}

Omita campos não mencionados. Retorne APENAS o JSON."""

_SYS_PLANNER_REDISTRIB = """Você é um planejador de cronogramas.
Analise as sobrecargas e sugira redistribuição de responsáveis.

Regras:
1. Atribua apenas para pessoas com horas livres no período
2. Não atribua durante períodos de férias
3. Prefira quem já está no mesmo projeto
4. Retorne SOMENTE um JSON array de mudanças:

[{
  "atv_id": 123,
  "atv_nome": "Nome",
  "projeto": "Proj X",
  "responsavel_atual": "João",
  "responsavel_novo": "Maria",
  "motivo": "João tem 15h de excesso. Maria tem 10h livres."
}]

Se nenhuma redistribuição for viável, retorne []."""

_SYS_PLANNER_CRIAR = """Você é um planejador de projetos.
Com base nas informações coletadas, complete o plano de criação de projeto.

Use os históricos de horas fornecidos como referência para horas_estimadas.
Se o usuário já informou horas, use os valores dele.

Retorne SOMENTE este JSON:
{
  "projeto": {"nome":"...","data_vencimento":"YYYY-MM-DD","unidade":"...","status":"Ativo"},
  "atividades": [{"nome":"...","tipo":"...","responsavel":"...","horas_estimadas": 40}]
}"""

_SYS_REFINER = """Você corrige planos de cronograma para eliminar violações de férias e capacidade.
Retorne APENAS o JSON corrigido no mesmo formato original."""

_SYS_FORMATTER = """Você é um assistente de gestão de projetos do Einstein.
Explique o plano proposto em PT-BR de forma clara e amigável.
- Use emojis relevantes
- Mostre atividades, responsáveis, datas estimadas e folga de prazo
- Se houver riscos, mencione-os brevemente
- Pergunte se o usuário quer aplicar ou ajustar
- Seja conciso (máx 180 palavras)"""

_SYS_CHAT = """Você é um assistente de gestão de cronogramas de projetos do Einstein.
Responda em PT-BR de forma direta. Use os dados de contexto fornecidos.
Se o usuário quiser executar uma ação (criar projeto, redistribuir), sugira que ele use o campo de chat descrevendo o que precisa."""


def _router(pedido: str, historico: list) -> str:
    hist_txt = "\n".join(f"{m['role']}: {m['content']}" for m in historico[-4:])
    txt = f"Histórico:\n{hist_txt}\n\nNova mensagem: {pedido}" if hist_txt else pedido
    resp = _call([
        {"role": "system", "content": _SYS_ROUTER},
        {"role": "user",   "content": txt},
    ]).strip().lower()
    for intencao in _INTENCOES:
        if intencao in resp:
            return intencao
    return "consultar"


def _extrair_dados(mensagem: str, existentes: dict) -> dict:
    """Extrai campos da mensagem e merge com dados existentes."""
    try:
        raw = _call([
            {"role": "system", "content": _SYS_EXTRATOR},
            {"role": "user",   "content": mensagem},
        ])
        novos = _parse_json_safe(raw)

        merged = dict(existentes)
        for k, v in novos.items():
            if k == "atividades" and isinstance(v, list):
                mapa = {a.get("nome", ""): a for a in merged.get("atividades", [])}
                for nova in v:
                    nome = nova.get("nome", "")
                    mapa[nome] = {**mapa.get(nome, {}), **{x: y for x, y in nova.items() if y}}
                merged["atividades"] = list(mapa.values())
            elif v not in (None, "", [], {}):
                merged[k] = v
        return merged
    except Exception:
        return existentes


def _campos_faltantes(dados: dict) -> list[str]:
    """Lista de campos obrigatórios ainda ausentes para criar projeto."""
    f = []
    if not dados.get("nome_projeto"):
        f.append("nome_projeto")
    if not dados.get("data_vencimento"):
        f.append("data_vencimento")
    atividades = dados.get("atividades", [])
    if not atividades:
        f.append("atividades")
    else:
        for atv in atividades:
            if not atv.get("responsavel"):
                f.append(f"responsavel::{atv.get('nome', atv.get('tipo', '?'))}")
    return f


_PERGUNTAS = {
    "nome_projeto":    "📁 Qual será o **nome** deste projeto?",
    "data_vencimento": "📅 Qual é o **prazo de entrega** do projeto? (ex: 30/09/2026 ou setembro)",
    "atividades":      "📋 Quais **atividades** o projeto terá? (ex: diagnóstico, estruturação de dados, dashboard, predições, implantação)",
}


def _proxima_pergunta(faltando: list) -> str:
    for campo in faltando:
        if campo in _PERGUNTAS:
            return _PERGUNTAS[campo]
        if campo.startswith("responsavel::"):
            nome_atv = campo.split("::", 1)[1]
            return f"👤 Quem será o **responsável** pela atividade **'{nome_atv}'**?"
    return "❓ Pode dar mais detalhes?"


def _planejar_redistribuicao(conflitos: list, contexto: dict) -> list:
    """LLM propõe redistribuição dado conflitos."""
    cap_disp = get_capacidade_disponivel(
        contexto.get("df"),
        contexto.get("capacidade", {}),
        contexto.get("ferias", {}),
        date.today(),
        date.today() + timedelta(weeks=16),
    )
    sobrecargas = [c for c in conflitos if c["tipo"] == "sobrecarga"]
    sobrecarregados = {c["pessoa"] for c in sobrecargas}
    atividades_afetadas = [
        a for a in contexto.get("atividades_list", [])
        if a.get("responsavel") in sobrecarregados
    ]
    ctx_txt = (
        f"Sobrecargas:\n{json.dumps(sobrecargas, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"Capacidade disponível (16 semanas):\n{json.dumps(cap_disp, ensure_ascii=False)}\n\n"
        f"Atividades dos sobrecarregados:\n"
        f"{json.dumps(atividades_afetadas, ensure_ascii=False, indent=2, default=str)}"
    )
    try:
        raw = _call([
            {"role": "system", "content": _SYS_PLANNER_REDISTRIB},
            {"role": "user",   "content": ctx_txt},
        ])
        result = _parse_json_safe(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _planejar_criacao(dados: dict, cap_por_pessoa: dict, historicos: dict) -> dict:
    """LLM propõe plano completo de criação."""
    payload = {
        **dados,
        "historicos_por_tipo":       historicos,
        "responsaveis_disponiveis":  list(cap_por_pessoa.keys()),
        "data_hoje":                 date.today().strftime("%Y-%m-%d"),
    }
    try:
        raw = _call([
            {"role": "system", "content": _SYS_PLANNER_CRIAR},
            {"role": "user",   "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ])
        return _parse_json_safe(raw)
    except Exception:
        return {}


def _refinar(plano: dict, violacoes: list, contexto: dict) -> dict:
    """LLM refina o plano eliminando violações."""
    ferias_str = {
        k: [str(s) for s in v]
        for k, v in contexto.get("ferias", {}).items()
    }
    prompt = (
        f"Violações detectadas:\n{json.dumps(violacoes, ensure_ascii=False)}\n\n"
        f"Plano original:\n{json.dumps(plano, ensure_ascii=False, default=str)}\n\n"
        f"Férias:\n{json.dumps(ferias_str, ensure_ascii=False)}\n\n"
        "Corrija o plano. Retorne APENAS o JSON corrigido."
    )
    try:
        raw = _call([
            {"role": "system", "content": _SYS_REFINER},
            {"role": "user",   "content": prompt},
        ])
        return _parse_json_safe(raw)
    except Exception:
        return plano


def _formatar(resumo: str, plano: dict | None, violacoes: list) -> str:
    """LLM converte tudo em resposta PT-BR humanizada."""
    prompt = (
        f"{resumo}\n\n"
        f"Plano:\n{json.dumps(plano, ensure_ascii=False, default=str) if plano else 'Nenhum.'}\n\n"
        f"Violações restantes: {json.dumps(violacoes, ensure_ascii=False) if violacoes else 'Nenhuma.'}"
    )
    return _call([
        {"role": "system", "content": _SYS_FORMATTER},
        {"role": "user",   "content": prompt},
    ])


# ─────────────────────────────────────────────────────────────────────────────
# 4. PONTO DE ENTRADA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def estado_inicial() -> dict:
    return {
        "intencao":        None,
        "dados_coletados": {},
        "fase":            "idle",
        "plano_proposto":  None,
    }


def processar_mensagem(
    pedido: str,
    historico: list,
    estado: dict,
    contexto: dict,
) -> dict:
    """
    Ponto de entrada principal.

    contexto deve conter:
      df, capacidade, ferias, responsaveis, projetos_meta, atividades_list

    Retorna:
      {resposta_texto, plano, estado (atualizado), violacoes}
    """
    # Cópia superficial para não mutar o original
    estado = dict(estado)
    estado["dados_coletados"] = dict(estado.get("dados_coletados") or {})
    cap = contexto.get("capacidade", {})

    # ── Fase: proposta aguardando ação do usuário ─────────────────────────────
    if estado.get("fase") == "proposta":
        pedido_lower = pedido.lower()
        if any(w in pedido_lower for w in ["cancel", "não", "nao", "descartar", "voltar", "abort"]):
            estado = estado_inicial()
            return {
                "resposta_texto": "Plano descartado. Como posso ajudar?",
                "plano": None, "estado": estado, "violacoes": [],
            }
        # Qualquer outra mensagem → re-exibe a proposta
        return {
            "resposta_texto": (
                "O plano acima ainda está aguardando confirmação. "
                "Clique em **✅ Aplicar** para gravar ou **✗ Descartar** para cancelar."
            ),
            "plano": estado.get("plano_proposto"),
            "estado": estado,
            "violacoes": [],
        }

    # ── Detecta intenção se idle ──────────────────────────────────────────────
    if not estado.get("intencao") or estado.get("fase") == "idle":
        intencao = _router(pedido, historico)
        estado["intencao"] = intencao
        estado["dados_coletados"] = {}
        estado["fase"] = "coletando" if intencao == "criar_projeto" else "processando"
    else:
        intencao = estado["intencao"]

    # ── Consulta / Detecção de conflitos ─────────────────────────────────────
    if intencao in ("consultar", "detectar_conflitos"):
        conflitos = get_conflitos_globais(
            contexto.get("df"), cap, contexto.get("ferias", {}),
            contexto.get("projetos_meta"),
        )
        n_sob  = sum(1 for c in conflitos if c["tipo"] == "sobrecarga")
        n_praz = sum(1 for c in conflitos if c["tipo"] == "estouro_prazo")
        ctx_txt = (
            f"Conflitos ({len(conflitos)} total — {n_sob} sobrecargas, {n_praz} estouros de prazo):\n"
            f"{json.dumps(conflitos[:30], ensure_ascii=False, indent=2, default=str)}\n\n"
            f"Capacidade/semana: {json.dumps(cap, ensure_ascii=False)}\n\n"
            f"Pergunta: {pedido}"
        )
        resposta = _call([
            {"role": "system", "content": _SYS_CHAT},
            {"role": "user",   "content": ctx_txt},
        ])
        estado = estado_inicial()
        return {"resposta_texto": resposta, "plano": None, "estado": estado, "violacoes": []}

    # ── Redistribuição / Reagendamento ────────────────────────────────────────
    if intencao in ("redistribuir", "reagendar"):
        conflitos = get_conflitos_globais(
            contexto.get("df"), cap, contexto.get("ferias", {}),
            contexto.get("projetos_meta"),
        )
        if not conflitos:
            estado = estado_inicial()
            return {
                "resposta_texto": (
                    "✅ Não detectei sobrecargas ou conflitos no cronograma. "
                    "Tudo parece bem calibrado!"
                ),
                "plano": None, "estado": estado, "violacoes": [],
            }

        changes = _planejar_redistribuicao(conflitos, contexto)

        # Evaluator-Optimizer: valida → refina (máx 3×)
        violacoes: list[str] = []
        for _ in range(3):
            if not changes:
                break
            val = simular_mudancas(changes, contexto.get("df"), cap, contexto.get("ferias", {}))
            violacoes = val["violacoes"]
            if val["ok"]:
                break
            changes = _refinar(
                {"changes": changes}, violacoes, contexto
            ).get("changes", changes)

        if not changes:
            estado = estado_inicial()
            return {
                "resposta_texto": (
                    "⚠️ Não consegui montar uma redistribuição viável respeitando "
                    "férias e capacidades. Tente redistribuir manualmente na aba Cadastro."
                ),
                "plano": None, "estado": estado, "violacoes": violacoes,
            }

        plano_final = {"tipo": "mudancas", "changes": changes}
        estado["fase"] = "proposta"
        estado["plano_proposto"] = plano_final

        n_conf = len([c for c in conflitos if c["tipo"] == "sobrecarga"])
        texto = _formatar(
            f"Plano de redistribuição: {len(changes)} mudança(s) para resolver {n_conf} sobrecarga(s).",
            plano_final, violacoes,
        )
        return {"resposta_texto": texto, "plano": plano_final, "estado": estado, "violacoes": violacoes}

    # ── Criar Projeto (entrevista guiada) ─────────────────────────────────────
    if intencao == "criar_projeto":
        # Injeta contexto: o extrator LLM não sabe que "Teste" = nome do projeto
        # a menos que digamos explicitamente qual campo está sendo respondido
        campo_ativo = estado.get("campo_ativo")
        msg_extrator = pedido
        if campo_ativo:
            if campo_ativo == "nome_projeto":
                msg_extrator = f"Nome do projeto: {pedido}"
            elif campo_ativo == "data_vencimento":
                msg_extrator = f"Prazo de entrega do projeto: {pedido}"
            elif campo_ativo == "atividades":
                msg_extrator = f"Atividades do projeto: {pedido}"
            elif campo_ativo.startswith("responsavel::"):
                nome_atv = campo_ativo.split("::", 1)[1]
                msg_extrator = f"O responsável pela atividade '{nome_atv}' é: {pedido}"
        dados = _extrair_dados(msg_extrator, estado.get("dados_coletados", {}))
        estado["dados_coletados"] = dados

        faltando = _campos_faltantes(dados)
        if faltando:
            pergunta = _proxima_pergunta(faltando)
            estado["fase"] = "coletando"
            estado["campo_ativo"] = faltando[0]  # memoriza o próximo campo esperado
            return {
                "resposta_texto": pergunta,
                "plano": None, "estado": estado, "violacoes": [],
            }
        estado.pop("campo_ativo", None)  # todos coletados — limpa o guia

        # Todos os dados coletados → busca históricos + chama planner
        historicos = {}
        for atv in dados.get("atividades", []):
            t = atv.get("tipo", "outros")
            if t not in historicos:
                historicos[t] = buscar_historico_atividades(t)
            # Usa média histórica se usuário não informou horas
            if not atv.get("horas_estimadas"):
                atv["horas_estimadas"] = historicos[t]["media"]

        plano = _planejar_criacao(dados, cap, historicos)

        # Valida schedule via simulação
        violacoes = []
        if plano.get("atividades"):
            ancora = date.today()
            sims = [
                {
                    "nome":        atv["nome"],
                    "responsavel": atv.get("responsavel", ""),
                    "horas":       atv.get("horas_estimadas", 40),
                    "projeto":     plano.get("projeto", {}).get("nome", ""),
                    "vencimento":  plano.get("projeto", {}).get("data_vencimento"),
                    "ordem":       i,
                }
                for i, atv in enumerate(plano["atividades"])
            ]
            schedule = simular_schedule_paralelo(sims, ancora, cap)

            import pandas as pd
            for i, atv in enumerate(plano["atividades"]):
                sched = schedule.get(i, {})
                si = sched.get("semana_inicio")
                sf = sched.get("semana_fim")
                resp = atv.get("responsavel", "")
                ferias_resp = [
                    pd.Timestamp(s).date() if hasattr(s, "date") else s
                    for s in contexto.get("ferias", {}).get(resp, [])
                ]
                if si and sf and ferias_resp:
                    d = si
                    while d <= sf:
                        if d in ferias_resp:
                            violacoes.append(
                                f"{resp} está de férias em {d.strftime('%d/%m/%Y')} "
                                f"(atividade: '{atv['nome']}')"
                            )
                        d += timedelta(weeks=1)
                if sched.get("status") == "estouro":
                    violacoes.append(
                        f"Atividade '{atv['nome']}' termina em "
                        f"{sf.strftime('%d/%m/%Y') if sf else '?'} "
                        f"— {abs(sched.get('folga_dias', 0))}d além do prazo"
                    )
                # Injeta datas no plano
                atv["semana_inicio"]  = si
                atv["semana_fim"]     = sf
                atv["folga_dias"]     = sched.get("folga_dias")
                atv["status_prazo"]   = sched.get("status")

        plano_final = {"tipo": "criar_projeto", **plano}
        estado["fase"] = "proposta"
        estado["plano_proposto"] = plano_final

        nome_proj = dados.get("nome_projeto", "projeto")
        n_atvs = len(dados.get("atividades", []))
        texto = _formatar(
            f"Projeto '{nome_proj}' com {n_atvs} atividade(s). Datas calculadas pelo scheduler paralelo.",
            plano_final, violacoes,
        )
        return {
            "resposta_texto": texto,
            "plano": plano_final, "estado": estado, "violacoes": violacoes,
        }

    # Fallback
    estado = estado_inicial()
    return {
        "resposta_texto": (
            "Não entendi bem. Tente:\n"
            "- **Criar projeto**: use o botão ➕ ou escreva 'Quero criar um novo projeto'\n"
            "- **Sobrecargas**: 'Detectar conflitos'\n"
            "- **Redistribuir**: 'Quem pode assumir atividades do Daniel?'"
        ),
        "plano": None, "estado": estado, "violacoes": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. ENTRADA POR FORMULÁRIO (bypassa entrevista LLM)
# ─────────────────────────────────────────────────────────────────────────────

def criar_projeto_do_formulario(dados_form: dict, historico: list, estado: dict, contexto: dict) -> dict:
    """
    Recebe dados diretamente do formulário UI (sem entrevista LLM).
    dados_form: {nome_projeto, data_vencimento, unidade, departamento,
                 atividades: [{nome, tipo, responsavel, horas_estimadas}]}
    """
    cap = contexto.get("capacidade", {})

    # Preenche horas_estimadas ausentes via histórico do banco (sem LLM)
    for atv in dados_form.get("atividades", []):
        if not atv.get("horas_estimadas"):
            hist = buscar_historico_atividades(atv.get("tipo", "outros"))
            atv["horas_estimadas"] = hist["media"]

    # Monta o plano diretamente dos dados do formulário — sem chamar o LLM
    atividades = [dict(a) for a in dados_form.get("atividades", [])]
    plano = {
        "projeto": {
            "nome":            dados_form.get("nome_projeto", ""),
            "data_vencimento": dados_form.get("data_vencimento", ""),
            "unidade":         dados_form.get("unidade", ""),
            "departamento":    dados_form.get("departamento", ""),
            "status":          "Ativo",
        },
        "atividades": atividades,
    }
    if not plano["projeto"]["nome"] or not plano["atividades"]:
        return {
            "resposta_texto": "❌ Não consegui gerar o plano. Verifique os campos preenchidos.",
            "plano": None, "estado": estado_inicial(), "violacoes": [],
        }

    # Injeta datas via scheduler paralelo
    import pandas as pd
    violacoes: list[str] = []
    ancora = date.today()
    sims = [
        {
            "nome":       atv["nome"],
            "responsavel": atv.get("responsavel", ""),
            "horas":      atv.get("horas_estimadas", 40),
            "projeto":    plano["projeto"].get("nome", ""),
            "vencimento": plano["projeto"].get("data_vencimento"),
            "tipo":       atv.get("tipo", "outros"),
            "ordem":      i,
        }
        for i, atv in enumerate(plano["atividades"])
    ]
    schedule = simular_schedule_paralelo(sims, ancora, cap)
    for i, atv in enumerate(plano["atividades"]):
        sched = schedule.get(i, {})
        si, sf = sched.get("semana_inicio"), sched.get("semana_fim")
        resp = atv.get("responsavel", "")
        ferias_resp = [
            pd.Timestamp(s).date() if hasattr(s, "date") else s
            for s in contexto.get("ferias", {}).get(resp, [])
        ]
        if si and sf and ferias_resp:
            d = si
            while d <= sf:
                if d in ferias_resp:
                    violacoes.append(f"{resp} está de férias em {d.strftime('%d/%m/%Y')} ('{atv['nome']}')")
                d += timedelta(weeks=1)
        if sched.get("status") == "estouro":
            violacoes.append(
                f"'{atv['nome']}' termina em {sf.strftime('%d/%m/%Y') if sf else '?'} "
                f"— {abs(sched.get('folga_dias', 0))}d além do prazo"
            )
        atv["semana_inicio"] = si
        atv["semana_fim"]    = sf
        atv["folga_dias"]    = sched.get("folga_dias")
        atv["status_prazo"]  = sched.get("status")

    plano_final = {"tipo": "criar_projeto", **plano}
    novo_estado = estado_inicial()
    novo_estado["fase"] = "proposta"
    novo_estado["plano_proposto"] = plano_final

    nome_proj = plano["projeto"].get("nome", "?")
    n_atvs    = len(plano["atividades"])
    aviso_viol = f"\n\n⚠️ **Atenção:** {len(violacoes)} violação(ões) detectada(s)." if violacoes else ""
    try:
        texto = _formatar(
            f"Projeto '{nome_proj}' com {n_atvs} atividade(s). "
            f"Datas calculadas pelo scheduler paralelo.",
            plano_final, violacoes,
        )
    except Exception:
        texto = (
            f"✅ Plano para **{nome_proj}** gerado com {n_atvs} atividade(s)."
            f"{aviso_viol}\n\nClique em **✅ Aplicar** para gravar ou **✗ Descartar** para cancelar."
        )
    return {"resposta_texto": texto, "plano": plano_final, "estado": novo_estado, "violacoes": violacoes}
