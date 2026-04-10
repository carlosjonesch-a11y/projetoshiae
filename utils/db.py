"""
db.py — Conexão e operações CRUD com banco Neon (PostgreSQL serverless)
"""

import streamlit as st
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import timedelta


def _get_url():
    try:
        return st.secrets["NEON_DATABASE_URL"]
    except (KeyError, FileNotFoundError, TypeError):
        return None


def is_configured():
    return bool(_get_url())


def get_connection():
    url = _get_url()
    if not url:
        raise ValueError(
            "Configure NEON_DATABASE_URL em .streamlit/secrets.toml\n"
            'Exemplo: NEON_DATABASE_URL = "postgresql://user:pass@host/db?sslmode=require"'
        )
    return psycopg2.connect(url, connect_timeout=10)


@contextmanager
def cursor():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _to_monday(d):
    """Normaliza uma date/Timestamp para a segunda-feira da sua semana ISO."""
    from datetime import date as _date, datetime as _datetime
    if isinstance(d, _datetime):
        d = d.date()
    if isinstance(d, _date):
        return d - timedelta(days=d.weekday())
    # fallback: string ou outro tipo — tenta via strptime
    from datetime import date as _date2
    import re as _re
    if isinstance(d, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed = _datetime.strptime(d, fmt).date()
                return parsed - timedelta(days=parsed.weekday())
            except ValueError:
                continue
    raise TypeError(f"_to_monday: tipo não suportado {type(d)}")


def _clear_cache():
    """Limpa cache de leitura após qualquer escrita e sinaliza recarga."""
    st.cache_data.clear()
    # Sinaliza ao app.py para recarregar df no próximo rerun
    try:
        st.session_state["_needs_reload"] = True
    except Exception:
        pass  # fora do contexto Streamlit (ex: testes)


def init_tables():
    """Cria as tabelas se não existirem."""
    with cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projetos (
                id            SERIAL PRIMARY KEY,
                nome          VARCHAR(200) NOT NULL,
                descricao     TEXT         DEFAULT '',
                status        VARCHAR(50)  DEFAULT 'Ativo',
                unidade       VARCHAR(100) DEFAULT '',
                departamento  VARCHAR(100) DEFAULT '',
                subarea       VARCHAR(100) DEFAULT '',
                tipo_projeto  VARCHAR(100) DEFAULT '',
                criado_em     TIMESTAMPTZ  DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS responsaveis (
                id                 SERIAL PRIMARY KEY,
                nome               VARCHAR(100) NOT NULL UNIQUE,
                email              VARCHAR(150) DEFAULT '',
                capacidade_semanal INTEGER      DEFAULT 36
            );
            CREATE TABLE IF NOT EXISTS atividades (
                id               SERIAL PRIMARY KEY,
                projeto_id       INTEGER       REFERENCES projetos(id) ON DELETE CASCADE,
                nome             VARCHAR(300)  NOT NULL,
                responsavel      VARCHAR(100)  DEFAULT '',
                horas_estimadas  NUMERIC(7,1)  DEFAULT 0,
                semana_inicio    DATE,
                semana_fim       DATE,
                ordem            INTEGER       DEFAULT 0,
                criado_em        TIMESTAMPTZ   DEFAULT NOW()
            );
        """)
        # Garante colunas em bancos já existentes
        cur.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='atividades' AND column_name='ordem'
                ) THEN
                    ALTER TABLE atividades ADD COLUMN ordem INTEGER DEFAULT 0;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='projetos' AND column_name='unidade'
                ) THEN
                    ALTER TABLE projetos ADD COLUMN unidade VARCHAR(100) DEFAULT '';
                    ALTER TABLE projetos ADD COLUMN departamento VARCHAR(100) DEFAULT '';
                    ALTER TABLE projetos ADD COLUMN subarea VARCHAR(100) DEFAULT '';
                    ALTER TABLE projetos ADD COLUMN tipo_projeto VARCHAR(100) DEFAULT '';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='projetos' AND column_name='data_vencimento'
                ) THEN
                    ALTER TABLE projetos ADD COLUMN data_vencimento DATE;
                END IF;
            END $$;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ferias (
                id           SERIAL PRIMARY KEY,
                responsavel  TEXT NOT NULL,
                data_inicio  DATE NOT NULL,
                data_fim     DATE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS enc_undo_log (
                id               SERIAL PRIMARY KEY,
                criado_em        TIMESTAMPTZ DEFAULT NOW(),
                atv_id           INTEGER NOT NULL,
                semana_ini_antes DATE,
                semana_fim_antes DATE,
                nome             TEXT
            );
        """)


# ── Projetos ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def listar_projetos():
    with cursor() as cur:
        cur.execute("SELECT * FROM projetos ORDER BY nome")
        return [dict(r) for r in cur.fetchall()]


def inserir_projeto(nome, descricao, status, unidade="", departamento="", subarea="", tipo_projeto="", data_vencimento=None):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO projetos (nome, descricao, status, unidade, departamento, subarea, tipo_projeto, data_vencimento)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (nome.strip(), descricao.strip(), status,
             unidade.strip(), departamento.strip(), subarea.strip(), tipo_projeto.strip(), data_vencimento),
        )
        new_id = cur.fetchone()["id"]
    _clear_cache()
    return new_id


