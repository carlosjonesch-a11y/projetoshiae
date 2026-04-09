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
if st.session_state.df is None and _db_loader.is_configured():
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
            # Carrega capacidade da tabela responsaveis (persiste entre sessões)
            try:
                _resps_load = _db_loader.listar_responsaveis()
                _cap_db = {r["nome"]: int(r["capacidade_semanal"]) for r in _resps_load}
            except Exception:
                _cap_db = {}
            for p in pes_db:
                if p not in st.session_state.capacidade:
                    st.session_state.capacidade[p] = _cap_db.get(p, 36)
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
    tab_pess, tab_cap, tab_cad,
) = st.tabs([
    "🌡️ Ocupação", "📅 Gantt", "🏆 Projetos", "📈 Evolução",
    "👥 Pessoas",  "⚡ Capacidade", "🗄️ Cadastro",
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
        # captura clique
        _pts = []
        if _ev and hasattr(_ev, "selection") and _ev.selection:
            _pts = getattr(_ev.selection, "points", []) or []
        if _pts:
            _pt = _pts[0]
            st.session_state["hm_sel"] = {
                "pessoa":  _pt.get("y"),
                "x_label": _pt.get("x"),
            }

        # ── Painel de atividades da célula clicada ─────────────────────────
        _sel = st.session_state.get("hm_sel")
        if _sel and _sel.get("pessoa") and _sel.get("x_label"):
            _hm_pessoa  = _sel["pessoa"]
            _hm_x_label = _sel["x_label"]
            _hm_semana  = _label_to_sem.get(_hm_x_label)

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

            if _hm_semana:
                try:
                    from utils import db as _db_hm
                    _ativs_hm = _db_hm.listar_atividades_por_pessoa_semana(
                        _hm_pessoa, pd.Timestamp(_hm_semana).date()
                    )
                    if _ativs_hm:
                        for _atv in _ativs_hm:
                            with st.expander(
                                f"📌 **{_atv['projeto_nome']}** — {_atv['nome']}",
                                expanded=True,
                            ):
                                with st.form(f"hm_edit_{_atv['id']}"):
                                    _lc1, _lc2 = st.columns(2)
                                    with _lc1:
                                        _new_ini = st.date_input(
                                            "📅 Início", value=_atv["semana_inicio"],
                                            format="DD/MM/YYYY",
                                        )
                                    with _lc2:
                                        _new_fim = st.date_input(
                                            "📅 Término", value=_atv["semana_fim"],
                                            format="DD/MM/YYYY",
                                        )
                                    if st.form_submit_button(
                                        "💾 Salvar datas", type="primary", use_container_width=True
                                    ):
                                        try:
                                            _db_hm.atualizar_atividade(
                                                _atv["id"],
                                                _atv["nome"],
                                                _atv["responsavel"],
                                                float(_atv.get("horas_estimadas") or 0),
                                                _new_ini,
                                                _new_fim,
                                                int(_atv.get("ordem") or 0),
                                            )
                                            st.success("✅ Datas atualizadas!")
                                            st.rerun()
                                        except Exception as _e:
                                            st.error(str(_e))
                    else:
                        # fallback: mostrar do df (sem edição de datas)
                        _df_cell = df[
                            (df["Responsável"] == _hm_pessoa) & (df["Semana"] == _hm_semana)
                        ]
                        if not _df_cell.empty:
                            for _, _row in (
                                _df_cell.drop_duplicates(["Projeto", "Atividade"]).iterrows()
                            ):
                                st.info(
                                    f"📌 **{_row['Projeto']}** — {_row['Atividade']} "
                                    f"({_fh(_row['Horas'])})"
                                    "\n\n_Atividade não cadastrada no banco — edição de datas indisponível._"
                                )
                        else:
                            st.info("Nenhuma atividade encontrada para esta célula.")
                except Exception as _exc:
                    _df_cell = df[
                        (df["Responsável"] == _hm_pessoa) & (df["Semana"] == _hm_semana)
                    ]
                    if not _df_cell.empty:
                        for _, _row in _df_cell.drop_duplicates(["Projeto", "Atividade"]).iterrows():
                            st.info(f"📌 **{_row['Projeto']}** — {_row['Atividade']} ({_fh(_row['Horas'])})") 
                    else:
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
                        if st.form_submit_button("➕ Salvar Projeto", type="primary", use_container_width=True):
                            if nome_p.strip():
                                try:
                                    _db.inserir_projeto(nome_p, desc_p, status_p,
                                                        unid_p, depto_p, subarea_p, tipo_p)
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
                                        cs1, cs2 = st.columns(2)
                                        with cs1:
                                            if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                                                try:
                                                    _db.atualizar_projeto(p["id"], ep_nome, ep_desc, ep_status,
                                                                          ep_unid, ep_depto, ep_sub, ep_tipo)
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
                            horas_a  = st.number_input("Horas estimadas", 0.0, 9999.0, step=0.5)
                            dc1, dc2 = st.columns(2)
                            with dc1: dt_ini = st.date_input("Início", format="DD/MM/YYYY")
                            with dc2: dt_fim = st.date_input("Término", format="DD/MM/YYYY")
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
                    _col_title, _col_btn = st.columns([3, 1])
                    with _col_title:
                        st.markdown("**Atividades por Projeto**")
                    with _col_btn:
                        if st.button("🔢 Reordenar por data", help="Reclassifica a ordem de todas as atividades de todos os projetos pela data de início", use_container_width=True):
                            try:
                                _n = _db.reordenar_atividades_por_data()
                                st.success(f"{_n} atividade(s) reordenadas!")
                                st.session_state.df = None
                                st.rerun()
                            except Exception as _e:
                                st.error(str(_e))
                    if proj_opts:
                        proj_view = st.selectbox("Selecionar projeto:", list(proj_opts.keys()), key="av_sel")
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
                                            ea_h     = st.number_input("Horas", 0.0, 9999.0,
                                                                        float(atv.get("horas_estimadas") or 0), step=0.5)
                                            ea_ini   = st.date_input("Início", value=atv.get("semana_inicio"), format="DD/MM/YYYY")
                                            ea_fim   = st.date_input("Término", value=atv.get("semana_fim"), format="DD/MM/YYYY")
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
