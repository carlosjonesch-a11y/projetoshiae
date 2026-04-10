"""
app.py — Dashboard de Cronograma de Projetos Einstein
Streamlit + Plotly · Layout redesenhado com filtros no topo
"""

import pandas as pd
import streamlit as st

from utils.charts import (
    fig_heatmap_ocupacao,
    fig_gantt,
    fig_gantt_projetos,
    fig_ranking_projetos,
    fig_evolucao_semanal,
    fig_horas_por_pessoa,
    calcular_sobrecargas,
)

# ── Configuração da página ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="Projetos Einstein",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Autenticação ───────────────────────────────────────────────────────────────
_APP_PASSWORD = st.secrets.get("APP_PASSWORD", None)

if _APP_PASSWORD:
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("""
        <style>
        #MainMenu, footer, header, .stDeployButton { display:none !important; }
        .login-box {
            max-width: 360px; margin: 80px auto 0; padding: 40px 36px 32px;
            background: white; border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.10);
            border: 1px solid #e8edf3;
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="login-box">
            <h3 style="margin:0 0 6px;color:#1e3a5f;">🔒 Gestão de Projetos</h3>
            <p style="color:#666;font-size:13px;margin-bottom:24px;">Acesso restrito. Informe a senha para continuar.</p>
        </div>
        """, unsafe_allow_html=True)
        _senha = st.text_input("Senha", type="password", label_visibility="collapsed",
                               placeholder="Digite a senha…")
        if st.button("Entrar", type="primary", use_container_width=True):
            if _senha == _APP_PASSWORD:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
        st.stop()

st.markdown("""
<style>
#MainMenu, footer, header, [data-testid="stSidebarNav"], .stDeployButton {
    display: none !important; visibility: hidden !important;
}
.main .block-container {
    padding: 1.2rem 2.5rem 2rem;
    max-width: 100%;
}
.page-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2471a3 100%);
    border-radius: 14px;
    padding: 20px 28px 16px;
    color: white;
    margin-bottom: 16px;
}
.page-header h1 { margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
.page-header p  { margin: 5px 0 0; font-size: 13px; opacity: 0.82; }
.filter-bar {
    background: white;
    border-radius: 10px;
    padding: 6px 16px 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 14px;
    border: 1px solid #e8edf3;
}
.filter-bar label {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.4px !important;
    color: #555 !important;
}
/* Tags do multiselect menores */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #1e3a5f !important;
    border-radius: 4px !important;
    padding: 0 6px !important;
    font-size: 11px !important;
    height: 20px !important;
    line-height: 20px !important;
    max-width: 90px !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    font-size: 11px !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    max-width: 68px !important;
    white-space: nowrap !important;
}
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    max-height: 60px !important;
    overflow-y: auto !important;
}
[data-testid="metric-container"] {
    background: white !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
    box-shadow: 0 1px 5px rgba(0,0,0,0.07) !important;
    border-left: 4px solid #2471a3 !important;
}
[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-size: 11px !important; color: #555 !important; text-transform: uppercase; letter-spacing: 0.4px; }
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-radius: 12px;
    padding: 5px 6px;
    gap: 3px;
    box-shadow: 0 1px 5px rgba(0,0,0,0.07);
    margin-bottom: 14px;
    border: 1px solid #e8edf3;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
}
.stTabs [aria-selected="true"] {
    background: #1e3a5f !important;
    color: white !important;
}
.section-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e3a5f;
    margin: 16px 0 8px;
    padding-bottom: 6px;
    border-bottom: 2px solid #e8edf3;
}
div[data-testid="stForm"] {
    background: white;
    border: 1px solid #e8edf3 !important;
    border-radius: 12px;
    padding: 16px !important;
}
/* Tamanho e alinhamento de tabelas */
[data-testid="stDataFrame"] {
    font-size: 13px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for _k, _v in [
    ("df", None), ("ferias", {}), ("semanas", []),
    ("pessoas", []), ("projetos", []), ("capacidade", {}), ("db_init", False),
    ("edit_proj", None), ("edit_resp", None), ("edit_atv", None),
    ("hm_sel", None),
    ("proj_meta", {}),
    ("encad_preview", None),
    ("encad_proj_id", None),
    ("ia_chat_history", []),
    ("ia_suggestions", []),
    ("ia_enc_preview", None),
    ("ia_enc_proj_nome", None),
    ("enc_manual_preview", None),
    ("enc_manual_alvo", None),
    ("enc_undo_snapshot", None),
    ("_needs_reload", False),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Helpers column_config ──────────────────────────────────────────────────────
def _fh(v):
    """Formata horas com separador de milhar brasileiro (ponto), sem decimais desnecessários."""
    v = round(float(v or 0), 1)
    if v == int(v):
        return f"{int(v):,}h".replace(",", ".")
    # Ex: 1234.5 → "1,234.5h" → "1.234,5h"
    s = f"{v:,.1f}h"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")

def _cc_h(label, width="small"):
    return st.column_config.NumberColumn(label, format="%.0fh", width=width)

def _cc_txt(label, width="medium"):
    return st.column_config.TextColumn(label, width=width)

def _cc_num(label, width="small"):
    return st.column_config.NumberColumn(label, width=width)

def _cc_pct(label):
    return st.column_config.TextColumn(label, width="small")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-header">
    <h1>Gestão de projetos</h1>
    <p>Gestão de cronogramas · Ocupação da equipe · Análise de projetos</p>
</div>""", unsafe_allow_html=True)

# ── Auto-load do banco ─────────────────────────────────────────────────────────
from utils import db as _db_loader
_should_reload = (
    st.session_state.df is None
    or st.session_state.get("_needs_reload", False)
)
if _should_reload and _db_loader.is_configured():
    st.session_state["_needs_reload"] = False  # consome o flag
    try:
        df_db, fer_db, sem_db, pes_db, proj_db = _db_loader.carregar_cronograma_do_banco()
        if df_db is not None:
            st.session_state.df       = df_db
            st.session_state.semanas  = sem_db
            st.session_state.pessoas  = pes_db
            st.session_state.projetos = proj_db
            # Carrega férias do banco (sobrescreve dict vazio)
            try:
                st.session_state.ferias = _db_loader.carregar_ferias_como_dict()
            except Exception:
                st.session_state.ferias = fer_db
            # Carrega capacidade SEMPRE do banco (não só pra novos)
            try:
                _resps_load = _db_loader.listar_responsaveis()
                _cap_db = {r["nome"]: int(r["capacidade_semanal"]) for r in _resps_load}
                st.session_state.capacidade = _cap_db
            except Exception:
                pass
            # Carrega metadados de projetos para filtros de Unidade/Departamento
            try:
                _projs_meta = _db_loader.listar_projetos()
                st.session_state.proj_meta = {
                    p2["nome"]: {
                        "unidade":      p2.get("unidade", ""),
                        "departamento": p2.get("departamento", ""),
                    }
                    for p2 in _projs_meta
                }
            except Exception:
                st.session_state.proj_meta = {}
    except Exception:
        pass

# ── Sem dados ─────────────────────────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown("---")
    st.info("🗄️ Nenhum dado encontrado. Acesse a aba **Cadastro** para adicionar projetos e atividades.")
    if not _db_loader.is_configured():
        st.warning("⚙️ Configure `NEON_DATABASE_URL` em `.streamlit/secrets.toml` para conectar ao banco.")
    st.stop()


# ── Referências ────────────────────────────────────────────────────────────────
df         = st.session_state.df
ferias     = st.session_state.ferias
semanas    = st.session_state.semanas
pessoas    = st.session_state.pessoas
projetos   = st.session_state.projetos
capacidade = st.session_state.capacidade

# ── Filtros (topo) ─────────────────────────────────────────────────────────────
_proj_meta    = st.session_state.get("proj_meta", {})
_unidades_all = sorted({v["unidade"]      for v in _proj_meta.values() if v.get("unidade")})
_deptos_all   = sorted({v["departamento"] for v in _proj_meta.values() if v.get("departamento")})

# ── Cascade: lê seleções do rerun anterior ────────────────────────────────────
_cur_unid = st.session_state.get("flt_unidade",  [])
_cur_dept = st.session_state.get("flt_depto",    [])
_cur_pess = st.session_state.get("flt_pessoas",  [])
_cur_proj = st.session_state.get("flt_projetos", [])

# Passo 1: Unidade → proj_scope e deptos disponíveis
_cur_unid = [u for u in _cur_unid if u in _unidades_all]
if _cur_unid:
    _proj_scope  = {n for n, m in _proj_meta.items() if m.get("unidade") in _cur_unid}
    _deptos_opts = sorted({m["departamento"] for n, m in _proj_meta.items()
                           if n in _proj_scope and m.get("departamento")})
else:
    _proj_scope  = set(projetos)
    _deptos_opts = _deptos_all

# Passo 2: Departamento → restringe proj_scope
_cur_dept = [d for d in _cur_dept if d in _deptos_opts]
if _cur_dept:
    _proj_scope = {n for n in _proj_scope
                   if _proj_meta.get(n, {}).get("departamento") in _cur_dept}

# Passo 3: proj_scope → pessoas candidatas (quem trabalha nesses projetos)
_df_scope   = df[df["Projeto"].isin(_proj_scope)]
_pess_scope = sorted(_df_scope["Responsável"].unique().tolist()) if not _df_scope.empty else sorted(pessoas)

# Passo 4: Pessoas selecionadas → restringe proj_scope
_cur_pess = [p for p in _cur_pess if p in _pess_scope]
if _cur_pess:
    _df_pess    = df[df["Responsável"].isin(_cur_pess) & df["Projeto"].isin(_proj_scope)]
    _proj_scope = _proj_scope & set(_df_pess["Projeto"].unique())

# Passo 5: proj_scope final → lista de projetos disponíveis
_proj_opts = sorted(_proj_scope)
_cur_proj  = [p for p in _cur_proj if p in _proj_opts]

# Passo 6: Projetos selecionados → restringe pessoas disponíveis
if _cur_proj:
    _df_proj    = df[df["Projeto"].isin(_cur_proj) & df["Responsável"].isin(_pess_scope)]
    _pess_scope = sorted(set(_pess_scope) & set(_df_proj["Responsável"].unique()))
    _cur_pess   = [p for p in _cur_pess if p in _pess_scope]

# Limpa session_state com valores válidos → auto-cascade no próximo rerun
st.session_state["flt_unidade"]  = _cur_unid
st.session_state["flt_depto"]    = _cur_dept
st.session_state["flt_pessoas"]  = _cur_pess
st.session_state["flt_projetos"] = _cur_proj

# ── Render filtros ─────────────────────────────────────────────────────────────
st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

# Linha 1: Período · Unidade · Departamento
fc1, fc2, fc3 = st.columns([3, 2, 2])