def deletar_projeto(pid):
    with cursor() as cur:
        cur.execute("DELETE FROM projetos WHERE id=%s", (pid,))
    _clear_cache()


# ── Responsáveis ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def listar_responsaveis():
    with cursor() as cur:
        cur.execute("SELECT * FROM responsaveis ORDER BY nome")
        return [dict(r) for r in cur.fetchall()]


def inserir_responsavel(nome, email, capacidade):
    with cursor() as cur:
        cur.execute(
            "INSERT INTO responsaveis (nome, email, capacidade_semanal) VALUES (%s,%s,%s) RETURNING id",
            (nome.strip(), email.strip(), int(capacidade)),
        )
        new_id = cur.fetchone()["id"]
    _clear_cache()
    return new_id


def deletar_responsavel(rid):
    with cursor() as cur:
        cur.execute("DELETE FROM responsaveis WHERE id=%s", (rid,))
    _clear_cache()


# ── Atividades ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def listar_atividades(projeto_id=None):
    with cursor() as cur:
        if projeto_id:
            cur.execute("""
                SELECT a.id, a.nome, a.responsavel, a.horas_estimadas,
                       a.semana_inicio, a.semana_fim, a.ordem, p.nome AS projeto_nome
                FROM atividades a
                JOIN projetos p ON p.id = a.projeto_id
                WHERE a.projeto_id = %s
                ORDER BY a.ordem, a.semana_inicio
            """, (projeto_id,))
        else:
            cur.execute("""
                SELECT a.id, a.nome, a.responsavel, a.horas_estimadas,
                       a.semana_inicio, a.semana_fim, a.ordem, p.nome AS projeto_nome
                FROM atividades a
                JOIN projetos p ON p.id = a.projeto_id
                ORDER BY p.nome, a.ordem, a.semana_inicio
            """)
        return [dict(r) for r in cur.fetchall()]


def inserir_atividade(projeto_id, nome, responsavel, horas, semana_inicio, semana_fim, ordem=0):
    semana_inicio = _to_monday(semana_inicio)
    semana_fim    = _to_monday(semana_fim)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO atividades
               (projeto_id, nome, responsavel, horas_estimadas, semana_inicio, semana_fim, ordem)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (int(projeto_id), nome.strip(), responsavel, float(horas), semana_inicio, semana_fim, int(ordem)),
        )
        new_id = cur.fetchone()["id"]
    _clear_cache()
    return new_id


def deletar_atividade(aid):
    with cursor() as cur:
        cur.execute("DELETE FROM atividades WHERE id=%s", (aid,))
    _clear_cache()


