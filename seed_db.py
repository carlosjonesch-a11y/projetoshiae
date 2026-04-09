"""
seed_db.py — Cria tabelas no Neon e insere dados da planilha
Executar: python seed_db.py
"""

import psycopg2
import psycopg2.extras
from utils.parser import parse_cronograma

URL = (
    "postgresql://neondb_owner:npg_8RXiutOM3pyc@"
    "ep-lucky-lake-an79n9hp-pooler.c-6.us-east-1.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS projetos (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(200) NOT NULL UNIQUE,
    descricao   TEXT         DEFAULT '',
    status      VARCHAR(50)  DEFAULT 'Ativo',
    criado_em   TIMESTAMPTZ  DEFAULT NOW()
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
    criado_em        TIMESTAMPTZ   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cronograma_semanal (
    id           SERIAL PRIMARY KEY,
    projeto      VARCHAR(200),
    atividade    VARCHAR(300),
    responsavel  VARCHAR(100),
    semana       DATE,
    horas        NUMERIC(7,1),
    UNIQUE(projeto, atividade, responsavel, semana)
);
"""


def main():
    # 1. Ler planilha
    print("Lendo planilha...")
    data = open("Cronograma.xlsx", "rb").read()
    df, ferias, semanas, pessoas, projetos = parse_cronograma(data)
    print(f"  {len(df)} registros | {len(projetos)} projetos | {len(pessoas)} pessoas")

    # 2. Conectar
    print("Conectando ao Neon...")
    conn = psycopg2.connect(URL, connect_timeout=15)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    print("  Conectado!")

    # 3. Criar tabelas
    print("Criando tabelas...")
    cur.execute(CREATE_TABLES)
    conn.commit()
    print("  Tabelas criadas.")

    # 4. Inserir responsáveis
    for pessoa in pessoas:
        cur.execute(
            "INSERT INTO responsaveis (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
            (pessoa,),
        )
    conn.commit()
    print(f"  {len(pessoas)} responsáveis inseridos.")

    # 5. Inserir projetos
    for proj in projetos:
        cur.execute(
            "INSERT INTO projetos (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
            (proj,),
        )
    conn.commit()
    print(f"  {len(projetos)} projetos inseridos.")

    # 6. Inserir cronograma_semanal
    insert_count = 0
    for _, row in df.iterrows():
        cur.execute(
            """INSERT INTO cronograma_semanal (projeto, atividade, responsavel, semana, horas)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (projeto, atividade, responsavel, semana)
               DO UPDATE SET horas = EXCLUDED.horas""",
            (
                row["Projeto"],
                row["Atividade"],
                row["Responsável"],
                row["Semana"].date(),
                float(row["Horas"]),
            ),
        )
        insert_count += 1
    conn.commit()
    print(f"  {insert_count} registros de cronograma_semanal inseridos.")

    # 7. Inserir atividades resumidas (inicio/fim por atividade)
    agg = (
        df.groupby(["Projeto", "Atividade", "Responsável"])
        .agg(inicio=("Semana", "min"), fim=("Semana", "max"), horas=("Horas", "sum"))
        .reset_index()
    )
    cur.execute("SELECT id, nome FROM projetos")
    proj_map = {r["nome"]: r["id"] for r in cur.fetchall()}

    atv_count = 0
    for _, row in agg.iterrows():
        proj_id = proj_map.get(row["Projeto"])
        if proj_id:
            cur.execute(
                """INSERT INTO atividades
                   (projeto_id, nome, responsavel, horas_estimadas, semana_inicio, semana_fim)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    proj_id,
                    row["Atividade"],
                    row["Responsável"],
                    float(row["horas"]),
                    row["inicio"].date(),
                    row["fim"].date(),
                ),
            )
            atv_count += 1
    conn.commit()
    print(f"  {atv_count} atividades inseridas.")

    # 8. Verificar
    cur.execute("SELECT COUNT(*) AS n FROM cronograma_semanal")
    total = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM projetos")
    n_proj = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM responsaveis")
    n_resp = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM atividades")
    n_atv = cur.fetchone()["n"]

    print("\n✅ BANCO POPULADO COM SUCESSO!")
    print(f"   projetos          : {n_proj}")
    print(f"   responsaveis      : {n_resp}")
    print(f"   atividades        : {n_atv}")
    print(f"   cronograma_semanal: {total}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