with fc1:
    sem_labels = [pd.Timestamp(s).strftime("%d/%m") for s in semanas]
    idx_ini, idx_fim = st.select_slider(
        "📅 Período",
        options=list(range(len(semanas))),
        value=(0, len(semanas) - 1),
        format_func=lambda i: sem_labels[i],
        key="flt_period",
    )
    semanas_filtro = semanas[idx_ini: idx_fim + 1]

with fc2:
    st.multiselect(
        f"🏥 Unidade  ({len(_unidades_all)} disponíveis)",
        options=_unidades_all,
        key="flt_unidade",
        placeholder="Todas as unidades…",
    )

with fc3:
    st.multiselect(
        f"🏢 Departamento  ({len(_deptos_opts)} disponíveis)",
        options=_deptos_opts,
        key="flt_depto",
        placeholder="Todos os departamentos…",
    )

# Linha 2: Pessoas · Projetos
fe1, fe2 = st.columns(2)

with fe1:
    st.multiselect(
        f"👥 Pessoas  ({len(_pess_scope)} disponíveis)",
        options=_pess_scope,
        key="flt_pessoas",
        placeholder="Todas as pessoas…",
    )
    pessoas_filtro = _cur_pess if _cur_pess else list(_pess_scope)

with fe2:
    st.multiselect(
        f"📁 Projetos  ({len(_proj_opts)} disponíveis)",
        options=_proj_opts,
        key="flt_projetos",
        placeholder="Todos os projetos…",
    )
    projetos_filtro = _cur_proj if _cur_proj else _proj_opts

st.markdown('</div>', unsafe_allow_html=True)

# ── DataFrame filtrado ─────────────────────────────────────────────────────────
df_f = df[
    df["Responsável"].isin(pessoas_filtro) &
    df["Projeto"].isin(projetos_filtro) &
    df["Semana"].isin(semanas_filtro)
]

# ── Cálculos base ──────────────────────────────────────────────────────────────
df_sob = calcular_sobrecargas(df, capacidade, ferias, pessoas_filtro, semanas_filtro)

por_pessoa = df_f.groupby("Responsável")["Horas"].sum()
pessoa_top = por_pessoa.idxmax() if not por_pessoa.empty else "—"
horas_top  = round(por_pessoa.max(), 1) if not por_pessoa.empty else 0

por_semana = df_f.groupby("Semana")["Horas"].sum()
if not por_semana.empty:
    sem_top_label = pd.Timestamp(por_semana.idxmax()).strftime("%d/%m")
    horas_sem_top = round(por_semana.max(), 1)
else:
    sem_top_label, horas_sem_top = "—", 0

# ── Métricas ───────────────────────────────────────────────────────────────────
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
with mc1: st.metric("⏱️ Total Horas",        _fh(df_f['Horas'].sum()))
with mc2: st.metric("📁 Projetos Ativos",    df_f["Projeto"].nunique())
with mc3: st.metric("🏆 Mais Ocupado",       pessoa_top, f"{_fh(horas_top)} totais")
with mc4: st.metric("📅 Semana + Carregada", sem_top_label, _fh(horas_sem_top))
with mc5: st.metric("⚠️ Sobrecargas",        len(df_sob), delta_color="inverse")

st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
(
    tab_ocup, tab_gantt, tab_proj, tab_evol,
    tab_pess, tab_cap, tab_cad, tab_ia,
) = st.tabs([
    "🌡️ Ocupação", "📅 Gantt", "🏆 Projetos", "📈 Evolução",
    "👥 Pessoas",  "⚡ Capacidade", "🗄️ Cadastro", "🤖 IA Gestão",
])