@st.cache_data(ttl=60)
def listar_atividades_por_pessoa_semana(responsavel: str, semana_date):
    """Retorna atividades de um responsável que estão ativas numa semana específica."""
    with cursor() as cur:
        cur.execute("""
            SELECT a.id, a.nome, a.responsavel, a.horas_estimadas,
                   a.semana_inicio, a.semana_fim, a.ordem, p.nome AS projeto_nome
            FROM atividades a
            JOIN projetos p ON p.id = a.projeto_id
            WHERE a.responsavel = %s
              AND a.semana_inicio <= %s
              AND a.semana_fim >= %s
            ORDER BY a.semana_inicio, p.nome
        """, (responsavel, semana_date, semana_date))
        return [dict(r) for r in cur.fetchall()]


# ── Atualizar ─────────────────────────────────────────────────────────────────

# ── Atualiza nome em atualizar_projeto (cascata) ────────────────────────


def atualizar_projeto(pid, nome, descricao, status, unidade="", departamento="", subarea="", tipo_projeto="", data_vencimento=None):
    with cursor() as cur:
        cur.execute(
            """UPDATE projetos SET nome=%s, descricao=%s, status=%s,
               unidade=%s, departamento=%s, subarea=%s, tipo_projeto=%s, data_vencimento=%s
               WHERE id=%s""",
            (nome.strip(), descricao.strip(), status,
             unidade.strip(), departamento.strip(), subarea.strip(), tipo_projeto.strip(), data_vencimento, pid),
        )
    _clear_cache()


def atualizar_responsavel(rid, nome, email, capacidade):
    nome = nome.strip()
    with cursor() as cur:
        # Busca nome atual para propagar em cascata
        cur.execute("SELECT nome FROM responsaveis WHERE id=%s", (rid,))
        row = cur.fetchone()
        nome_antigo = row["nome"] if row else None

        cur.execute(
            "UPDATE responsaveis SET nome=%s, email=%s, capacidade_semanal=%s WHERE id=%s",
            (nome, email.strip(), int(capacidade), rid),
        )

        # Propaga nome novo para atividades e férias
        if nome_antigo and nome_antigo != nome:
            cur.execute(
                "UPDATE atividades SET responsavel=%s WHERE responsavel=%s",
                (nome, nome_antigo),
            )
            cur.execute(
                "UPDATE ferias SET responsavel=%s WHERE responsavel=%s",
                (nome, nome_antigo),
            )
    _clear_cache()


def atualizar_atividade(aid, nome, responsavel, horas, semana_inicio, semana_fim, ordem):
    semana_inicio = _to_monday(semana_inicio)
    semana_fim    = _to_monday(semana_fim)
    with cursor() as cur:
        cur.execute(
            """UPDATE atividades
               SET nome=%s, responsavel=%s, horas_estimadas=%s,
                   semana_inicio=%s, semana_fim=%s, ordem=%s
               WHERE id=%s""",
            (nome.strip(), responsavel, float(horas), semana_inicio, semana_fim, int(ordem), aid),
        )
    _clear_cache()


def reordenar_atividades_por_data():
    """
    Para cada projeto, reclassifica o campo 'ordem' das atividades
    em ordem crescente de semana_inicio (1, 2, 3…).
    Atividades sem data ficam com ordem 0.
    """
    with cursor() as cur:
        cur.execute("""
            SELECT id, projeto_id, semana_inicio
            FROM atividades
            ORDER BY projeto_id, semana_inicio NULLS FIRST, id
        """)
        rows = cur.fetchall()

    # Agrupa por projeto e calcula nova ordem
    from collections import defaultdict
    por_projeto = defaultdict(list)
    for r in rows:
        por_projeto[r["projeto_id"]].append(r)

    updates = []
    for proj_id, ativs in por_projeto.items():
        ordem = 1
        for atv in ativs:
            if atv["semana_inicio"] is None:
                updates.append((0, atv["id"]))
            else:
                updates.append((ordem, atv["id"]))
                ordem += 1

    with cursor() as cur:
        for nova_ordem, aid in updates:
            cur.execute("UPDATE atividades SET ordem=%s WHERE id=%s", (nova_ordem, aid))

    _clear_cache()
    return len(updates)


