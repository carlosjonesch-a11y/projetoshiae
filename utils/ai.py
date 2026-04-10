"""
ai.py — Integração com Groq e Gemini para gestão inteligente de demandas.
Provedor padrão: Groq (llama-3.3-70b-versatile). Alternativa: Gemini 2.0 Flash.
Defina AI_PROVIDER = "groq" ou "gemini" em .streamlit/secrets.toml.
"""

import json
import streamlit as st
import pandas as pd


# ── Configuração ──────────────────────────────────────────────────────────────

# Fila de fallback: tenta cada entrada em ordem até uma funcionar.
# Modelos verificados em 10/04/2026 — apenas produção/preview ativos no Groq.
# Formato: (provedor, modelo)
_FALLBACK_CHAIN = [
    ("groq",   "llama-3.3-70b-versatile"),    # produção — principal (testado ✅)
    ("groq",   "openai/gpt-oss-120b"),          # produção — fallback robusto (testado ✅)
    ("groq",   "llama-3.1-8b-instant"),         # produção — fallback leve (testado ✅)
    ("gemini", "models/gemini-2.5-flash"),      # produção — Gemini principal (testado ✅)
    ("gemini", "models/gemini-flash-latest"),   # produção — alias estável (testado ✅)
]

# Compat: mantido para código externo que lê essas constantes
_GROQ_MODEL   = "llama-3.3-70b-versatile"
_GEMINI_MODEL = "models/gemini-2.5-flash"


def _provider() -> str:
    """Retorna o provedor preferido: 'groq' ou 'gemini'."""
    prov = str(st.secrets.get("AI_PROVIDER", "groq")).lower().strip()
    return "gemini" if prov == "gemini" else "groq"


def is_configured() -> bool:
    """Verifica se pelo menos uma chave de IA está configurada."""
    has_groq   = bool(st.secrets.get("GROQ_API_KEY",   None))
    has_gemini = bool(st.secrets.get("GEMINI_API_KEY", None))
    return has_groq or has_gemini


def _call_groq(messages: list, model: str) -> str:
    api_key = st.secrets.get("GROQ_API_KEY", None)
    if not api_key:
        raise ValueError("GROQ_API_KEY não configurada")
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("Instale: pip install groq")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=4000,
    )
    return response.choices[0].message.content


def _call_gemini(messages: list, model: str) -> str:
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada")
    try:
        from google import genai as genai_sdk
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError("Instale: pip install google-genai")
    client = genai_sdk.Client(api_key=api_key)
    # Converte messages para o formato do SDK
    contents = []
    for m in messages:
        role = "user" if m["role"] in ("user", "system") else "model"
        contents.append(genai_types.Content(
            role=role,
            parts=[genai_types.Part(text=m["content"])],
        ))
    resp = client.models.generate_content(model=model, contents=contents)
    return resp.text


def _call(messages: list) -> str:
    """
    Chama modelos em sequência de fallback até um responder sem erro.
    Ordem preferencial: Groq llama-3.3 → llama-3.1 → mixtral → Gemini 2.0 → Gemini 1.5.
    Se o provedor preferido for 'gemini', coloca Gemini primeiro na fila.
    """
    prov_pref = _provider()
    chain = sorted(
        _FALLBACK_CHAIN,
        key=lambda x: (0 if x[0] == prov_pref else 1),
    )

    last_err = None
    for prov, model in chain:
        try:
            if prov == "gemini":
                return _call_gemini(messages, model)
            else:
                return _call_groq(messages, model)
        except Exception as e:
            err_str = str(e)
            # Só tenta próximo em rate-limit, modelo não encontrado ou sem chave
            if any(k in err_str for k in ("rate_limit", "429", "not found",
                                           "does not exist", "não configurada",
                                           "not configured", "404")):
                last_err = f"[{prov}/{model}] {err_str[:120]}"
                continue
            # Outros erros (auth, etc.) — levanta imediatamente
            raise
    raise RuntimeError(
        f"Todos os modelos falharam. Último erro: {last_err}"
    )


