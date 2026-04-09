"""
charts.py
Funções de visualização Plotly para o dashboard de cronograma.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


CORES_PROJETOS = px.colors.qualitative.Bold


def _semana_label(dt):
    """Formata timestamp como '06/04'."""
    return pd.Timestamp(dt).strftime("%d/%m")


# -------------------------------------------------------
# 1. Heatmap de Ocupação
# -------------------------------------------------------
def fig_heatmap_ocupacao(df: pd.DataFrame, ferias: dict, capacidade: dict, pessoas_filtro: list, semanas_filtro: list):
    """
    Heatmap pessoa × semana mostrando % de ocupação.
    Férias ficam em cinza. Sobrecarga em vermelho.
    """
    df_f = df[df["Responsável"].isin(pessoas_filtro) & df["Semana"].isin(semanas_filtro)]
    semanas = sorted(semanas_filtro)
    pessoas = sorted(pessoas_filtro)

    z = []
    text = []
    customdata = []

    for pessoa in pessoas:
        row_z = []
        row_text = []
        row_custom = []
        cap = capacidade.get(pessoa, 36)
        for sem in semanas:
            # Férias?
            is_ferias = sem in ferias.get(pessoa, [])
            if is_ferias:
                row_z.append(None)
                row_text.append("Férias")
                row_custom.append((pessoa, _semana_label(sem), "Férias", cap))
            else:
                horas = df_f[(df_f["Responsável"] == pessoa) & (df_f["Semana"] == sem)]["Horas"].sum()
                pct_float = (horas / cap) * 100 if cap > 0 else 0
                pct = round(pct_float)
                row_z.append(pct_float)
                row_text.append(f"{horas:.0f}h<br>{pct}%")
                row_custom.append((pessoa, _semana_label(sem), horas, cap))
        z.append(row_z)
        text.append(row_text)
        customdata.append(row_custom)

    labels_x = [_semana_label(s) for s in semanas]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=labels_x,
        y=pessoas,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 10},
        colorscale=[
            # 0–90 % → verde pastel
            [0.000, "#d4edda"],
            [0.450, "#d4edda"],
            # 91–100 % → amarelo pastel
            [0.451, "#fff3cd"],
            [0.500, "#fff3cd"],
            # 101 %+ → vermelho pastel → forte
            [0.501, "#f8d7da"],
            [1.000, "#c0392b"],
        ],
        zmin=0,
        zmax=200,
        colorbar=dict(
            title="% Ocupação",
            ticksuffix="%",
            tickvals=[0, 90, 100, 150, 200],
            ticktext=["0%", "90%", "100%", "150%", "200%+"],
        ),
        hoverongaps=False,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Semana: %{x}<br>"
            "Horas: %{text}<br>"
            "<extra></extra>"
        ),
    ))

    # Células de férias em cinza
    shapes = []
    annotations = []
    for i, pessoa in enumerate(pessoas):
        for j, sem in enumerate(semanas):
            if sem in ferias.get(pessoa, []):
                shapes.append(dict(
                    type="rect",
                    xref="x", yref="y",
                    x0=j - 0.5, x1=j + 0.5,
                    y0=i - 0.5, y1=i + 0.5,
                    fillcolor="#b0b0b0",
                    opacity=0.8,
                    line_width=0,
                ))
                annotations.append(dict(
                    x=labels_x[j], y=pessoa,
                    text="🏖️", showarrow=False,
                    font=dict(size=12),
                ))

    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        title="Heatmap de Ocupação por Pessoa × Semana",
        xaxis_title="Semana",
        yaxis_title="",
        height=max(300, 60 * len(pessoas)),
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
        clickmode="event+select",
    )
    return fig


# -------------------------------------------------------
# 2a. Gantt Nível 1 — uma barra por projeto
# -------------------------------------------------------
def fig_gantt_projetos(df: pd.DataFrame, projetos_filtro: list):
    """Gantt nível 1: uma barra por projeto, mostrando período total e horas."""
    df_f = df[df["Projeto"].isin(projetos_filtro)].copy()
    proj_data = (
        df_f.groupby("Projeto")
        .agg(
            Inicio=("Semana", "min"),
            Fim=("Semana", "max"),
            TotalHoras=("Horas", "sum"),
            Atividades=("Atividade", "nunique"),
        )
        .reset_index()
        .sort_values("Inicio")
        .reset_index(drop=True)
    )
    proj_data["Fim"] = proj_data["Fim"] + pd.Timedelta(days=7)

    paleta = ["#1e3a5f", "#2471a3", "#1abc9c", "#e67e22",
              "#8e44ad", "#c0392b", "#27ae60", "#d35400"]
    cor_map = {p: paleta[i % len(paleta)] for i, p in enumerate(sorted(proj_data["Projeto"].unique()))}

    fig = px.timeline(
        proj_data,
        x_start="Inicio",
        x_end="Fim",
        y="Projeto",
        color="Projeto",
        color_discrete_map=cor_map,
        custom_data=["TotalHoras", "Atividades"],
        title="Gantt — Linha do Tempo dos Projetos",
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Início: %{base|%d/%m/%Y}  →  Fim: %{x|%d/%m/%Y}<br>"
            "Total Horas: %{customdata[0]:.0f}h<br>"
            "Atividades: %{customdata[1]}<extra></extra>"
        ),
        texttemplate="%{customdata[0]:.0f}h",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=12, color="white"),
        marker_line_color="white",
        marker_line_width=2,
    )
    n_rows = len(proj_data)
    fig.update_layout(
        height=max(350, 64 * n_rows + 120),
        plot_bgcolor="white",
        showlegend=False,
        margin=dict(l=10, r=10, t=60, b=40),
        xaxis_title="",
        yaxis_title="",
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e8edf3", tickformat="%d/%m", tickangle=-30)
    return fig


# -------------------------------------------------------
# 2b. Gantt Nível 2 — atividades de um projeto
# -------------------------------------------------------
def fig_gantt(df: pd.DataFrame, projetos_filtro: list):
    """Gráfico de Gantt horizontal por atividade × período."""
    df_f = df[df["Projeto"].isin(projetos_filtro)].copy()

    gantt_data = (
        df_f.groupby(["Projeto", "Atividade", "Responsável"])
        .agg(Inicio=("Semana", "min"), Fim=("Semana", "max"), TotalHoras=("Horas", "sum"))
        .reset_index()
    )
    gantt_data["Fim"] = gantt_data["Fim"] + pd.Timedelta(days=7)
    gantt_data = gantt_data.sort_values(["Projeto", "Inicio"]).reset_index(drop=True)

    # Número sequencial por projeto
    gantt_data["N"] = gantt_data.groupby("Projeto").cumcount() + 1
    gantt_data["Label"] = gantt_data.apply(
        lambda r: f"{r['N']:02d}. {r['Atividade'][:50]}", axis=1
    )

    paleta = [
        "#1e3a5f", "#2471a3", "#1abc9c", "#e67e22",
        "#8e44ad", "#c0392b", "#27ae60", "#d35400",
    ]
    pessoas_ord = sorted(gantt_data["Responsável"].unique())
    cor_map = {p: paleta[i % len(paleta)] for i, p in enumerate(pessoas_ord)}

    fig = px.timeline(
        gantt_data,
        x_start="Inicio",
        x_end="Fim",
        y="Label",
        color="Responsável",
        color_discrete_map=cor_map,
        custom_data=["Responsável", "TotalHoras", "Projeto", "N"],
        labels={"Label": ""},
        title="Gantt — Linha do Tempo das Atividades",
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{customdata[2]}</b><br>"
            "Atividade #%{customdata[3]}: %{y}<br>"
            "Responsável: %{customdata[0]}<br>"
            "Horas: %{customdata[1]:.0f}h<br>"
            "Início: %{base|%d/%m/%Y}<br>"
            "Fim: %{x|%d/%m/%Y}<extra></extra>"
        ),
        texttemplate="%{customdata[1]:.0f}h",
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=11, color="white"),
    )
    n_rows = len(gantt_data)
    fig.update_layout(
        height=max(500, 42 * n_rows + 120),
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=60, b=40),
        xaxis_title="",
        yaxis_title="",
        legend_title="Responsável",
        legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="right", x=1),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e8edf3", tickformat="%d/%m", tickangle=-30)
    return fig


# -------------------------------------------------------
# 3. Ranking de Projetos
# -------------------------------------------------------
def fig_ranking_projetos(df: pd.DataFrame, projetos_filtro: list):
    """Bar chart horizontal com total de horas por projeto."""
    df_f = df[df["Projeto"].isin(projetos_filtro)]
    ranking = (
        df_f.groupby("Projeto")["Horas"]
        .sum()
        .reset_index()
        .sort_values("Horas", ascending=True)
    )
    ranking["HorasStr"] = ranking["Horas"].apply(
        lambda h: f"{int(round(h)):,}h".replace(",", ".")
    )
    fig = px.bar(
        ranking,
        x="Horas",
        y="Projeto",
        orientation="h",
        color_discrete_sequence=["#1e3a5f"],
        text="HorasStr",
        title="Ranking — Total de Horas por Projeto",
        labels={"Horas": "Total de Horas", "Projeto": ""},
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        height=max(300, 45 * len(ranking)),
        plot_bgcolor="white",
        margin=dict(l=10, r=60, t=50, b=10),
    )
    return fig


# -------------------------------------------------------
# 4. Evolução Semanal do Time
# -------------------------------------------------------
def fig_evolucao_semanal(df: pd.DataFrame, capacidade: dict, pessoas_filtro: list, semanas_filtro: list, ferias: dict):
    """Área chart com horas semanais totais + linha de capacidade."""
    df_f = df[df["Responsável"].isin(pessoas_filtro) & df["Semana"].isin(semanas_filtro)]
    semanas = sorted(semanas_filtro)

    horas_por_semana = df_f.groupby("Semana")["Horas"].sum().reindex(semanas, fill_value=0)
    labels_x = [_semana_label(s) for s in semanas]

    # Capacidade disponível por semana (exclui férias)
    cap_por_semana = []
    for sem in semanas:
        total_cap = 0
        for p in pessoas_filtro:
            if sem not in ferias.get(p, []):
                total_cap += capacidade.get(p, 36)
        cap_por_semana.append(total_cap)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels_x,
        y=horas_por_semana.values,
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(52, 152, 219, 0.2)",
        line=dict(color="#2980b9", width=2),
        marker=dict(size=6),
        name="Horas realizadas",
        hovertemplate="Semana %{x}<br>Horas: %{y:.0f}h<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=labels_x,
        y=cap_por_semana,
        mode="lines",
        line=dict(color="#e74c3c", width=2, dash="dash"),
        name="Capacidade total",
        hovertemplate="Capacidade: %{y:.0f}h<extra></extra>",
    ))
    fig.update_layout(
        title="Evolução Semanal de Horas do Time",
        xaxis_title="Semana",
        yaxis_title="Horas",
        plot_bgcolor="white",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=70, b=10),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eeeeee")
    fig.update_yaxes(showgrid=True, gridcolor="#eeeeee")
    return fig


# -------------------------------------------------------
# 5. Gráfico de horas por pessoa (pizza / bar)
# -------------------------------------------------------
def fig_horas_por_pessoa(df: pd.DataFrame, pessoas_filtro: list):
    """Bar chart de total de horas por pessoa."""
    df_f = df[df["Responsável"].isin(pessoas_filtro)]
    por_pessoa = (
        df_f.groupby("Responsável")["Horas"]
        .sum()
        .reset_index()
        .sort_values("Horas", ascending=False)
    )
    por_pessoa["HorasStr"] = por_pessoa["Horas"].apply(
        lambda h: f"{int(round(h)):,}h".replace(",", ".")
    )
    fig = px.bar(
        por_pessoa,
        x="Responsável",
        y="Horas",
        color_discrete_sequence=["#1e3a5f"],
        text="HorasStr",
        title="Total de Horas por Pessoa",
        labels={"Horas": "Total de Horas"},
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="white",
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# -------------------------------------------------------
# 6. Sobreposições
# -------------------------------------------------------
def calcular_sobreposicoes(df: pd.DataFrame, pessoas_filtro: list, semanas_filtro: list):
    """
    Retorna DataFrame com linhas onde uma pessoa tem >1 projeto na mesma semana.
    Colunas: Responsável, Semana, Horas_Total, Projetos, Qtd_Projetos
    """
    df_f = df[df["Responsável"].isin(pessoas_filtro) & df["Semana"].isin(semanas_filtro)]
    agg = (
        df_f.groupby(["Responsável", "Semana"])
        .agg(
            Horas_Total=("Horas", lambda x: round(x.sum(), 1)),
            Projetos=("Projeto", lambda x: ", ".join(sorted(x.unique()))),
            Qtd_Projetos=("Projeto", "nunique"),
        )
        .reset_index()
    )
    sobreposicoes = agg[agg["Qtd_Projetos"] > 1].copy()
    sobreposicoes["Semana_Label"] = sobreposicoes["Semana"].apply(_semana_label)
    sobreposicoes = sobreposicoes.sort_values(["Responsável", "Semana"])
    return sobreposicoes


# -------------------------------------------------------
# 7. Alertas de Sobrecarga
# -------------------------------------------------------
def calcular_sobrecargas(df: pd.DataFrame, capacidade: dict, ferias: dict, pessoas_filtro: list, semanas_filtro: list):
    """
    Retorna DataFrame com semanas onde pessoa excede sua capacidade.
    """
    df_f = df[df["Responsável"].isin(pessoas_filtro) & df["Semana"].isin(semanas_filtro)]
    agg = df_f.groupby(["Responsável", "Semana"])["Horas"].sum().reset_index()

    alertas = []
    for _, row in agg.iterrows():
        pessoa = row["Responsável"]
        sem = row["Semana"]
        horas = row["Horas"]
        cap = capacidade.get(pessoa, 36)
        is_ferias = sem in ferias.get(pessoa, [])
        excesso = horas - cap
        if excesso > 0 and not is_ferias:
            alertas.append({
                "Responsável": pessoa,
                "Semana": _semana_label(sem),
                "Horas": round(horas, 1),
                "Capacidade": cap,
                "Excesso (h)": round(excesso, 1),
                "% Sobrecarga": f"{round((horas/cap)*100,1)}%",
            })

    return pd.DataFrame(alertas).sort_values("Excesso (h)", ascending=False) if alertas else pd.DataFrame()