# ── Fonte única de verdade: carregar de atividades ──────────────────────────

def carregar_cronograma_do_banco():
    """
    Constrói o DataFrame diretamente da tabela atividades (fonte única de verdade).
    Expande cada atividade em linhas semanais distribuindo as horas uniformemente.
    Colunas: Projeto, Atividade, Responsável, Semana, Horas
    """
    import pandas as pd

    with cursor() as cur:
        cur.execute("""
            SELECT p.nome AS projeto,
                   a.nome AS atividade,
                   a.responsavel,
                   a.horas_estimadas,
                   a.semana_inicio,
                   a.semana_fim
            FROM atividades a
            JOIN projetos p ON p.id = a.projeto_id
            WHERE a.semana_inicio IS NOT NULL
              AND a.semana_fim IS NOT NULL
              AND a.horas_estimadas > 0
            ORDER BY p.nome, a.semana_inicio
        """)
        rows = cur.fetchall()

    if not rows:
        return None, {}, [], [], []

    records = []
    for r in rows:
        d   = _to_monday(r["semana_inicio"])
        fim = _to_monday(r["semana_fim"])
        semanas_atv = []
        while d <= fim:
            semanas_atv.append(d)
            d += timedelta(weeks=1)
        if not semanas_atv:
            continue
        h_per_week = round(float(r["horas_estimadas"]) / len(semanas_atv), 1)
        for sem in semanas_atv:
            records.append({
                "Projeto":     r["projeto"],
                "Atividade":   r["atividade"],
                "Responsável": r["responsavel"],
                "Semana":      pd.Timestamp(sem),
                "Horas":       h_per_week,
            })

    if not records:
        return None, {}, [], [], []

    df = pd.DataFrame(records)
    df["Semana"] = pd.to_datetime(df["Semana"])
    df["Horas"] = df["Horas"].astype(float)
    df = df.sort_values(["Projeto", "Semana", "Responsável"]).reset_index(drop=True)

    semanas  = sorted(df["Semana"].unique().tolist())
    pessoas  = sorted(df["Responsável"].unique().tolist())
    projetos = sorted(df["Projeto"].unique().tolist())

    return df, {}, semanas, pessoas, projetos



# ── Classificador de tipo de atividade ───────────────────────────────────────

# Ordem lógica: Diagnóstico → Dados → Predições → Dashboard → Implantação → Sustentação → Expansão
TIPO_ATIVIDADE_ORDEM = {
    "diagnostico":    1,
    "dados":          2,
    "predicoes":      3,
    "dashboard":      4,
    "implantacao":    5,
    "sustentacao":    6,
    "expansao":       7,
    "outros":         9,
}

TIPO_ATIVIDADE_LABEL = {
    "diagnostico": "📋 Diagnóstico/Entendimento",
    "dados":       "🗄️ Dados/Estruturação",
    "predicoes":   "🔮 Predições/ML",
    "dashboard":   "📊 Dashboard",
    "implantacao": "🚀 Implantação",
    "sustentacao": "🔧 Sustentação/CCO",
    "expansao":    "🌐 Expansão/Célula",
    "outros":      "📌 Outros",
}


