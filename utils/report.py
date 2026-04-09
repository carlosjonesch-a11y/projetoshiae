"""
report.py
Gera relatório HTML e PDF a partir dos dados do cronograma.
"""

import io
import base64
import pandas as pd
import plotly.io as pio


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório de Cronograma — {titulo}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6fa; color: #2d3436; }}
  .header {{ background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); color: white; padding: 36px 48px; }}
  .header h1 {{ font-size: 28px; font-weight: 700; }}
  .header p {{ font-size: 14px; opacity: 0.85; margin-top: 6px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .metrics {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 32px; }}
  .metric-card {{ background: white; border-radius: 12px; padding: 20px 24px; flex: 1; min-width: 180px;
                  box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 4px solid #3498db; }}
  .metric-card .label {{ font-size: 12px; color: #636e72; text-transform: uppercase; letter-spacing: 0.5px; }}
  .metric-card .value {{ font-size: 26px; font-weight: 700; color: #2d3436; margin-top: 4px; }}
  .metric-card .sub {{ font-size: 12px; color: #636e72; margin-top: 2px; }}
  .section {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px;
              box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
  .section h2 {{ font-size: 18px; font-weight: 600; color: #2c3e50; margin-bottom: 16px;
                 padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}
  .chart-img {{ width: 100%; border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f8f9fa; padding: 10px 14px; text-align: left; font-weight: 600;
        color: #636e72; border-bottom: 2px solid #dee2e6; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #f0f0f0; }}
  tr:hover td {{ background: #f8f9fa; }}
  .badge-red {{ background: #fdeded; color: #c0392b; padding: 2px 8px; border-radius: 12px;
                font-size: 11px; font-weight: 600; }}
  .badge-yellow {{ background: #fff8e1; color: #f39c12; padding: 2px 8px; border-radius: 12px;
                   font-size: 11px; font-weight: 600; }}
  .badge-green {{ background: #e8f5e9; color: #27ae60; padding: 2px 8px; border-radius: 12px;
                  font-size: 11px; font-weight: 600; }}
  .footer {{ text-align: center; font-size: 12px; color: #b2bec3; padding: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 Relatório de Cronograma de Projetos</h1>
  <p>Gerado em {data_geracao} &nbsp;|&nbsp; Período: {periodo}</p>
</div>
<div class="container">

  <!-- MÉTRICAS -->
  <div class="metrics">
    <div class="metric-card">
      <div class="label">Total de Horas</div>
      <div class="value">{total_horas}h</div>
      <div class="sub">no período selecionado</div>
    </div>
    <div class="metric-card">
      <div class="label">Projetos</div>
      <div class="value">{qtd_projetos}</div>
      <div class="sub">projetos ativos</div>
    </div>
    <div class="metric-card">
      <div class="label">Pessoa Mais Ocupada</div>
      <div class="value">{pessoa_top}</div>
      <div class="sub">{horas_pessoa_top}h totais</div>
    </div>
    <div class="metric-card">
      <div class="label">Semana Mais Carregada</div>
      <div class="value">{semana_top}</div>
      <div class="sub">{horas_semana_top}h nessa semana</div>
    </div>
    <div class="metric-card" style="border-color: {cor_sobreposicoes};">
      <div class="label">Sobreposições</div>
      <div class="value">{qtd_sobreposicoes}</div>
      <div class="sub">semanas com conflito</div>
    </div>
  </div>

  <!-- GRÁFICOS -->
  {secoes_graficos}

  <!-- TABELAS -->
  {secoes_tabelas}

</div>
<div class="footer">Relatório gerado pelo Dashboard de Cronograma de Projetos Einstein</div>
</body>
</html>
"""


def _fig_para_png_base64(fig):
    """Converte figura Plotly para imagem PNG em base64."""
    img_bytes = pio.to_image(fig, format="png", width=1100, height=fig.layout.height or 450, scale=1.5)
    return base64.b64encode(img_bytes).decode("utf-8")


def _tabela_html(df_table: pd.DataFrame, badge_col: str = None):
    """Gera HTML de uma tabela a partir de um DataFrame."""
    if df_table.empty:
        return "<p style='color:#636e72; font-style:italic;'>Nenhum dado encontrado.</p>"
    rows_html = ""
    for _, row in df_table.iterrows():
        cells = ""
        for col in df_table.columns:
            val = row[col]
            if badge_col and col == badge_col:
                try:
                    num = float(str(val).replace("%", "").replace("h", ""))
                    if num > 120:
                        badge = f'<span class="badge-red">{val}</span>'
                    elif num > 100:
                        badge = f'<span class="badge-yellow">{val}</span>'
                    else:
                        badge = f'<span class="badge-green">{val}</span>'
                    cells += f"<td>{badge}</td>"
                except Exception:
                    cells += f"<td>{val}</td>"
            else:
                cells += f"<td>{val}</td>"
        rows_html += f"<tr>{cells}</tr>"

    headers = "".join(f"<th>{c}</th>" for c in df_table.columns)
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{rows_html}</tbody></table>"


def gerar_html(
    df: pd.DataFrame,
    ferias: dict,
    capacidade: dict,
    semanas_filtro: list,
    pessoas_filtro: list,
    figs: dict,          # {"heatmap": fig, "gantt": fig, ...}
    df_sobrecargas: pd.DataFrame,
    df_sobreposicoes: pd.DataFrame,
):
    """Retorna string HTML completa do relatório."""
    from datetime import date

    df_f = df[df["Responsável"].isin(pessoas_filtro) & df["Semana"].isin(semanas_filtro)]

    total_horas = int(df_f["Horas"].sum())
    qtd_projetos = df_f["Projeto"].nunique()

    por_pessoa = df_f.groupby("Responsável")["Horas"].sum()
    pessoa_top = por_pessoa.idxmax() if not por_pessoa.empty else "—"
    horas_pessoa_top = int(por_pessoa.max()) if not por_pessoa.empty else 0

    por_semana = df_f.groupby("Semana")["Horas"].sum()
    if not por_semana.empty:
        semana_top_ts = por_semana.idxmax()
        semana_top = pd.Timestamp(semana_top_ts).strftime("%d/%m")
        horas_semana_top = int(por_semana.max())
    else:
        semana_top = "—"
        horas_semana_top = 0

    qtd_sobreposicoes = len(df_sobreposicoes) if df_sobreposicoes is not None else 0
    cor_sobreposicoes = "#e74c3c" if qtd_sobreposicoes > 0 else "#27ae60"

    if semanas_filtro:
        periodo = f"{pd.Timestamp(min(semanas_filtro)).strftime('%d/%m/%Y')} — {pd.Timestamp(max(semanas_filtro)).strftime('%d/%m/%Y')}"
    else:
        periodo = "—"

    # Gráficos como imagens
    nomes_graficos = {
        "heatmap": "Heatmap de Ocupação",
        "gantt": "Gantt — Linha do Tempo",
        "ranking": "Ranking de Projetos",
        "evolucao": "Evolução Semanal",
        "por_pessoa": "Total de Horas por Pessoa",
    }
    secoes_graficos = ""
    for key, titulo_sec in nomes_graficos.items():
        if key in figs and figs[key] is not None:
            try:
                b64 = _fig_para_png_base64(figs[key])
                secoes_graficos += f"""
                <div class="section">
                  <h2>{titulo_sec}</h2>
                  <img class="chart-img" src="data:image/png;base64,{b64}" alt="{titulo_sec}">
                </div>"""
            except Exception:
                pass

    # Tabelas
    secoes_tabelas = ""
    if df_sobrecargas is not None and not df_sobrecargas.empty:
        secoes_tabelas += f"""
        <div class="section">
          <h2>⚠️ Alertas de Sobrecarga</h2>
          {_tabela_html(df_sobrecargas, badge_col="% Sobrecarga")}
        </div>"""

    if df_sobreposicoes is not None and not df_sobreposicoes.empty:
        df_sob_display = df_sobreposicoes[["Responsável", "Semana_Label", "Horas_Total", "Projetos", "Qtd_Projetos"]].copy()
        df_sob_display.columns = ["Responsável", "Semana", "Horas", "Projetos", "Qtd. Projetos"]
        secoes_tabelas += f"""
        <div class="section">
          <h2>🔄 Sobreposições de Projetos</h2>
          {_tabela_html(df_sob_display)}
        </div>"""

    html = HTML_TEMPLATE.format(
        titulo="Einstein",
        data_geracao=date.today().strftime("%d/%m/%Y"),
        periodo=periodo,
        total_horas=total_horas,
        qtd_projetos=qtd_projetos,
        pessoa_top=pessoa_top,
        horas_pessoa_top=horas_pessoa_top,
        semana_top=semana_top,
        horas_semana_top=horas_semana_top,
        qtd_sobreposicoes=qtd_sobreposicoes,
        cor_sobreposicoes=cor_sobreposicoes,
        secoes_graficos=secoes_graficos,
        secoes_tabelas=secoes_tabelas,
    )
    return html


def gerar_pdf(html_content: str) -> bytes:
    """Converte HTML para PDF usando WeasyPrint."""
    try:
        from weasyprint import HTML as WH
        pdf_bytes = WH(string=html_content).write_pdf()
        return pdf_bytes
    except ImportError:
        raise ImportError("WeasyPrint não está instalado. Execute: pip install weasyprint")