def _parse_json(raw: str) -> list:
    """Remove markdown code fences e faz parse do JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Contexto ──────────────────────────────────────────────────────────────────

def build_context(
    df: pd.DataFrame,
    capacidade: dict,
    ferias: dict,
    atividades_list: list,
) -> dict:
    """
    Constrói dicionário de contexto com toda a agenda para enviar à IA.
    Inclui: carga semanal, sobrecargas, capacidade livre, férias e atividades.
    """
    carga_list = []
    sobrecargas = []

    if df is not None and not df.empty:
        carga = (
            df.groupby(["Responsável", "Semana"])["Horas"]
            .sum()
            .reset_index()
        )
        carga["Semana"] = carga["Semana"].dt.strftime("%d/%m/%Y")
        carga_list = carga.rename(
            columns={"Responsável": "pessoa", "Semana": "semana", "Horas": "horas"}
        ).to_dict("records")

        for row in carga_list:
            cap = capacidade.get(row["pessoa"], 36)
            if row["horas"] > cap:
                sobrecargas.append({
                    "pessoa":      row["pessoa"],
                    "semana":      row["semana"],
                    "horas":       round(row["horas"], 1),
                    "capacidade":  cap,
                    "excesso":     round(row["horas"] - cap, 1),
                })

    ferias_fmt = {
        pessoa: [pd.Timestamp(s).strftime("%d/%m/%Y") for s in sems]
        for pessoa, sems in ferias.items()
    }

    ativs_fmt = []
    for a in atividades_list:
        ini = a.get("semana_inicio")
        fim = a.get("semana_fim")
        ativs_fmt.append({
            "id":          a["id"],
            "projeto":     a.get("projeto_nome", ""),
            "atividade":   a["nome"],
            "responsavel": a.get("responsavel", ""),
            "horas":       float(a.get("horas_estimadas") or 0),
            "inicio":      ini.strftime("%d/%m/%Y") if hasattr(ini, "strftime") else str(ini or ""),
            "fim":         fim.strftime("%d/%m/%Y") if hasattr(fim, "strftime") else str(fim or ""),
            "ordem":       int(a.get("ordem") or 0),
        })

    return {
        "capacidade_semanal": capacidade,
        "ferias":             ferias_fmt,
        "carga_atual":        carga_list,
        "sobrecargas":        sobrecargas,
        "atividades":         ativs_fmt,
    }


# ── Redistribuição Inteligente ────────────────────────────────────────────────

_SYSTEM_REDISTRIB = """Você é um assistente especializado em gestão de cronogramas de projetos.

Analise a carga de trabalho da equipe e sugira redistribuições de atividades para eliminar sobrecargas.

Regras:
1. Só sugira redistribuir para pessoas com capacidade livre na semana afetada
2. Respeite as férias — não atribua atividades durante períodos de férias
3. Prefira pessoas que já estão no mesmo projeto
4. Uma atividade só pode ser sugerida uma vez
5. Retorne SOMENTE um JSON array, sem texto adicional

Formato:
[
  {
    "tipo": "reatribuir",
    "atv_id": 123,
    "atv_nome": "Nome da atividade",
    "projeto": "Nome do projeto",
    "responsavel_atual": "João",
    "novo_responsavel": "Maria",
    "motivo": "João está 12h acima da capacidade. Maria tem 8h livres na semana 14/04."
  }
]

Se nenhuma redistribuição for possível, retorne [].
"""


def sugerir_redistribuicao(context: dict) -> list:
    """
    Analisa sobrecargas e sugere redistribuição de atividades entre responsáveis.
    Retorna lista de dicts com mudanças sugeridas.
    """
    if not context.get("sobrecargas"):
        return []

    user_msg = f"""Contexto atual da equipe:

Capacidade semanal por pessoa: {json.dumps(context['capacidade_semanal'], ensure_ascii=False)}

Sobrecargas detectadas: {json.dumps(context['sobrecargas'], ensure_ascii=False, default=str)}

Carga atual por pessoa/semana: {json.dumps(context['carga_atual'], ensure_ascii=False, default=str)}

Férias: {json.dumps(context['ferias'], ensure_ascii=False, default=str)}

Atividades: {json.dumps(context['atividades'], ensure_ascii=False, default=str)}