def classificar_tipo_atividade(nome: str) -> str:
    """Classifica uma atividade pelo nome, retornando chave do TIPO_ATIVIDADE_ORDEM."""
    import unicodedata

    def norm(s):
        return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()

    n = norm(nome)

    # 4. Dashboard tem prioridade quando o nome começa com essa palavra
    # (ex: "Dashboard - PS + Diagnóstico" é um dashboard, não um diagnóstico)
    if n.startswith("dashboard") or n.startswith("construcao do dash") or n.startswith("criacao do dash"):
        return "dashboard"

    # Implantação explícita no início do nome tem prioridade (ex: "Implantação do modelo preditivo")
    if n.startswith("implanta") or n.startswith("deploy") or n.startswith("go-live"):
        return "implantacao"

    # 1. Diagnóstico / Entendimento (primeira etapa sempre)
    if any(w in n for w in [
        "diagnost", "entendimento", "levantamento", "mapeamento",
        "discovery", "kick-off", "kickoff", "kick off", "estudo de viabilidade",
        "estudos ", "estudo e mapeam",
    ]):
        return "diagnostico"

    # 2. Dados / Estruturação (base de dados antes de qualquer visualização)
    if any(w in n for w in [
        "estrutur", "tabela", "etl", "pipeline", "ingest", "modelagem",
        "extracao", "extracao", "dwh", "data lake", "fonte de dado",
        "carga de dado", "coleta", "validar de dado", "validacao de dado",
        "construcao das tabelas", "tabela de demanda", "modelo de dado",
    ]):
        return "dados"

    # 3. Predições / ML
    if any(w in n for w in [
        "predicao", "predicoes", "predi", "machine learn",
        "ml ", " ia ", "algoritmo", "forecast", "previsao",
        "construcao das predi", "modelo preditivo", "modelo ml",
        "treinamento do modelo", "treinar modelo",
    ]):
        return "predicoes"

    # 4. Dashboard / Visualização (restante dos casos)
    if any(w in n for w in [
        "dashboard", "painel", "relatorio", "visualizacao", "report",
    ]):
        return "dashboard"

    # 7. Expansão / Célula — verificar ANTES de sustentação (CCO pode aparecer nos dois)
    if any(w in n for w in [
        "celula", "abrangencia", "replicacao", "expansao",
        "construcao da celula",
    ]):
        return "expansao"

    # 5. Implantação / Deploy
    if any(w in n for w in [
        "implantacao", "implantar", "deploy", "go-live", "golive",
        "piloto",
    ]):
        return "implantacao"

    # 6. Sustentação / CCO / Acompanhamento
    if any(w in n for w in [
        "sustentacao", "suporte", "manutencao", "cco", "acompanhamento",
        "coach", "reuniao",
    ]):
        return "sustentacao"

    return "outros"




# ── Férias ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def listar_ferias():
    """Retorna lista de períodos de férias: [{id, responsavel, data_inicio, data_fim}]."""
    with cursor() as cur:
        cur.execute("""
            SELECT id, responsavel, data_inicio, data_fim
            FROM ferias
            ORDER BY responsavel, data_inicio
        """)
        return [dict(r) for r in cur.fetchall()]


def inserir_ferias(responsavel: str, data_inicio, data_fim):
    """Cria um novo período de férias para um responsável."""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO ferias (responsavel, data_inicio, data_fim) VALUES (%s,%s,%s) RETURNING id",
            (responsavel.strip(), data_inicio, data_fim),
        )
        new_id = cur.fetchone()["id"]
    _clear_cache()
    return new_id


def deletar_ferias(fid: int):
    """Remove um período de férias pelo id."""
    with cursor() as cur:
        cur.execute("DELETE FROM ferias WHERE id=%s", (fid,))
    _clear_cache()


def carregar_ferias_como_dict():
    """
    Converte os registros da tabela ferias no formato
    {responsavel: [pd.Timestamp, ...]} com uma entrada por semana (seg a seg, 7 dias).
    """
    import pandas as pd

    registros = listar_ferias()
    ferias: dict = {}
    for r in registros:
        resp = r["responsavel"]
        ini  = pd.Timestamp(r["data_inicio"])
        fim  = pd.Timestamp(r["data_fim"])
        # Gera timestamps das semanas cobertas pelo intervalo
        sem = ini
        while sem <= fim:
            ferias.setdefault(resp, [])
            if sem not in ferias[resp]:
                ferias[resp].append(sem)
            sem += pd.Timedelta(weeks=1)
    # Ordena listas
    for resp in ferias:
        ferias[resp] = sorted(set(ferias[resp]))
    return ferias