# ═══ OCUPAÇÃO ══════════════════════════════════════════════════════════════════
with tab_ocup:
    st.markdown('<p class="section-title">Heatmap de Ocupação · Pessoa × Semana</p>', unsafe_allow_html=True)
    st.caption("Verde ≤ 90% · Amarelo 91–100% · Vermelho > 100% · 🏖️ Férias · 💡 Clique numa célula para ver as atividades")
    if pessoas_filtro and semanas_filtro:
        _label_to_sem = {pd.Timestamp(s).strftime("%d/%m"): s for s in semanas}
        _fig_hm = fig_heatmap_ocupacao(df, ferias, capacidade, pessoas_filtro, semanas_filtro)
        _ev = st.plotly_chart(
            _fig_hm,
            use_container_width=True,
            on_select="rerun",
            key="hm_ocup",
        )
        # captura clique via on_select (funciona em Streamlit >=1.33 com clickmode='event+select')
        _pts = []
        if _ev and hasattr(_ev, "selection") and _ev.selection:
            _pts = getattr(_ev.selection, "points", []) or []
        if _pts:
            _pt = _pts[0]
            # go.Heatmap pode retornar y/x como string ou index — normaliza
            _y_raw = _pt.get("y")
            _x_raw = _pt.get("x")
            if isinstance(_y_raw, (int, float)):
                _y_raw = pessoas_filtro[int(_y_raw)] if int(_y_raw) < len(pessoas_filtro) else None
            if _y_raw is not None and _x_raw is not None:
                st.session_state["hm_sel"] = {
                    "pessoa":  str(_y_raw),
                    "x_label": str(_x_raw),
                }

        # ── Seletor manual (sempre disponível como alternativa ao clique) ──
        _hm_labels_x = [pd.Timestamp(s).strftime("%d/%m") for s in semanas_filtro]
        st.caption("💡 **Clique numa célula** ou use os seletores abaixo para ver e editar atividades:")
        _hmc1, _hmc2, _hmc3 = st.columns([2, 2, 1])
        with _hmc1:
            _pick_pessoa = st.selectbox(
                "Pessoa", ["— selecione —"] + list(pessoas_filtro),
                key="hm_pick_pessoa", label_visibility="collapsed",
            )
        with _hmc2:
            _pick_sem = st.selectbox(
                "Semana", ["— selecione —"] + _hm_labels_x,
                key="hm_pick_sem", label_visibility="collapsed",
            )
        with _hmc3:
            if st.button("🔍 Ver", key="hm_pick_btn", use_container_width=True):
                if _pick_pessoa != "— selecione —" and _pick_sem != "— selecione —":
                    st.session_state["hm_sel"] = {"pessoa": _pick_pessoa, "x_label": _pick_sem}
                    st.rerun()

        # ── Painel de atividades da célula selecionada ─────────────────────
        _sel = st.session_state.get("hm_sel")
        if _sel and _sel.get("pessoa") and _sel.get("x_label"):
            _hm_pessoa  = _sel["pessoa"]
            _hm_x_label = _sel["x_label"]
            _hm_semana  = _label_to_sem.get(_hm_x_label)

            # Carga atual da pessoa na semana selecionada
            _hm_horas_sem = 0.0
            if _hm_semana is not None and df is not None:
                _mask = (df["Responsável"] == _hm_pessoa) & (df["Semana"] == pd.Timestamp(_hm_semana))
                _hm_horas_sem = float(df[_mask]["Horas"].sum())
            _hm_cap = capacidade.get(_hm_pessoa, 36)
            _hm_pct = round(_hm_horas_sem / _hm_cap * 100) if _hm_cap > 0 else 0

            st.markdown("---")
            _ht1, _ht2 = st.columns([6, 1])
            with _ht1:
                st.markdown(
                    f'<p class="section-title">📋 Atividades de <b>{_hm_pessoa}</b> · semana {_hm_x_label}</p>',
                    unsafe_allow_html=True,
                )
            with _ht2:
                if st.button("✖ Fechar", key="hm_close"):
                    st.session_state["hm_sel"] = None
                    st.rerun()

            # Barra de carga semanal
            _cor_bar = "normal" if _hm_pct <= 90 else ("off" if _hm_pct <= 110 else "inverse")
            st.progress(
                min(_hm_pct / 100, 1.0),
                text=f"Carga semana {_hm_x_label}: **{_hm_horas_sem:.0f}h** de {_hm_cap}h ({_hm_pct}%)"
                     + (" 🔴 SOBRECARGA" if _hm_pct > 110 else (" 🟡" if _hm_pct > 90 else (" 🟢" if _hm_pct > 60 else " ⬜"))),
            )

            # ── Gráfico empilhado: horas/projeto × semana para a pessoa selecionada ──
            if df is not None:
                _df_p = df[df["Responsável"] == _hm_pessoa].copy()
                if not _df_p.empty:
                    import plotly.graph_objects as _go
                    _sems_all = sorted(_df_p["Semana"].unique())
                    _sems_lbl = [pd.Timestamp(s).strftime("%d/%m") for s in _sems_all]
                    _projs_p  = sorted(_df_p["Projeto"].dropna().unique())
                    _fig_stk  = _go.Figure()
                    for _proj in _projs_p:
                        _y_vals = [
                            float(_df_p[(_df_p["Semana"] == s) & (_df_p["Projeto"] == _proj)]["Horas"].sum())
                            for s in _sems_all
                        ]
                        _fig_stk.add_trace(_go.Bar(name=_proj, x=_sems_lbl, y=_y_vals))
                    # Linha de capacidade
                    _fig_stk.add_trace(_go.Scatter(
                        x=_sems_lbl, y=[_hm_cap] * len(_sems_lbl),
                        mode="lines", name=f"Cap. ({_hm_cap}h)",
                        line=dict(color="red", dash="dash", width=1.5),
                        showlegend=True,
                    ))
                    # Destaque da semana selecionada
                    if _hm_x_label in _sems_lbl:
                        _xi = _sems_lbl.index(_hm_x_label)
                        _fig_stk.add_vrect(
                            x0=_xi - 0.5, x1=_xi + 0.5,
                            fillcolor="royalblue", opacity=0.12, line_width=0,
                        )
                    _fig_stk.update_layout(
                        barmode="stack", height=300,
                        margin=dict(l=0, r=0, t=28, b=0),
                        legend=dict(orientation="h", yanchor="top", y=-0.20, xanchor="left", x=0),
                        paper_bgcolor="white", plot_bgcolor="white",
                        title=dict(text=f"Demanda semanal por projeto — {_hm_pessoa}", font=dict(size=13)),
                        yaxis=dict(title="horas"),
                        xaxis=dict(tickangle=-45),
                    )
                    st.plotly_chart(_fig_stk, use_container_width=True, key="hm_stk_bar")
                    st.caption(f"🟦 Semana {_hm_x_label} destacada · 🔴 linha = capacidade ({_hm_cap}h/sem)")

            if _hm_semana:
                try:
                    from utils import db as _db_hm
                    _ativs_hm = _db_hm.listar_atividades_por_pessoa_semana(
                        _hm_pessoa, pd.Timestamp(_hm_semana).date()
                    )
                    if _ativs_hm:
                        # Carga de cada pessoa na semana (para dropdown de redistribuição)
                        _carga_sem = {}
                        if df is not None:
                            for _pp in pessoas_filtro:
                                _mm = (df["Responsável"] == _pp) & (df["Semana"] == pd.Timestamp(_hm_semana))
                                _carga_sem[_pp] = float(df[_mm]["Horas"].sum())

                        for _atv in _ativs_hm:
                            _atv_label = f"📌 **{_atv['projeto_nome']}** — {_atv['nome']} ({_fh(float(_atv.get('horas_estimadas') or 0))})"
                            with st.expander(_atv_label, expanded=True):
                                with st.form(f"hm_edit_{_atv['id']}"):
                                    _ea1, _ea2 = st.columns(2)
                                    with _ea1:
                                        _new_nome = st.text_input("🏷️ Nome", value=_atv["nome"])
                                        _new_horas = st.number_input(
                                            "⏱️ Total de horas", 0.0, 9999.0,
                                            float(_atv.get("horas_estimadas") or 0), step=0.5,
                                            help="Horas TOTAIS da atividade — divididas pelo nº de semanas",
                                        )
                                        if _atv.get("semana_inicio") and _atv.get("semana_fim") and _new_horas > 0:
                                            _nsem_hm = max(1, ((_atv["semana_fim"] - _atv["semana_inicio"]).days // 7) + 1)
                                            st.caption(f"📊 ≈ **{_new_horas / _nsem_hm:.1f} h/semana** ({_nsem_hm} sem.)")
                                    with _ea2:
                                        # Dropdown de responsável com carga de cada um
                                        _resp_opts_hm = [
                                            f"{p}  ({_carga_sem.get(p, 0):.0f}h / {capacidade.get(p, 36)}h)"
                                            for p in pessoas_filtro
                                        ]
                                        _resp_labels_hm = list(pessoas_filtro)
                                        _resp_idx_hm = _resp_labels_hm.index(_atv["responsavel"]) \
                                            if _atv.get("responsavel") in _resp_labels_hm else 0
                                        _new_resp_display = st.selectbox(
                                            "👤 Responsável",
                                            _resp_opts_hm,
                                            index=_resp_idx_hm,
                                        )
                                        _new_resp = _resp_labels_hm[_resp_opts_hm.index(_new_resp_display)]
                                        _new_ini = st.date_input(
                                            "📅 Início", value=_atv["semana_inicio"],
                                            format="DD/MM/YYYY",
                                        )
                                        _new_fim = st.date_input(
                                            "📅 Término", value=_atv["semana_fim"],
                                            format="DD/MM/YYYY",
                                        )
                                    _sb1, _sb2 = st.columns(2)
                                    with _sb1:
                                        if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                                            try:
                                                _db_hm.atualizar_atividade(
                                                    _atv["id"], _new_nome, _new_resp,
                                                    _new_horas, _new_ini, _new_fim,
                                                    int(_atv.get("ordem") or 0),
                                                )
                                                st.success("✅ Atividade atualizada!")
                                                st.session_state.df = None
                                                st.rerun()
                                            except Exception as _e:
                                                st.error(str(_e))
                                    with _sb2:
                                        if st.form_submit_button("🗑️ Excluir", use_container_width=True):
                                            try:
                                                _db_hm.deletar_atividade(_atv["id"])
                                                st.session_state.df = None
                                                st.session_state["hm_sel"] = None
                                                st.rerun()
                                            except Exception as _e:
                                                st.error(str(_e))
                    else:
                        _df_cell = df[
                            (df["Responsável"] == _hm_pessoa) & (df["Semana"] == pd.Timestamp(_hm_semana))
                        ] if df is not None else pd.DataFrame()
                        if not _df_cell.empty:
                            for _, _row in _df_cell.drop_duplicates(["Projeto", "Atividade"]).iterrows():
                                st.info(
                                    f"📌 **{_row['Projeto']}** — {_row['Atividade']} ({_fh(_row['Horas'])})"
                                    "\n\n_Atividade do banco não encontrada — use a aba Cadastro para editar._"
                                )
                        else:
                            st.info("Nenhuma atividade encontrada para esta célula.")
                except Exception as _exc:
                    st.warning(f"Erro ao buscar atividades: {_exc}")
    if not df_sob.empty:
        st.markdown('<p class="section-title">⚠️ Alertas de Sobrecarga</p>', unsafe_allow_html=True)
        df_sob_disp = df_sob.copy()
        df_sob_disp["Nível"] = df_sob_disp["Excesso (h)"].apply(
            lambda x: "🔴 Crítico" if x > 10 else ("🟠 Alto" if x > 5 else "🟡 Moderado")
        )
        df_sob_disp["Utilização %"] = df_sob_disp["% Sobrecarga"].str.replace("%", "").astype(float)
        st.dataframe(
            df_sob_disp[["Nível", "Responsável", "Semana", "Horas", "Capacidade", "Excesso (h)", "Utilização %"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Nível":         st.column_config.TextColumn("Nível", width="small"),
                "Responsável":   st.column_config.TextColumn("Responsável", width="medium"),
                "Semana":        st.column_config.TextColumn("Semana", width="small"),
                "Horas":         st.column_config.NumberColumn("Horas", format="%.0fh", width="small"),
                "Capacidade":    st.column_config.NumberColumn("Capacidade", format="%.0fh", width="small"),
                "Excesso (h)":   st.column_config.NumberColumn("Excesso", format="%.0fh", width="small"),
                "Utilização %":  st.column_config.ProgressColumn(
                    "Utilização", min_value=0, max_value=200, format="%d%%",
                ),
            },
        )
    else:
        st.success("✅ Nenhuma sobrecarga no período selecionado.")

    # ── Alertas de conflito com férias ────────────────────────────────────
    _ferias_dash = st.session_state.get("ferias", {})
    if _ferias_dash:
        try:
            from utils import db as _db_conf
            _all_ativs_dash = _db_conf.listar_atividades()
            _conf_dash = _db_conf.checar_conflitos_ferias(_ferias_dash, _all_ativs_dash)
            if _conf_dash:
                st.markdown('<p class="section-title">🏖️ Conflitos com Férias</p>',
                            unsafe_allow_html=True)
                for _cd in _conf_dash:
                    st.warning(
                        f"**{_cd['responsavel']}** está de férias nas semanas "
                        f"{', '.join(_cd['semanas_conflito'])} mas possui atividade: "
                        f"**{_cd['atividade']}** ({_cd['projeto']})"
                    )
        except Exception:
            pass

# ═══ GANTT ═════════════════════════════════════════════════════════════════════
with tab_gantt:
    if projetos_filtro and not df_f.empty:
        st.markdown('<p class="section-title">Gantt — Atividades do Projeto</p>',
                    unsafe_allow_html=True)
        _proj_gantt = st.multiselect(
            "Selecionar projeto(s):",
            options=projetos_filtro,
            default=[],
            key="gantt_proj_sel",
            placeholder="Todos os projetos…",
        )
        _proj_gantt_sel = _proj_gantt if _proj_gantt else projetos_filtro
        st.plotly_chart(fig_gantt(df_f, _proj_gantt_sel), use_container_width=True)
    else:
        st.warning("Selecione projetos e período para visualizar o Gantt.")

# ═══ PROJETOS ══════════════════════════════════════════════════════════════════
with tab_proj:
    st.markdown('<p class="section-title">Ranking de Horas por Projeto</p>', unsafe_allow_html=True)
    if projetos_filtro and not df_f.empty:
        st.plotly_chart(fig_ranking_projetos(df_f, projetos_filtro), use_container_width=True)
    else:
        st.warning("Selecione projetos e período.")

# ═══ EVOLUÇÃO ══════════════════════════════════════════════════════════════════
with tab_evol:
    st.markdown('<p class="section-title">Evolução Semanal de Horas do Time</p>', unsafe_allow_html=True)
    if pessoas_filtro and semanas_filtro:
        st.plotly_chart(
            fig_evolucao_semanal(df, capacidade, pessoas_filtro, semanas_filtro, ferias),
            use_container_width=True,
        )

# ═══ PESSOAS ═══════════════════════════════════════════════════════════════════
with tab_pess:
    st.markdown('<p class="section-title">Distribuição de Horas por Pessoa</p>', unsafe_allow_html=True)
    if pessoas_filtro and not df_f.empty:
        st.plotly_chart(fig_horas_por_pessoa(df_f, pessoas_filtro), use_container_width=True)
        fer_pessoas = [p for p in pessoas_filtro if p in ferias and ferias[p]]
        if fer_pessoas:
            st.markdown('<p class="section-title">🏖️ Férias Detectadas</p>', unsafe_allow_html=True)
            cols_fer = st.columns(min(len(fer_pessoas), 4))
            for i, p in enumerate(fer_pessoas):
                with cols_fer[i % 4]:
                    labels = " · ".join(pd.Timestamp(s).strftime("%d/%m") for s in ferias[p])
                    st.info(f"**{p}**\n\n{labels}")

# ═══ CAPACIDADE ════════════════════════════════════════════════════════════════
with tab_cap:
    st.markdown('<p class="section-title">⚡ Capacidade Semanal da Equipe</p>', unsafe_allow_html=True)
    st.caption("Defina o máximo de horas por semana por pessoa. Usado no cálculo de sobrecarga e % de ocupação.")

    n_cols = min(len(pessoas), 4)
    cap_cols = st.columns(n_cols)
    for i, pessoa in enumerate(pessoas):
        with cap_cols[i % n_cols]:
            cap_val = st.number_input(
                pessoa,
                min_value=1, max_value=80,
                value=int(st.session_state.capacidade.get(pessoa, 36)),
                step=1,
                key=f"cap_{pessoa}",
            )
            st.session_state.capacidade[pessoa] = cap_val

    if st.button("💾 Salvar capacidades no banco", type="primary"):
        try:
            _resps_save = _db_loader.listar_responsaveis()
            _resp_map   = {r["nome"]: r for r in _resps_save}
            for p in pessoas:
                nova_cap = int(st.session_state.capacidade.get(p, 36))
                if p in _resp_map:
                    r = _resp_map[p]
                    _db_loader.atualizar_responsavel(r["id"], r["nome"], r.get("email", ""), nova_cap)
            st.success("✅ Capacidades salvas!")
        except Exception as _ce:
            st.error(str(_ce))

    st.markdown('<p class="section-title">Resumo de Capacidade × Utilização</p>', unsafe_allow_html=True)
    cap_data = []
    for p in pessoas:
        if p not in pessoas_filtro:
            continue
        cap = st.session_state.capacidade.get(p, 36)
        horas_tot  = round(df[df["Responsável"] == p]["Horas"].sum(), 1)
        sems_uteis = len([s for s in semanas_filtro if s not in ferias.get(p, [])])
        cap_total  = cap * sems_uteis
        pct = round((horas_tot / cap_total * 100), 1) if cap_total > 0 else 0
        cap_data.append({
            "Pessoa":        p,
            "Cap/Sem (h)":   cap,
            "Sem. Úteis":    sems_uteis,
            "Cap Total (h)": cap_total,
            "Alocado (h)":   horas_tot,
            "Utilização %":  pct,
        })
    if cap_data:
        df_cap = pd.DataFrame(cap_data)
        st.dataframe(
            df_cap,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pessoa":        st.column_config.TextColumn("Pessoa", width="medium"),
                "Cap/Sem (h)":   st.column_config.NumberColumn("Cap/Sem", format="%.0fh", width="small"),
                "Sem. Úteis":    st.column_config.NumberColumn("Sem. Úteis", width="small"),
                "Cap Total (h)": st.column_config.NumberColumn("Cap Total", format="%.0fh", width="small"),
                "Alocado (h)":   st.column_config.NumberColumn("Alocado", format="%.0fh", width="small"),
                "Utilização %":  st.column_config.ProgressColumn(
                    "Utilização", min_value=0, max_value=150, format="%d%%",
                ),
            },
        )

# ═══ CADASTRO ══════════════════════════════════════════════════════════════════
with tab_cad:
    st.markdown('<p class="section-title">🗄️ Cadastro no Banco de Dados Neon</p>', unsafe_allow_html=True)

    try:
        from utils import db as _db
        _db_ok = True
    except ImportError:
        _db_ok = False
        st.error("psycopg2 não instalado. Execute: `pip install psycopg2-binary`")

    if _db_ok:
        if not _db.is_configured():
            st.warning("⚙️ Banco de dados não configurado.")
            st.markdown("""
**Para ativar o cadastro:**
1. Crie conta gratuita em [neon.tech](https://neon.tech)
2. Crie um projeto/banco de dados
3. Copie a **Connection String**
4. Cole em `.streamlit/secrets.toml`:
```toml
NEON_DATABASE_URL = "postgresql://user:pass@host/neondb?sslmode=require"
```
5. Reinicie o app (`Ctrl+C` → `streamlit run app.py`)
            """)
        else:
            if not st.session_state.db_init:
                try:
                    _db.init_tables()
                    st.session_state.db_init = True
                except Exception as e:
                    st.error(f"Erro ao inicializar banco: {e}")
                    st.stop()

            sub_proj, sub_atv, sub_resp, sub_fer = st.tabs(
                ["📁 Projetos", "📋 Atividades", "👤 Responsáveis", "🏖️ Férias"]
            )

            # ── Projetos ──────────────────────────────────────────────────────
            with sub_proj:
                cf1, cf2 = st.columns([1, 2])
                with cf1:
                    st.markdown("**Novo Projeto**")
                    with st.form("form_projeto", clear_on_submit=True):
                        nome_p   = st.text_input("Nome *", placeholder="Ex: HOEB - Fase 2")
                        desc_p   = st.text_area("Descrição", height=60)
                        gp1, gp2 = st.columns(2)
                        with gp1:
                            unid_p = st.text_input("Unidade", placeholder="Ex: HMI")
                            subarea_p = st.text_input("Sub-área", placeholder="Ex: TI Clínica")
                        with gp2:
                            depto_p = st.text_input("Departamento", placeholder="Ex: Projetos")
                            tipo_p  = st.text_input("Tipo de Projeto", placeholder="Ex: Implantação")
                        status_p = st.selectbox("Status", ["Ativo", "Pausado", "Concluído"])
                        venc_p   = st.date_input("📅 Data de Vencimento", value=None, format="DD/MM/YYYY")
                        if st.form_submit_button("➕ Salvar Projeto", type="primary", use_container_width=True):
                            if nome_p.strip():
                                try:
                                    _db.inserir_projeto(nome_p, desc_p, status_p,
                                                        unid_p, depto_p, subarea_p, tipo_p,
                                                        data_vencimento=venc_p or None)
                                    st.success("Projeto salvo!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                            else:
                                st.warning("Informe o nome.")
                with cf2:
                    st.markdown("**Projetos Cadastrados**")
                    try:
                        projs = _db.listar_projetos()
                        BADGE = {"Ativo": "🟢", "Pausado": "🟡", "Concluído": "⚫"}
                        if projs:
                            for p in projs:
                                if st.session_state.edit_proj == p["id"]:
                                    with st.form(f"edit_p_{p['id']}"):
                                        ep_nome  = st.text_input("Nome", value=p["nome"])
                                        ep_desc  = st.text_area("Descrição", value=p.get("descricao", ""), height=50)
                                        eg1, eg2 = st.columns(2)
                                        with eg1:
                                            ep_unid   = st.text_input("Unidade", value=p.get("unidade", ""))
                                            ep_sub    = st.text_input("Sub-área", value=p.get("subarea", ""))
                                        with eg2:
                                            ep_depto  = st.text_input("Departamento", value=p.get("departamento", ""))
                                            ep_tipo   = st.text_input("Tipo", value=p.get("tipo_projeto", ""))
                                        _stati    = ["Ativo", "Pausado", "Concluído"]
                                        ep_status = st.selectbox("Status", _stati,
                                                                  index=_stati.index(p.get("status", "Ativo")))
                                        ep_venc   = st.date_input(
                                            "📅 Data de Vencimento",
                                            value=p.get("data_vencimento"),
                                            format="DD/MM/YYYY",
                                        )
                                        cs1, cs2 = st.columns(2)
                                        with cs1:
                                            if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                                                try:
                                                    _db.atualizar_projeto(p["id"], ep_nome, ep_desc, ep_status,
                                                                          ep_unid, ep_depto, ep_sub, ep_tipo,
                                                                          data_vencimento=ep_venc or None)
                                                    st.session_state.edit_proj = None
                                                    st.session_state.df = None  # força recarga com novo nome
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(str(e))
                                        with cs2:
                                            if st.form_submit_button("✖ Cancelar", use_container_width=True):
                                                st.session_state.edit_proj = None
                                                st.rerun()
                                else:
                                    with st.container(border=True):
                                        pc1, pc2 = st.columns([5, 1])
                                        with pc1:
                                            st.markdown(f"**{p['nome']}** &nbsp; {BADGE.get(p['status'], '')} *{p['status']}*",
                                                        unsafe_allow_html=True)
                                            meta = []
                                            if p.get("unidade"):       meta.append(f"🏥 {p['unidade']}")
                                            if p.get("departamento"):  meta.append(f"🏢 {p['departamento']}")
                                            if p.get("subarea"):       meta.append(f"📂 {p['subarea']}")
                                            if p.get("tipo_projeto"):  meta.append(f"🏷️ {p['tipo_projeto']}")
                                            if p.get("data_vencimento"):
                                                import datetime as _dt_venc
                                                _vd = p["data_vencimento"]
                                                _vd_str = _vd.strftime("%d/%m/%Y") if hasattr(_vd, "strftime") else str(_vd)
                                                _hoje = _dt_venc.date.today()
                                                _vd_date = _vd if hasattr(_vd, "year") else _dt_venc.date.fromisoformat(str(_vd))
                                                _vd_icon = "🔴" if _vd_date < _hoje else ("🟡" if (_vd_date - _hoje).days <= 30 else "🟢")
                                                meta.append(f"{_vd_icon} Vence {_vd_str}")
                                            if meta:
                                                st.caption("  ·  ".join(meta))
                                            if p.get("descricao"):
                                                st.caption(p["descricao"][:100])
                                        with pc2:
                                            if st.button("✏️", key=f"ep_{p['id']}", help="Editar"):
                                                st.session_state.edit_proj = p["id"]
                                                st.rerun()
                                            if st.button("🗑️", key=f"dp_{p['id']}", help="Excluir"):
                                                _db.deletar_projeto(p["id"])
                                                st.rerun()
                        else:
                            st.info("Nenhum projeto cadastrado.")
                    except Exception as e:
                        st.error(str(e))

            # ── Atividades ────────────────────────────────────────────────────
            with sub_atv:
                try:
                    projs_db  = _db.listar_projetos()
                    proj_opts = {p["nome"]: p["id"] for p in projs_db}
                except Exception:
                    proj_opts = {}

                af1, af2 = st.columns([1, 2])
                with af1:
                    st.markdown("**Nova Atividade**")
                    if not proj_opts:
                        st.info("Cadastre um projeto primeiro.")
                    else:
                        with st.form("form_atividade", clear_on_submit=True):
                            proj_sel = st.selectbox("Projeto *", list(proj_opts.keys()))
                            nome_a   = st.text_input("Atividade *", placeholder="Ex: Construção do dashboard")
                            ordem_a  = st.number_input("Ordem (1ª, 2ª, 3ª…)", 0, 999, 0, step=1,
                                                        help="Define a sequência: 1 = primeira atividade do projeto")
                            resp_a   = st.selectbox("Responsável", pessoas if pessoas else [""])
                            horas_a  = st.number_input(
                                "⏱️ Total de horas da atividade", 0.0, 9999.0, step=0.5,
                                help="Horas TOTAIS para toda a atividade. Serão divididas igualmente pelo número de semanas do período.",
                            )
                            dc1, dc2 = st.columns(2)
                            with dc1: dt_ini = st.date_input("Início", format="DD/MM/YYYY")
                            with dc2: dt_fim = st.date_input("Término", format="DD/MM/YYYY")
                            if horas_a > 0 and dt_fim >= dt_ini:
                                _n_sem_prev = max(1, ((dt_fim - dt_ini).days // 7) + 1)
                                _hpw_prev   = horas_a / _n_sem_prev
                                st.caption(f"📊 {horas_a:.0f}h ÷ {_n_sem_prev} semana(s) = **{_hpw_prev:.1f} h/semana** no heatmap")
                            if st.form_submit_button("➕ Salvar Atividade", type="primary"):
                                if nome_a.strip():
                                    try:
                                        _db.inserir_atividade(
                                            proj_opts[proj_sel], nome_a, resp_a,
                                            horas_a, dt_ini, dt_fim, int(ordem_a),
                                        )
                                        st.success("Atividade salva!")
                                        st.session_state.df = None
                                        st.rerun()
                                    except Exception as e:
                                        st.error(str(e))
                                else:
                                    st.warning("Informe o nome.")
                        # Alerta de conflito fora do form (lê ferias do session_state atual)
                        _ferias_now = st.session_state.get("ferias", {})
                        if _ferias_now:
                            import datetime as _dt
                            _ini_chk = _dt.date.today()
                            _fim_chk = _dt.date.today()
                            # Mostra preview de conflito ainda sem salvar
                            _conf_prev = []
                            if pessoas:
                                _conf_prev = _db.checar_conflito_atividade(
                                    _ferias_now, pessoas[0], _ini_chk, _fim_chk
                                )
                            # Aviso geral de conflitos já existentes por projeto
                            try:
                                _ativs_all = _db.listar_atividades(proj_opts.get(proj_opts and list(proj_opts.keys())[0]))
                                _conflicts = _db.checar_conflitos_ferias(_ferias_now, _ativs_all)
                                if _conflicts:
                                    with st.expander(f"⚠️ {len(_conflicts)} conflito(s) de férias neste projeto", expanded=False):
                                        for _c in _conflicts:
                                            st.warning(
                                                f"**{_c['atividade']}** — {_c['responsavel']}\n\n"
                                                f"Semanas em conflito: {', '.join(_c['semanas_conflito'])}"
                                            )
                            except Exception:
                                pass

                with af2:
                    st.markdown("**Atividades por Projeto**")
                    if proj_opts:
                        _av_c1, _av_c2 = st.columns([3, 2])
                        with _av_c1:
                            proj_view = st.selectbox(
                                "Selecionar projeto:", list(proj_opts.keys()),
                                key="av_sel", label_visibility="collapsed",
                            )
                        with _av_c2:
                            if st.button("🔢 Reordenar", help="Reclassifica a ordem de todas as atividades do projeto pela data de início", use_container_width=True):
                                try:
                                    _n = _db.reordenar_atividades_por_data()
                                    st.success(f"{_n} atividade(s) reordenadas!")
                                    st.session_state.df = None
                                    st.rerun()
                                except Exception as _e:
                                    st.error(str(_e))

                        try:
                            ativs = _db.listar_atividades(proj_opts[proj_view])
                            if ativs:
                                for atv in ativs:
                                    ordem_label = f"{int(atv.get('ordem') or 0):02d}. " if atv.get("ordem") else ""
                                    if st.session_state.edit_atv == atv["id"]:
                                        with st.form(f"edit_a_{atv['id']}"):
                                            ea_nome  = st.text_input("Nome", value=atv["nome"])
                                            ea_ordem = st.number_input("Ordem", 0, 999,
                                                                        int(atv.get("ordem") or 0))
                                            ea_resp  = st.selectbox("Responsável",
                                                                     pessoas if pessoas else [""],
                                                                     index=(pessoas.index(atv["responsavel"])
                                                                            if atv.get("responsavel") in pessoas else 0))
                                            ea_h     = st.number_input(
                                                "⏱️ Total de horas", 0.0, 9999.0,
                                                float(atv.get("horas_estimadas") or 0), step=0.5,
                                                help="Horas TOTAIS da atividade — divididas pelo nº de semanas",
                                            )
                                            ea_ini   = st.date_input("Início", value=atv.get("semana_inicio"), format="DD/MM/YYYY")
                                            ea_fim   = st.date_input("Término", value=atv.get("semana_fim"), format="DD/MM/YYYY")
                                            if ea_h > 0 and atv.get("semana_inicio") and atv.get("semana_fim"):
                                                _nsem_ed = max(1, ((ea_fim - ea_ini).days // 7) + 1)
                                                st.caption(f"📊 ≈ **{ea_h / _nsem_ed:.1f} h/semana** ({_nsem_ed} sem.)")
                                            elif ea_h > 0:
                                                st.caption("📊 Defina início e término para ver h/semana")
                                            as1, as2 = st.columns(2)
                                            with as1:
                                                if st.form_submit_button("💾 Salvar", type="primary"):
                                                    try:
                                                        _db.atualizar_atividade(
                                                            atv["id"], ea_nome, ea_resp, ea_h,
                                                            ea_ini, ea_fim, ea_ordem,
                                                        )
                                                        # Checa conflito logo após salvar
                                                        _ferias_edit = st.session_state.get("ferias", {})
                                                        _conf_edit = _db.checar_conflito_atividade(
                                                            _ferias_edit, ea_resp, ea_ini, ea_fim
                                                        )
                                                        if _conf_edit:
                                                            st.warning(
                                                                f"⚠️ Férias de **{ea_resp}** nas semanas: "
                                                                + ", ".join(_conf_edit)
                                                            )
                                                        st.session_state.edit_atv = None
                                                        st.session_state.df = None
                                                        st.rerun()
                                                    except Exception as e:
                                                        st.error(str(e))
                                            with as2:
                                                if st.form_submit_button("✖ Cancelar"):
                                                    st.session_state.edit_atv = None
                                                    st.rerun()
                                    else:
                                        ac1, ac2, ac3, ac4, ac5 = st.columns([0.5, 2.5, 1.5, 1, 0.5])
                                        with ac1:
                                            st.caption(f"#{int(atv.get('ordem') or 0):02d}")
                                        with ac2:
                                            st.write(atv["nome"])
                                        with ac3:
                                            st.caption(atv.get("responsavel") or "—")
                                        with ac4:
                                            h = float(atv.get("horas_estimadas") or 0)
                                            st.caption(_fh(h))
                                        with ac5:
                                            bc1, bc2 = st.columns(2)
                                            with bc1:
                                                if st.button("✏️", key=f"ea_{atv['id']}", help="Editar"):
                                                    st.session_state.edit_atv = atv["id"]
                                                    st.rerun()
                                            with bc2:
                                                if st.button("🗑️", key=f"da_{atv['id']}", help="Excluir"):
                                                    _db.deletar_atividade(atv["id"])
                                                    st.session_state.df = None
                                                    st.rerun()
                            else:
                                st.info("Nenhuma atividade para este projeto.")
                        except Exception as e:
                            st.error(str(e))

            # ── Responsáveis ──────────────────────────────────────────────────
            with sub_resp:
                rf1, rf2 = st.columns([1, 2])
                with rf1:
                    st.markdown("**Novo Responsável**")
                    with st.form("form_resp", clear_on_submit=True):
                        nome_r  = st.text_input("Nome *")
                        email_r = st.text_input("E-mail")
                        cap_r   = st.number_input("Capacidade (h/sem)", 1, 80, 36)
                        if st.form_submit_button("➕ Salvar", type="primary"):
                            if nome_r.strip():
                                try:
                                    _db.inserir_responsavel(nome_r, email_r, cap_r)
                                    st.success("Responsável salvo!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                            else:
                                st.warning("Informe o nome.")
                with rf2:
                    st.markdown("**Equipe Cadastrada**")
                    try:
                        resps = _db.listar_responsaveis()
                        if resps:
                            for r in resps:
                                if st.session_state.edit_resp == r["id"]:
                                    with st.form(f"edit_r_{r['id']}"):
                                        er_nome  = st.text_input("Nome", value=r["nome"])
                                        er_email = st.text_input("E-mail", value=r.get("email", ""))
                                        er_cap   = st.number_input("Capacidade (h/sem)", 1, 80,
                                                                    int(r.get("capacidade_semanal", 36)))
                                        rs1, rs2 = st.columns(2)
                                        with rs1:
                                            if st.form_submit_button("💾 Salvar", type="primary"):
                                                try:
                                                    _db.atualizar_responsavel(r["id"], er_nome, er_email, er_cap)
                                                    st.session_state.edit_resp = None
                                                    # Força recarga completa: nome pode ter mudado
                                                    # em atividades, férias e capacidade
                                                    st.session_state.df = None
                                                    st.session_state.capacidade = {}
                                                    st.session_state.ferias = {}
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(str(e))
                                        with rs2:
                                            if st.form_submit_button("✖ Cancelar"):
                                                st.session_state.edit_resp = None
                                                st.rerun()
                                else:
                                    rc1, rc2, rc3, rc4, rc5 = st.columns([2, 2, 1, 0.5, 0.5])
                                    with rc1: st.write(f"**{r['nome']}**")
                                    with rc2: st.caption(r.get("email") or "—")
                                    with rc3: st.caption(f"{_fh(r['capacidade_semanal'])}/sem")
                                    with rc4:
                                        if st.button("✏️", key=f"er_{r['id']}", help="Editar"):
                                            st.session_state.edit_resp = r["id"]
                                            st.rerun()
                                    with rc5:
                                        if st.button("🗑️", key=f"dr_{r['id']}", help="Excluir"):
                                            _db.deletar_responsavel(r["id"])
                                            st.rerun()
                        else:
                            st.info("Nenhum responsável cadastrado.")
                    except Exception as e:
                        st.error(str(e))

                # ── Reconciliação de nomes órfãos ──────────────────────────
                st.markdown("---")
                try:
                    _orfaos = _db.listar_nomes_orfaos()
                    if _orfaos:
                        st.warning(
                            f"⚠️ **{len(_orfaos)} nome(s) antigo(s) detectado(s)** em atividades/férias "
                            "que não correspondem a nenhum responsável cadastrado. Corrija abaixo:"
                        )
                        _nomes_validos = [r["nome"] for r in _db.listar_responsaveis()]
                        for _orf in _orfaos:
                            with st.container(border=True):
                                _oc1, _oc2, _oc3 = st.columns([2, 2, 1])
                                with _oc1:
                                    st.markdown(
                                        f"**'{_orf['nome']}'** usado em: "
                                        + ", ".join(f"*{o}*" for o in _orf["origens"])
                                    )
                                with _oc2:
                                    _novo = st.selectbox(
                                        "Mapear para:",
                                        options=_nomes_validos,
                                        key=f"rec_{_orf['nome']}",
                                    )
                                with _oc3:
                                    if st.button(
                                        "✅ Corrigir",
                                        key=f"fix_{_orf['nome']}",
                                        type="primary",
                                        use_container_width=True,
                                    ):
                                        try:
                                            _db.substituir_nome_responsavel(_orf["nome"], _novo)
                                            st.session_state.df = None
                                            st.session_state.capacidade = {}
                                            st.session_state.ferias = {}
                                            st.success(f"'{_orf['nome']}' → '{_novo}' corrigido!")
                                            st.rerun()
                                        except Exception as _re:
                                            st.error(str(_re))
                    else:
                        st.success("✅ Todos os nomes em atividades e férias estão sincronizados com os responsáveis cadastrados.")
                except Exception as _oe:
                    st.error(str(_oe))

                # ── Reatribuição por projeto ───────────────────────────────
                with st.expander("🔧 Reatribuir atividades por projeto (correção avançada)", expanded=False):
                    st.caption(
                        "Use quando atividades de uma pessoa foram atribuídas por engano a outra. "
                        "Selecione os projetos afetados para mover apenas as atividades corretas."
                    )
                    try:
                        _all_resps  = [r["nome"] for r in _db.listar_responsaveis()]
                        _all_projs  = _db.listar_projetos()
                        _proj_map   = {p["nome"]: p["id"] for p in _all_projs}

                        _ra1, _ra2 = st.columns(2)
                        with _ra1:
                            _de  = st.selectbox("De (nome atual incorreto):", _all_resps, key="re_de")
                        with _ra2:
                            _para = st.selectbox("Para (nome correto):", _all_resps, key="re_para")

                        # Mostra apenas projetos onde "_de" tem atividades
                        try:
                            _ativs_de = _db.listar_atividades()
                            _projs_com_de = sorted({a["projeto_nome"] for a in _ativs_de if a.get("responsavel") == _de})
                        except Exception:
                            _projs_com_de = list(_proj_map.keys())

                        if _projs_com_de:
                            _proj_sel = st.multiselect(
                                f"Projetos para reatribuir ('{_de}' aparece em {len(_projs_com_de)}):",
                                options=_projs_com_de,
                                default=_projs_com_de,
                                key="re_projs",
                            )
                            _ids_sel = [_proj_map[p] for p in _proj_sel if p in _proj_map]
                            _n_prev  = sum(1 for a in _ativs_de
                                          if a.get("responsavel") == _de
                                          and a.get("projeto_nome") in _proj_sel)
                            st.info(f"**{_n_prev} atividade(s)** serão movidas de **'{_de}'** → **'{_para}'**")
                            if _de != _para and st.button("✅ Confirmar reatribuição", type="primary",
                                                          key="re_confirm", use_container_width=True):
                                try:
                                    _moved = _db.reatribuir_por_projeto(_de, _para, _ids_sel)
                                    st.session_state.df = None
                                    st.session_state.capacidade = {}
                                    st.session_state.ferias = {}
                                    st.success(f"✅ {_moved} atividade(s) reatribuídas de '{_de}' → '{_para}'!")
                                    st.rerun()
                                except Exception as _re:
                                    st.error(str(_re))
                        else:
                            st.info(f"Nenhuma atividade encontrada para '{_de}'.")
                    except Exception as _re2:
                        st.error(str(_re2))

            # ── Férias ────────────────────────────────────────────────────────
            with sub_fer:
                st.markdown("**Registrar Período de Férias**")
                try:
                    _resp_opts = [r["nome"] for r in _db.listar_responsaveis()]
                except Exception:
                    _resp_opts = pessoas

                ff1, ff2 = st.columns([1, 2])
                with ff1:
                    if not _resp_opts:
                        st.info("Cadastre um responsável primeiro.")
                    else:
                        with st.form("form_ferias", clear_on_submit=True):
                            fer_resp = st.selectbox("Responsável *", _resp_opts)
                            fd1, fd2 = st.columns(2)
                            with fd1:
                                fer_ini = st.date_input("Início *", format="DD/MM/YYYY")
                            with fd2:
                                fer_fim = st.date_input("Término *", format="DD/MM/YYYY")
                            if st.form_submit_button("➕ Registrar Férias", type="primary", use_container_width=True):
                                if fer_fim < fer_ini:
                                    st.warning("A data de término deve ser igual ou posterior ao início.")
                                else:
                                    try:
                                        _db.inserir_ferias(fer_resp, fer_ini, fer_fim)
                                        st.success(f"Férias de **{fer_resp}** registradas!")
                                        # Atualiza ferias no session_state
                                        st.session_state.ferias = _db.carregar_ferias_como_dict()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(str(e))

                with ff2:
                    st.markdown("**Férias Cadastradas**")
                    try:
                        _fer_list = _db.listar_ferias()
                        if _fer_list:
                            # Verifica conflitos globais
                            _all_ativs = _db.listar_atividades()
                            _ferias_dict = st.session_state.get("ferias", {})
                            _conflitos_all = _db.checar_conflitos_ferias(_ferias_dict, _all_ativs)
                            _conflito_keys = {
                                (c["responsavel"], c["atividade"]) for c in _conflitos_all
                            }

                            for fer in _fer_list:
                                ini_str = fer["data_inicio"].strftime("%d/%m/%Y") if hasattr(fer["data_inicio"], "strftime") else str(fer["data_inicio"])
                                fim_str = fer["data_fim"].strftime("%d/%m/%Y")    if hasattr(fer["data_fim"],    "strftime") else str(fer["data_fim"])
                                # Conflitos para este responsável
                                _conf_fer = [
                                    c for c in _conflitos_all
                                    if c["responsavel"] == fer["responsavel"]
                                ]
                                with st.container(border=True):
                                    fc1, fc2 = st.columns([5, 1])
                                    with fc1:
                                        st.markdown(
                                            f"🏖️ **{fer['responsavel']}** &nbsp; "
                                            f"`{ini_str}` → `{fim_str}`",
                                            unsafe_allow_html=True,
                                        )
                                        if _conf_fer:
                                            for _c in _conf_fer:
                                                st.warning(
                                                    f"⚠️ Conflito com **{_c['atividade']}** "
                                                    f"({_c['projeto']}) — semanas: "
                                                    + ", ".join(_c["semanas_conflito"])
                                                )
                                    with fc2:
                                        if st.button("🗑️", key=f"df_{fer['id']}", help="Excluir"):
                                            _db.deletar_ferias(fer["id"])
                                            st.session_state.ferias = _db.carregar_ferias_como_dict()
                                            st.rerun()
                        else:
                            st.info("Nenhum período de férias cadastrado.")
                    except Exception as e:
                        st.error(str(e))

# ═══ IA GESTÃO ═════════════════════════════════════════════════════════════════
with tab_ia:
    from utils import ai as _ai

    st.markdown('<p class="section-title">🤖 Gestão Inteligente com IA</p>', unsafe_allow_html=True)

    if not _ai.is_configured():
        st.warning(
            "⚠️ **Nenhuma chave de IA configurada.** Adicione em `.streamlit/secrets.toml`:\n\n"
            "```toml\n# Groq (gratuito) — https://console.groq.com/keys\n"
            "AI_PROVIDER = \"groq\"\nGROQ_API_KEY = \"gsk_...\"\n\n"
            "# OU Gemini — https://aistudio.google.com/apikey\n"
            "AI_PROVIDER = \"gemini\"\nGEMINI_API_KEY = \"AIza...\"\n```\n"
        )
        st.stop()

    # Monta contexto completo uma vez por execução
    @st.cache_data(ttl=30, show_spinner=False)
    def _build_ia_context(_df_hash, _cap_hash, _fer_hash):
        try:
            _ativs_all = _db.listar_atividades()
            return _ai.build_context(df, capacidade, ferias, _ativs_all)
        except Exception:
            return {"capacidade_semanal": {}, "ferias": {}, "carga_atual": [],
                    "sobrecargas": [], "atividades": []}

    _ia_ctx = _build_ia_context(
        str(id(df)),
        str(sorted(capacidade.items())),
        str(sorted(ferias.keys())),
    )

    ia_tab1, ia_tab2 = st.tabs([
        "🤖 Agente de Cronograma",
        "� Analista de Projeto",
    ])

    # ── Agente de Cronograma ───────────────────────────────────────────────────
    with ia_tab1:
        from utils import agente as _agente
        import json as _json

        st.markdown("**Converse com o agente para criar projetos, redistribuir atividades, detectar conflitos e reagendar.**")

        if "agente_estado" not in st.session_state:
            st.session_state["agente_estado"] = _agente.estado_inicial()
        if "agente_chat_history" not in st.session_state:
            st.session_state["agente_chat_history"] = []

        # Chips de ação rápida
        _chip_c1, _chip_c2, _chip_c3, _chip_c4 = st.columns(4)
        _chip_msg = None
        with _chip_c1:
            if st.button("🔍 Detectar conflitos", use_container_width=True, key="chip_conflitos"):
                _chip_msg = "Detecte todos os conflitos e sobrecargas no cronograma atual."
        with _chip_c2:
            if st.button("➕ Criar novo projeto", use_container_width=True, key="chip_criar"):
                # Vai direto para o formulário sem passar pelo router
                _novo_est = _agente.estado_inicial()
                _novo_est["intencao"] = "criar_projeto"
                _novo_est["fase"]     = "coletando"
                st.session_state["agente_estado"] = _novo_est
                st.rerun()
        with _chip_c3:
            if st.button("♻️ Ver sobrecargas", use_container_width=True, key="chip_sobrecargas"):
                _chip_msg = "Mostre as sobrecargas de cada pessoa no período atual."
        with _chip_c4:
            if st.button("📅 Sugerir reagendamento", use_container_width=True, key="chip_reagendar"):
                _chip_msg = "Sugira reagendamentos para equilibrar a carga de trabalho."

        # Exibe histórico
        for _amsg in st.session_state["agente_chat_history"]:
            with st.chat_message(_amsg["role"]):
                st.markdown(_amsg["content"])

        # ── Formulário de novo projeto (quando em modo coletando criar_projeto) ──
        _ag_est_now = st.session_state["agente_estado"]
        if _ag_est_now.get("intencao") == "criar_projeto" and _ag_est_now.get("fase") == "coletando":
            _dados_par = _ag_est_now.get("dados_coletados", {})
            _tipos_atv_opts = ["diagnostico", "dados", "predicoes", "dashboard",
                               "implantacao", "sustentacao", "expansao", "outros"]
            _unidades_opts  = sorted({v.get("unidade", "") for v in st.session_state.get("proj_meta", {}).values() if v.get("unidade")})
            if not _unidades_opts:
                _unidades_opts = ["CMC", "CMA", "HMVSC", "HOEB"]

            with st.container(border=True):
                st.markdown("#### 📁 Novo Projeto")
                with st.form("form_novo_projeto", border=False):
                    _fp_c1, _fp_c2 = st.columns([2, 1])
                    with _fp_c1:
                        _f_nome = st.text_input("Nome do projeto *",
                                                value=_dados_par.get("nome_projeto", ""),
                                                placeholder="Ex: Predição de risco de reinternação")
                    with _fp_c2:
                        _f_unidade = st.selectbox("Unidade", [""] + _unidades_opts,
                                                   index=0)
                    _fp_c3, _fp_c4 = st.columns([1, 1])
                    with _fp_c3:
                        import datetime as _dt_form
                        _f_prazo = st.date_input("Prazo de entrega *",
                                                  value=None,
                                                  format="DD/MM/YYYY",
                                                  min_value=_dt_form.date.today())
                    with _fp_c4:
                        _f_depto = st.text_input("Departamento (opcional)",
                                                  value=_dados_par.get("departamento", ""),
                                                  placeholder="Ex: Oncologia")

                    st.markdown("**Atividades do projeto** — adicione todas as fases:")
                    _atv_default = pd.DataFrame([
                        {"Tipo": "diagnostico",  "Nome da Atividade": "Diagnóstico e Entendimento",      "Responsável": "", "Horas": 30},
                        {"Tipo": "dados",        "Nome da Atividade": "Estruturação e Curadoria de Dados","Responsável": "", "Horas": 40},
                        {"Tipo": "predicoes",    "Nome da Atividade": "Modelagem Preditiva",              "Responsável": "", "Horas": 80},
                        {"Tipo": "dashboard",    "Nome da Atividade": "Dashboard e Visualização",         "Responsável": "", "Horas": 60},
                        {"Tipo": "implantacao",  "Nome da Atividade": "Implantação e Go-Live",            "Responsável": "", "Horas": 20},
                    ])
                    _f_ativs = st.data_editor(
                        _atv_default,
                        column_config={
                            "Tipo": st.column_config.SelectboxColumn(
                                "Tipo", options=_tipos_atv_opts, required=True),
                            "Nome da Atividade": st.column_config.TextColumn(
                                "Nome da Atividade", required=True),
                            "Responsável": st.column_config.SelectboxColumn(
                                "Responsável", options=[""] + (pessoas or []), required=True),
                            "Horas": st.column_config.NumberColumn(
                                "Horas", min_value=1, max_value=2000, format="%d h"),
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        key="form_ativs_editor",
                    )

                    _fs_c1, _fs_c2 = st.columns([3, 1])
                    with _fs_c1:
                        _f_submit = st.form_submit_button(
                            "🤖 Gerar plano com IA", type="primary", use_container_width=True)
                    with _fs_c2:
                        _f_cancel_placeholder = st.form_submit_button(
                            "✖ Cancelar", use_container_width=True)

                    if _f_cancel_placeholder:
                        st.session_state["agente_estado"] = _agente.estado_inicial()
                        st.rerun()

                    if _f_submit:
                        _f_erros = []
                        if not _f_nome.strip():
                            _f_erros.append("Nome do projeto é obrigatório.")
                        if not _f_prazo:
                            _f_erros.append("Prazo de entrega é obrigatório.")
                        _f_ativs_validas = _f_ativs[
                            _f_ativs["Responsável"].notna() & (_f_ativs["Responsável"] != "") &
                            _f_ativs["Nome da Atividade"].notna() & (_f_ativs["Nome da Atividade"] != "")
                        ]
                        if _f_ativs_validas.empty:
                            _f_erros.append("Adicione ao menos uma atividade com nome e responsável.")
                        if _f_erros:
                            for _fe in _f_erros:
                                st.error(_fe)
                        else:
                            _dados_form = {
                                "nome_projeto":    _f_nome.strip(),
                                "data_vencimento": _f_prazo.strftime("%Y-%m-%d"),
                                "unidade":         _f_unidade,
                                "departamento":    _f_depto.strip(),
                                "atividades": [
                                    {
                                        "nome":             row["Nome da Atividade"],
                                        "tipo":             row["Tipo"],
                                        "responsavel":      row["Responsável"],
                                        "horas_estimadas":  int(row["Horas"]),
                                    }
                                    for _, row in _f_ativs_validas.iterrows()
                                ],
                            }
                            _ag_ctx = {
                                "df": df, "capacidade": capacidade,
                                "ferias": ferias, "responsaveis": pessoas,
                                "projetos_meta": st.session_state.get("proj_meta", {}),
                                "atividades_list": [],
                            }
                            _msg_form = f"Criar projeto '{_f_nome.strip()}' vencendo em {_f_prazo.strftime('%d/%m/%Y')}."
                            with st.spinner("🤖 Gerando plano com IA..."):
                                try:
                                    _ag_result = _agente.criar_projeto_do_formulario(
                                        _dados_form,
                                        st.session_state["agente_chat_history"],
                                        st.session_state["agente_estado"],
                                        _ag_ctx,
                                    )
                                    _ag_resposta = _ag_result["resposta_texto"]
                                    _ag_estado   = _ag_result["estado"]
                                except Exception as _age:
                                    _ag_resposta = f"❌ Erro ao gerar plano: {_age}"
                                    _ag_estado   = _agente.estado_inicial()
                            _ag_hist = st.session_state["agente_chat_history"]
                            _ag_hist.append({"role": "user",      "content": _msg_form})
                            _ag_hist.append({"role": "assistant",  "content": _ag_resposta})
                            st.session_state["agente_chat_history"] = _ag_hist
                            st.session_state["agente_estado"]       = _ag_estado
                            st.rerun()

        else:
            # ── Chat normal (detectar conflitos, redistribuir, consultar) ─────
            _agente_input = st.chat_input(
                "Ex: Detectar conflitos | Ver sobrecargas | Redistribuir atividades de Daniel",
                key="agente_chat_input",
            )
            _user_msg = _agente_input or _chip_msg
            if _user_msg:
                _ag_history = st.session_state["agente_chat_history"]
                _ag_estado  = st.session_state["agente_estado"]
                _ag_ctx = {
                    "df": df, "capacidade": capacidade,
                    "ferias": ferias, "responsaveis": pessoas,
                    "projetos_meta": st.session_state.get("proj_meta", {}),
                    "atividades_list": [],
                }
                with st.chat_message("user"):
                    st.markdown(_user_msg)
                with st.chat_message("assistant"):
                    with st.spinner("Agente analisando..."):
                        try:
                            _ag_result   = _agente.processar_mensagem(_user_msg, _ag_history, _ag_estado, _ag_ctx)
                            _ag_resposta = _ag_result["resposta_texto"]
                            _ag_estado   = _ag_result["estado"]
                        except Exception as _age:
                            _ag_resposta = f"❌ Erro no agente: {_age}"
                            _ag_estado   = st.session_state["agente_estado"]
                    st.markdown(_ag_resposta)
                _ag_history.append({"role": "user",      "content": _user_msg})
                _ag_history.append({"role": "assistant",  "content": _ag_resposta})
                st.session_state["agente_chat_history"] = _ag_history
                st.session_state["agente_estado"]       = _ag_estado

        # Plano pendente de aplicação
        _ag_plano = st.session_state["agente_estado"].get("plano_proposto")
        if _ag_plano:
            with st.container(border=True):
                if _ag_plano.get("tipo") == "mudancas":
                    _chg = _ag_plano.get("changes", [])
                    st.caption(f"📋 **{len(_chg)} mudança(s) prontas para aplicar:**")
                    _chg_rows = [
                        {"Atividade": c.get("atv_nome", c.get("nome", "?")),
                         "Responsável Novo": c.get("responsavel_novo", c.get("novo_responsavel", "—")),
                         "Motivo": c.get("motivo", "")}
                        for c in _chg
                    ]
                    st.dataframe(pd.DataFrame(_chg_rows), use_container_width=True, hide_index=True)
                elif _ag_plano.get("tipo") == "criar_projeto":
                    _pinfo = _ag_plano.get("projeto", {})
                    _ainfo = _ag_plano.get("atividades", [])
                    st.caption(f"📋 **Novo projeto: {_pinfo.get('nome', '?')} — {len(_ainfo)} atividade(s)**")
                    if _ainfo:
                        _atv_rows = [
                            {
                                "Atividade": a.get("nome"),
                                "Responsável": a.get("responsavel"),
                                "Horas": a.get("horas_estimadas", ""),
                                "Início": a["semana_inicio"].strftime("%d/%m/%Y") if a.get("semana_inicio") else "—",
                                "Fim":    a["semana_fim"].strftime("%d/%m/%Y") if a.get("semana_fim") else "—",
                                "Status": "⚠️ Estouro" if a.get("status_prazo") == "estouro" else "✅ OK",
                            }
                            for a in _ainfo
                        ]
                        st.dataframe(pd.DataFrame(_atv_rows), use_container_width=True, hide_index=True)

                    # ── Impacto por responsável ───────────────────────────────
                    from collections import defaultdict as _ddict
                    from datetime import timedelta as _td
                    _imp = _ddict(lambda: {"horas": 0.0, "semanas": set()})
                    for _a in _ainfo:
                        _rsp = _a.get("responsavel", "")
                        if not _rsp:
                            continue
                        _imp[_rsp]["horas"] += float(_a.get("horas_estimadas") or 0)
                        _si = _a.get("semana_inicio")
                        _sf = _a.get("semana_fim")
                        if _si and _sf:
                            _wd = _si
                            while _wd <= _sf:
                                _imp[_rsp]["semanas"].add(_wd)
                                _wd += _td(weeks=1)

                    _imp_rows = []
                    for _rsp, _info in _imp.items():
                        _cap_sem = capacidade.get(_rsp, 36)
                        _n_sem   = max(len(_info["semanas"]), 1)
                        _cap_per = _cap_sem * _n_sem
                        _carga_atual = 0.0
                        if df is not None and not df.empty and _info["semanas"]:
                            import pandas as _pd2
                            _datas = {_pd2.Timestamp(s) for s in _info["semanas"]}
                            _mask  = (df["Responsável"] == _rsp) & (df["Semana"].isin(_datas))
                            _carga_atual = float(df[_mask]["Horas"].sum())
                        _livre  = max(0.0, _cap_per - _carga_atual)
                        _novo   = _info["horas"]
                        _status = "🟢 OK" if _carga_atual + _novo <= _cap_per else "🔴 Sobrecarga"
                        _pct    = min(100, int((_carga_atual + _novo) / _cap_per * 100)) if _cap_per else 0
                        _imp_rows.append({
                            "Responsável":        _rsp,
                            "Cap. disponível (h)": int(_livre),
                            "Horas no projeto":   int(_novo),
                            "Saldo após (h)":     int(_livre - _novo),
                            "Uso no período":     f"{_pct}%",
                            "Status":             _status,
                        })

                    if _imp_rows:
                        st.markdown("**👤 Situação dos responsáveis no período do projeto:**")
                        st.dataframe(pd.DataFrame(_imp_rows), use_container_width=True, hide_index=True)

                    # ── Melhor período disponível por atividade ───────────────
                    import datetime as _dt_bp
                    _mon_fn = lambda _d_: _d_ - _dt_bp.timedelta(days=_d_.weekday())

                    # Horas já usadas por (responsável, semana) no banco atual
                    _used_rsp = {}
                    if df is not None and not df.empty:
                        for _, _ru in df.iterrows():
                            _rk = _ru["Responsável"]
                            _sw = _ru["Semana"]
                            _sw = _mon_fn(_sw.date() if hasattr(_sw, "date") else _sw)
                            _used_rsp.setdefault(_rk, {})
                            _used_rsp[_rk][_sw] = _used_rsp[_rk].get(_sw, 0.0) + float(_ru["Horas"])

                    # Semanas de férias por responsável
                    _fer_set = {}
                    for _kf, _vf in ferias.items():
                        _fer_set[_kf] = set()
                        for _fv in _vf:
                            try:
                                _fv_d = _fv.date() if hasattr(_fv, "date") else _fv
                                _fer_set[_kf].add(_mon_fn(_fv_d))
                            except Exception:
                                pass

                    # Nível sequencial por tipo — atividades do mesmo nível
                    # só podem começar após o fim de TODAS do nível anterior.
                    _TIPO_LVL = {
                        "diagnostico": 1,
                        "dados": 2,
                        "predicoes": 3, "dashboard": 3,
                        "implantacao": 4,
                        "sustentacao": 5, "expansao": 5, "outros": 5,
                    }
                    _hoje_mon = _mon_fn(_dt_bp.date.today())

                    # Data de vencimento do projeto (deadline)
                    _vd_proj = None
                    _vd_str  = _pinfo.get("data_vencimento", "")
                    if _vd_str:
                        try:
                            _vd_proj = _dt_bp.datetime.strptime(_vd_str, "%Y-%m-%d").date()
                        except Exception:
                            pass

                    # Horizonte de varredura: até vencimento + 8 semanas
                    _scan_end = (
                        (_vd_proj + _dt_bp.timedelta(weeks=8)) if _vd_proj
                        else (_hoje_mon + _dt_bp.timedelta(weeks=78))
                    )
                    _all_weeks = []
                    _dw = _hoje_mon
                    while _dw <= _scan_end:
                        _all_weeks.append(_dw)
                        _dw += _dt_bp.timedelta(weeks=1)

                    # Pré-computa horas livres/semana por pessoa
                    _free_cap: dict = {}
                    for _rsp_u in {_a.get("responsavel", "") for _a in _ainfo}:
                        if not _rsp_u:
                            continue
                        _cap_u = float(capacidade.get(_rsp_u, 36))
                        _ur_u  = _used_rsp.get(_rsp_u, {})
                        _fr_u  = _fer_set.get(_rsp_u, set())
                        _free_cap[_rsp_u] = {
                            _w: (0.0 if _w in _fr_u else max(0.0, _cap_u - _ur_u.get(_w, 0.0)))
                            for _w in _all_weeks
                        }

                    def _best_window(rsp, hh, earliest, deadline=None):
                        """
                        Retorna (si, sf) da janela que cobre 'hh' horas com menor span
                        de calendário, começando em >= earliest.
                        Penaliza janelas que terminam após o deadline (soft constraint).
                        """
                        fw    = _free_cap.get(rsp, {})
                        weeks = [w for w in _all_weeks if w >= earliest]
                        bsi = bsf = None
                        bspan = 10 ** 9
                        for _si_i, _si_w in enumerate(weeks):
                            _acc = 0.0
                            for _sf_w in weeks[_si_i:]:
                                _acc += fw.get(_sf_w, 0.0)
                                if _acc >= hh:
                                    _span = (_sf_w - _si_w).days
                                    # Penalidade suave: prefere janelas dentro do prazo
                                    if deadline and _sf_w > deadline:
                                        _span += 10000
                                    if _span < bspan:
                                        bspan = _span
                                        bsi, bsf = _si_w, _sf_w
                                    break
                        return bsi, bsf

                    # Ordena por nível de tipo, mantendo índice original
                    _ainfo_order = sorted(
                        range(len(_ainfo)),
                        key=lambda _i_: _TIPO_LVL.get(_ainfo[_i_].get("tipo", "outros"), 5),
                    )
                    _lvl_fim: dict = {}  # {nivel: última semana_fim calculada}
                    _ps_dict: dict = {}  # {orig_idx: entry}

                    for _pi in _ainfo_order:
                        _pa  = _ainfo[_pi]
                        _rr  = _pa.get("responsavel", "")
                        _hh  = float(_pa.get("horas_estimadas") or 40)
                        _cap = float(capacidade.get(_rr, 36))
                        if not _rr or _cap <= 0:
                            continue
                        _lvl = _TIPO_LVL.get(_pa.get("tipo", "outros"), 5)

                        # Início mais cedo = máx dos fins de todos os níveis anteriores
                        _pred_fim = max(
                            (_lvl_fim[_l] for _l in _lvl_fim if _l < _lvl),
                            default=None,
                        )
                        _earliest = (
                            (_pred_fim + _dt_bp.timedelta(weeks=1))
                            if _pred_fim else _hoje_mon
                        )
                        _earliest = max(_earliest, _hoje_mon)

                        # Melhor janela: menor span que cobre _hh, respeitando deadline
                        _si2, _sf2 = _best_window(_rr, _hh, _earliest, _vd_proj)

                        # Atualiza fim máximo do nível
                        if _sf2:
                            _lvl_fim[_lvl] = max(_lvl_fim.get(_lvl, _sf2), _sf2)

                        _orig_ini = _pa.get("semana_inicio")
                        if _orig_ini is not None and hasattr(_orig_ini, "date"):
                            _orig_ini = _orig_ini.date()
                        _mesma = (_si2 == _orig_ini) if (_si2 and _orig_ini) else True
                        _diff  = ""
                        if not _mesma and _si2 and _orig_ini:
                            _dd = (_si2 - _orig_ini).days
                            _diff = f"({'+' if _dd > 0 else ''}{_dd}d vs atual)"
                        _ps_dict[_pi] = {
                            "_idx": _pi, "_ini": _si2, "_fim": _sf2,
                            "_mesma": _mesma, "_diff": _diff,
                            "atv":   _pa.get("nome", ""),
                            "resp":  _rr,
                            "atual": (
                                f"{_orig_ini.strftime('%d/%m/%Y')} → "
                                f"{_pa['semana_fim'].strftime('%d/%m/%Y')}"
                            ) if _orig_ini and _pa.get("semana_fim") else "—",
                            "melhor": (
                                f"{_si2.strftime('%d/%m/%Y')} → {_sf2.strftime('%d/%m/%Y')}"
                            ) if _si2 else "—",
                        }

                    # Exibe na ordem original do plano
                    _ps_list = [_ps_dict[_i] for _i in range(len(_ainfo)) if _i in _ps_dict]

                    if _ps_list:
                        st.markdown("**📅 Melhor período disponível por atividade:**")
                        _ph = st.columns([3, 2, 3, 3, 1])
                        for _lbl, _col in zip(
                            ["Atividade", "Responsável", "Período atual", "Melhor período", ""],
                            _ph,
                        ):
                            _col.markdown(f"**{_lbl}**")
                        _any_diff = False
                        for _ps in _ps_list:
                            _pc = st.columns([3, 2, 3, 3, 1])
                            _pc[0].write(_ps["atv"])
                            _pc[1].write(_ps["resp"])
                            _pc[2].write(_ps["atual"])
                            if _ps["_mesma"]:
                                _pc[3].write(_ps["melhor"] + " ✅")
                                _pc[4].write("")
                            else:
                                _any_diff = True
                                _pc[3].write(f"{_ps['melhor']}  \n`{_ps['_diff']}`")
                                if _ps["_ini"] and _pc[4].button(
                                    "↺", key=f"swap_per_{_ps['_idx']}",
                                    help="Aplicar melhor período para esta atividade",
                                    use_container_width=True,
                                ):
                                    _np = {**st.session_state["agente_estado"]["plano_proposto"]}
                                    _na = [dict(_x_) for _x_ in _np["atividades"]]
                                    _na[_ps["_idx"]]["semana_inicio"] = _ps["_ini"]
                                    _na[_ps["_idx"]]["semana_fim"]    = _ps["_fim"]
                                    _vs = _np.get("projeto", {}).get("data_vencimento", "")
                                    if _vs:
                                        try:
                                            _vd = _dt_bp.datetime.strptime(_vs, "%Y-%m-%d").date()
                                            _na[_ps["_idx"]]["status_prazo"] = "ok" if _ps["_fim"] <= _vd else "estouro"
                                            _na[_ps["_idx"]]["folga_dias"] = (_vd - _ps["_fim"]).days
                                        except Exception:
                                            pass
                                    _np["atividades"] = _na
                                    _ne = dict(st.session_state["agente_estado"])
                                    _ne["plano_proposto"] = _np
                                    st.session_state["agente_estado"] = _ne
                                    st.rerun()

                        if _any_diff:
                            if st.button(
                                "↺ Aplicar todos os melhores períodos",
                                key="swap_all_periods",
                                use_container_width=True,
                            ):
                                _np = {**st.session_state["agente_estado"]["plano_proposto"]}
                                _na = [dict(_x_) for _x_ in _np["atividades"]]
                                _vs = _np.get("projeto", {}).get("data_vencimento", "")
                                _vd2 = None
                                if _vs:
                                    try:
                                        _vd2 = _dt_bp.datetime.strptime(_vs, "%Y-%m-%d").date()
                                    except Exception:
                                        pass
                                for _ps in _ps_list:
                                    if not _ps["_mesma"] and _ps["_ini"]:
                                        _na[_ps["_idx"]]["semana_inicio"] = _ps["_ini"]
                                        _na[_ps["_idx"]]["semana_fim"]    = _ps["_fim"]
                                        if _vd2:
                                            _na[_ps["_idx"]]["status_prazo"] = "ok" if _ps["_fim"] <= _vd2 else "estouro"
                                            _na[_ps["_idx"]]["folga_dias"] = (_vd2 - _ps["_fim"]).days
                                _np["atividades"] = _na
                                _ne = dict(st.session_state["agente_estado"])
                                _ne["plano_proposto"] = _np
                                st.session_state["agente_estado"] = _ne
                                st.rerun()

                _ap_c1, _ap_c2 = st.columns(2)
                with _ap_c1:
                    if st.button("✅ Aplicar plano", type="primary", key="agente_apply_btn", use_container_width=True):
                        try:
                            if _ag_plano.get("tipo") == "mudancas":
                                _agente.aplicar_mudancas(_ag_plano["changes"])
                            elif _ag_plano.get("tipo") == "criar_projeto":
                                _agente.criar_projeto_com_atividades(
                                    _ag_plano["projeto"],
                                    _ag_plano["atividades"],
                                    _ag_plano.get("ancora"),
                                    capacidade,
                                )
                            st.session_state["agente_estado"] = _agente.estado_inicial()
                            st.session_state.df = None
                            st.success("✅ Plano aplicado com sucesso!")
                            st.rerun()
                        except Exception as _agae:
                            st.error(f"Erro ao aplicar: {_agae}")
                with _ap_c2:
                    if st.button("✖ Cancelar plano", key="agente_cancel_btn", use_container_width=True):
                        st.session_state["agente_estado"] = _agente.estado_inicial()
                        st.rerun()

        if st.session_state["agente_chat_history"]:
            if st.button("🗑️ Limpar conversa", key="agente_chat_clear"):
                st.session_state["agente_chat_history"] = []
                st.session_state["agente_estado"] = _agente.estado_inicial()
                st.rerun()

    # ── Chat Livre ─────────────────────────────────────────────────────────────
    with ia_tab2:
        st.markdown("**Converse com a IA sobre o cronograma. Ela conhece todas as atividades, cargas e férias.**")

        # Exibe histórico
        for _msg in st.session_state.get("ia_chat_history", []):
            with st.chat_message(_msg["role"]):
                st.markdown(_msg["content"])

        # Input do usuário
        _user_input = st.chat_input(
            "Ex: Quem tem mais capacidade livre essa semana? | Quais projetos têm atraso?",
            key="ia_chat_input",
        )
        if _user_input:
            _history = st.session_state.get("ia_chat_history", [])
            with st.chat_message("user"):
                st.markdown(_user_input)
            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    try:
                        _resp = _ai.chat_livre(_ia_ctx, _history, _user_input)
                    except Exception as _ce:
                        _resp = f"❌ Erro ao consultar IA: {_ce}"
                st.markdown(_resp)
            _history.append({"role": "user",      "content": _user_input})
            _history.append({"role": "assistant",  "content": _resp})
            st.session_state["ia_chat_history"] = _history
            # Sem st.rerun() — evita tela branca; mensagens já renderizadas acima

        if st.session_state.get("ia_chat_history"):
            if st.button("🗑️ Limpar conversa", key="ia_chat_clear"):
                st.session_state["ia_chat_history"] = []
                st.rerun()