Sugira as redistribuições necessárias para eliminar as sobrecargas detectadas."""

    raw = _call([
        {"role": "system", "content": _SYSTEM_REDISTRIB},
        {"role": "user",   "content": user_msg},
    ])
    return _parse_json(raw)


# ── Encadeamento Inteligente ──────────────────────────────────────────────────

_SYSTEM_ENCADEIA = """Você é um assistente de planejamento de projetos.

Reorganize as datas das atividades para que:
1. Cada atividade comece imediatamente após o término da anterior (sem semanas vazias entre elas)
2. Respeite as férias dos responsáveis (não programe atividades nas semanas de férias da pessoa)
3. Mantenha a ordem do campo 'ordem' de cada atividade
4. A primeira atividade (menor 'ordem') mantém sua data de início original
5. Mantenha a duração de cada atividade (fim - inicio em dias)
6. Retorne SOMENTE um JSON array, sem texto adicional

Formato:
[
  {
    "tipo": "reagendar",
    "atv_id": 123,
    "atv_nome": "Nome",
    "projeto": "Projeto X",
    "responsavel_atual": "João",
    "novo_responsavel": null,
    "data_inicio_atual": "06/01/2025",
    "data_inicio_nova": "06/01/2025",
    "data_fim_atual": "20/01/2025",
    "data_fim_nova": "20/01/2025",
    "motivo": "Encadeada após atividade anterior"
  }
]
"""


def sugerir_encadeamento(context: dict, atividades_projeto: list) -> list:
    """
    Sugere sequência e datas de atividades de um projeto, minimizando gaps
    e respeitando férias dos responsáveis.
    Retorna lista de dicts com mudanças de data.
    """
    atividades_projeto_sorted = sorted(
        atividades_projeto,
        key=lambda x: (x.get("ordem") or 0, x.get("inicio", "")),
    )

    user_msg = f"""Contexto:
Férias: {json.dumps(context['ferias'], ensure_ascii=False, default=str)}
Capacidade: {json.dumps(context['capacidade_semanal'], ensure_ascii=False, default=str)}

Atividades do projeto (ordenadas por 'ordem'):
{json.dumps(atividades_projeto_sorted, ensure_ascii=False, indent=2, default=str)}

Gere as novas datas para encadear as atividades sem gaps.
A data de início da primeira atividade deve ser mantida."""

    raw = _call([
        {"role": "system", "content": _SYSTEM_ENCADEIA},
        {"role": "user",   "content": user_msg},
    ])
    return _parse_json(raw)


# ── Chat Livre ────────────────────────────────────────────────────────────────

_SYSTEM_CHAT = """Você é um assistente de gestão de projetos integrado ao dashboard de cronograma.

Você tem acesso ao estado atual da equipe: atividades, carga semanal, férias, capacidade e sobrecargas.

Regras:
- Responda sempre em português (pt-BR)
- Seja direto e objetivo
- Quando sugerir ações (redistribuir, reagendar, encadear), liste-as claramente
- Não execute ações diretamente — apenas analise e sugira
- Indique ao usuário qual ferramenta do sistema usar para aplicar as sugestões
"""


def chat_livre(context: dict, messages_history: list, user_message: str) -> str:
    """
    Chat livre com contexto completo da agenda.
    messages_history: lista de {"role": "user"|"assistant", "content": "..."}
    Retorna a resposta da IA como string.
    """
    context_summary = f"""Estado atual do sistema:
- Pessoas com sobrecarga: {len(context.get('sobrecargas', []))} ocorrência(s)
- Total de atividades: {len(context.get('atividades', []))}
- Sobrecargas: {json.dumps(context.get('sobrecargas', []), ensure_ascii=False, default=str)}
- Capacidade semanal: {json.dumps(context.get('capacidade_semanal', {}), ensure_ascii=False)}
- Férias: {json.dumps(context.get('ferias', {}), ensure_ascii=False, default=str)}
- Atividades (primeiras 60): {json.dumps(context.get('atividades', [])[:60], ensure_ascii=False, default=str)}"""

    messages = [
        {"role": "system",    "content": _SYSTEM_CHAT},
        {"role": "user",      "content": context_summary},
        {"role": "assistant", "content": "Entendido. Estou pronto para analisar o cronograma e responder suas dúvidas."},
    ]
    messages.extend(messages_history)
    messages.append({"role": "user", "content": user_message})

    return _call(messages)