def checar_conflitos_ferias(ferias_dict: dict, atividades_list: list) -> list:
    """
    Verifica quais atividades conflitam com férias do seu responsável.

    Returns list of dicts:
        {atividade, responsavel, projeto, semanas_conflito (list[str 'dd/mm'])}
    """
    import pandas as pd

    conflitos = []
    for atv in atividades_list:
        resp = atv.get("responsavel", "")
        ini  = atv.get("semana_inicio")
        fim  = atv.get("semana_fim")
        if not resp or not ini or not fim:
            continue
        ferias_resp = ferias_dict.get(resp, [])
        if not ferias_resp:
            continue
        # Expande semanas da atividade
        sem = pd.Timestamp(ini)
        fim_ts = pd.Timestamp(fim)
        conflitantes = []
        while sem <= fim_ts:
            if sem in ferias_resp:
                conflitantes.append(sem.strftime("%d/%m"))
            sem += pd.Timedelta(weeks=1)
        if conflitantes:
            conflitos.append({
                "atividade":       atv.get("nome", ""),
                "responsavel":     resp,
                "projeto":         atv.get("projeto_nome", ""),
                "semanas_conflito": conflitantes,
            })
    return conflitos


def checar_conflito_atividade(ferias_dict: dict, responsavel: str, semana_inicio, semana_fim) -> list:
    """
    Verifica conflito de uma única atividade (para usar nos formulários).
    Retorna lista de strings 'dd/mm' das semanas em conflito.
    """
    import pandas as pd

    ferias_resp = ferias_dict.get(responsavel, [])
    if not ferias_resp or not semana_inicio or not semana_fim:
        return []
    sem = pd.Timestamp(semana_inicio)
    fim_ts = pd.Timestamp(semana_fim)
    conflitantes = []
    while sem <= fim_ts:
        if sem in ferias_resp:
            conflitantes.append(sem.strftime("%d/%m"))
        sem += pd.Timedelta(weeks=1)
    return conflitantes


# ── Reconciliação de nomes ────────────────────────────────────────────────────

def listar_nomes_orfaos():
    """
    Retorna nomes usados em atividades ou férias que NÃO existem em responsaveis.nome.
    Indica origem: 'atividades' e/ou 'ferias'.
    Retorna list[dict]: [{nome, origens: list}]
    """
    with cursor() as cur:
        cur.execute("SELECT DISTINCT nome FROM responsaveis")
        nomes_validos = {r["nome"] for r in cur.fetchall()}

        cur.execute("SELECT DISTINCT responsavel FROM atividades WHERE responsavel IS NOT NULL AND responsavel <> ''")
        nomes_atv = {r["responsavel"] for r in cur.fetchall()}

        cur.execute("SELECT DISTINCT responsavel FROM ferias WHERE responsavel IS NOT NULL AND responsavel <> ''")
        nomes_fer = {r["responsavel"] for r in cur.fetchall()}

    orfaos = {}
    for nome in nomes_atv - nomes_validos:
        orfaos.setdefault(nome, []).append("atividades")
    for nome in nomes_fer - nomes_validos:
        orfaos.setdefault(nome, []).append("férias")

    return [{"nome": k, "origens": v} for k, v in sorted(orfaos.items())]


def substituir_nome_responsavel(nome_antigo: str, nome_novo: str):
    """
    Substitui nome_antigo por nome_novo em atividades e ferias.
    Usado para reconciliar nomes órfãos (renomeados sem cascata).
    """
    with cursor() as cur:
        cur.execute(
            "UPDATE atividades SET responsavel=%s WHERE responsavel=%s",
            (nome_novo, nome_antigo),
        )
        cur.execute(
            "UPDATE ferias SET responsavel=%s WHERE responsavel=%s",
            (nome_novo, nome_antigo),
        )
    _clear_cache()


def reatribuir_por_projeto(nome_antigo: str, nome_novo: str, projeto_ids: list) -> int:
    """
    Move atividades de nome_antigo → nome_novo apenas nos projetos indicados.
    Retorna quantidade de atividades atualizadas.
    """
    if not projeto_ids:
        return 0
    with cursor() as cur:
        cur.execute(
            f"""UPDATE atividades SET responsavel=%s
                WHERE responsavel=%s AND projeto_id = ANY(%s::int[])""",
            (nome_novo, nome_antigo, projeto_ids),
        )
        count = cur.rowcount
    _clear_cache()
    return count

