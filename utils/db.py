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


def _clear_cache():
    """Limpa cache de leitura após qualquer escrita."""
    st.cache_data.clear()


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


# ── Projetos ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def listar_projetos():
    with cursor() as cur:
        cur.execute("SELECT * FROM projetos ORDER BY nome")
        return [dict(r) for r in cur.fetchall()]


def inserir_projeto(nome, descricao, status, unidade="", departamento="", subarea="", tipo_projeto=""):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO projetos (nome, descricao, status, unidade, departamento, subarea, tipo_projeto)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (nome.strip(), descricao.strip(), status,
             unidade.strip(), departamento.strip(), subarea.strip(), tipo_projeto.strip()),
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


def atualizar_projeto(pid, nome, descricao, status, unidade="", departamento="", subarea="", tipo_projeto=""):
    with cursor() as cur:
        cur.execute(
            """UPDATE projetos SET nome=%s, descricao=%s, status=%s,
               unidade=%s, departamento=%s, subarea=%s, tipo_projeto=%s
               WHERE id=%s""",
            (nome.strip(), descricao.strip(), status,
             unidade.strip(), departamento.strip(), subarea.strip(), tipo_projeto.strip(), pid),
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
        d = r["semana_inicio"]
        fim = r["semana_fim"]
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

