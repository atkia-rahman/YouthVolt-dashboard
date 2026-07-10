import streamlit as st
import pandas as pd
import requests
from io import StringIO
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="Project YouthVolt",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── BRANDING ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Quicksand:wght@400;500;600;700&display=swap');

/* Force light mode */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #f8fafc !important;
    color: #1a2333 !important;
}

html, body, [class*="css"], p, div, span, label, input, button, td, th, li {
    font-family: 'Quicksand', sans-serif !important;
    color: #1a2333 !important;
}
h1, h2, h3, h4, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    font-family: 'Poppins', sans-serif !important;
    color: #1a2333 !important;
}
.block-container {
    padding-top: 1rem !important;
    max-width: 1000px !important;
    background-color: #f8fafc !important;
}
/* Hide default streamlit header */
header[data-testid="stHeader"] { display: none; }

/* Radio buttons as horizontal tabs */
div[role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 0 !important;
    border-bottom: 2px solid #e2e8f0 !important;
    margin-bottom: 1.5rem !important;
    background: white !important;
    padding: 0 !important;
}
div[role="radiogroup"] label {
    font-family: 'Poppins', sans-serif !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    color: #64748b !important;
    padding: 10px 14px !important;
    border-bottom: 2.5px solid transparent !important;
    margin-bottom: -2px !important;
    cursor: pointer !important;
    white-space: nowrap !important;
    background: white !important;
}
div[role="radiogroup"] label:has(input:checked) {
    color: #1c8ecf !important;
    font-weight: 600 !important;
    border-bottom: 2.5px solid #1c8ecf !important;
}
div[role="radiogroup"] input { display: none !important; }

/* Force white background on all cards and containers */
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"],
section[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
}

.section-label {
    font-family: 'Poppins', sans-serif !important;
    font-size: 11px;
    font-weight: 600;
    color: #64748b !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
/* Dataframe font */
div[data-testid="stDataFrame"] * {
    font-family: 'Quicksand', sans-serif !important;
}
/* Info boxes */
div[data-testid="stInfo"] {
    background: #e8f4fc !important;
    color: #1a2333 !important;
}
</style>
""", unsafe_allow_html=True)

# ── GOOGLE SHEETS URLS ───────────────────────────────────────
HOUSEHOLD_SHEET_ID = "13yhmFpcD-R8PBkYOxKPAJPOsmgwDDMQj2h9ZldI8p4M"
SCHOOL_SHEET_ID    = "1x_mzUQWlOlbnFY9a6r8rkoNi7ES8MwzHKTAvrItimWk"

def sheet_to_df(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Could not load sheet: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_data():
    hh = sheet_to_df(HOUSEHOLD_SHEET_ID)
    sc = sheet_to_df(SCHOOL_SHEET_ID)
    return hh, sc

# ── LOAD DATA ────────────────────────────────────────────────
hh_raw, sc_raw = load_data()

# ── PROCESS SCHOOL DATA ──────────────────────────────────────
def process_school(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    df.columns = df.columns.str.strip()

    # Rename columns to standard names
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if 'date' in cl:               col_map[c] = 'Date'
        elif 'time' in cl:             col_map[c] = 'Time Slot'
        elif 'class' in cl:            col_map[c] = 'Class'
        elif 'fan' in cl:              col_map[c] = 'Fans ON'
        elif 'light' in cl:            col_map[c] = 'Lights ON'
        elif 'phase' in cl:            col_map[c] = 'Phase'
        elif 'note' in cl:             col_map[c] = 'Notes'
        elif 'observer' in cl:         col_map[c] = 'Observer'
    df = df.rename(columns=col_map)

    for col in ['Fans ON','Lights ON']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    df = df.dropna(subset=['Fans ON','Lights ON'])

    # Daily average per class (average 3 time slots)
    group_cols = [c for c in ['Date','Class','Phase'] if c in df.columns]
    daily = df.groupby(group_cols).agg(
        avg_fans=('Fans ON','mean'),
        avg_lights=('Lights ON','mean'),
        slots=('Time Slot','count')
    ).reset_index()
    daily['avg_devices'] = daily['avg_fans'] + daily['avg_lights']

    # Per-class summary
    baseline     = daily[daily['Phase']=='Baseline']
    intervention = daily[daily['Phase']=='Intervention']

    b_avg = baseline.groupby('Class')['avg_devices'].mean()
    i_avg = intervention.groupby('Class')['avg_devices'].mean() if not intervention.empty else pd.Series(dtype=float)

    summary = pd.DataFrame({'baseline_avg': b_avg})
    if not i_avg.empty:
        summary['intervention_avg'] = i_avg
        summary['efficiency_pct'] = ((summary['baseline_avg'] - summary['intervention_avg']) / summary['baseline_avg'] * 100).round(1)
        max_eff = summary['efficiency_pct'].max()
        summary['score'] = (summary['efficiency_pct'] / max_eff * 100).round(0).astype(int) if max_eff > 0 else 0
        summary['rank'] = summary['efficiency_pct'].rank(ascending=False).astype(int)
    else:
        summary['intervention_avg'] = None
        summary['efficiency_pct'] = None
        summary['score'] = None
        summary['rank'] = None

    summary = summary.reset_index()
    return daily, summary, df

# ── PROCESS HOUSEHOLD DATA ───────────────────────────────────
def process_household(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    df.columns = df.columns.str.strip()

    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if 'date' in cl:              col_map[c] = 'Date'
        elif 'household' in cl:       col_map[c] = 'Household ID'
        elif 'meter' in cl:           col_map[c] = 'Meter Reading'
        elif 'phase' in cl:           col_map[c] = 'Phase'
        elif 'note' in cl:            col_map[c] = 'Notes'
        elif 'observer' in cl:        col_map[c] = 'Observer'
    df = df.rename(columns=col_map)

    if 'Meter Reading' in df.columns:
        df['Meter Reading'] = pd.to_numeric(df['Meter Reading'], errors='coerce')
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    df = df.dropna(subset=['Meter Reading','Household ID','Phase'])

    # Per household: find baseline start/end and intervention start/end
    results = []
    for hh_id, grp in df.groupby('Household ID'):
        b_start = grp[grp['Phase']=='Baseline Start']['Meter Reading'].values
        b_end   = grp[grp['Phase']=='Baseline End']['Meter Reading'].values
        i_start = grp[grp['Phase']=='Intervention Start']['Meter Reading'].values
        i_end   = grp[grp['Phase']=='Intervention End']['Meter Reading'].values

        b_start_date = grp[grp['Phase']=='Baseline Start']['Date'].values
        b_end_date   = grp[grp['Phase']=='Baseline End']['Date'].values
        i_start_date = grp[grp['Phase']=='Intervention Start']['Date'].values
        i_end_date   = grp[grp['Phase']=='Intervention End']['Date'].values

        row = {'Household ID': hh_id}

        if len(b_start) and len(b_end):
            b_kwh  = float(b_end[0]) - float(b_start[0])
            b_days = (pd.Timestamp(b_end_date[0]) - pd.Timestamp(b_start_date[0])).days or 7
            row['baseline_daily_avg'] = round(b_kwh / b_days, 2)
        else:
            row['baseline_daily_avg'] = None

        if len(i_start) and len(i_end):
            i_kwh  = float(i_end[0]) - float(i_start[0])
            i_days = (pd.Timestamp(i_end_date[0]) - pd.Timestamp(i_start_date[0])).days or 14
            row['intervention_daily_avg'] = round(i_kwh / i_days, 2)
        else:
            row['intervention_daily_avg'] = None

        if row.get('baseline_daily_avg') and row.get('intervention_daily_avg'):
            row['efficiency_pct'] = round(
                (row['baseline_daily_avg'] - row['intervention_daily_avg']) / row['baseline_daily_avg'] * 100, 1
            )
        else:
            row['efficiency_pct'] = None

        results.append(row)

    summary = pd.DataFrame(results)
    if 'efficiency_pct' in summary.columns and summary['efficiency_pct'].notna().any():
        summary = summary.sort_values('efficiency_pct', ascending=False)
        summary['rank'] = range(1, len(summary)+1)

    return summary, df

# ── RUN PROCESSING ───────────────────────────────────────────
sc_daily, sc_summary, sc_clean = process_school(sc_raw)
hh_summary, hh_clean = process_household(hh_raw)

# ── CURRENT PHASE DETECTION ──────────────────────────────────
def detect_phase(sc_df, hh_df):
    if not hh_df.empty and 'Phase' in hh_df.columns:
        hh_phases = hh_df['Phase'].dropna().unique()
        if any('Intervention' in p for p in hh_phases):
            return "Household: Intervention"
        elif any('Baseline' in p for p in hh_phases):
            return "Household: Baseline"
    if not sc_df.empty and 'Phase' in sc_df.columns:
        latest = sc_df['Phase'].dropna().iloc[-1] if len(sc_df) else None
        if latest:
            return f"School: {latest}"
    return "Not started"

current_phase = detect_phase(sc_clean, hh_clean)

# ── COLORS ───────────────────────────────────────────────────
BLUE   = "#1c8ecf"
YELLOW = "#fbc212"
GREEN  = "#22c55e"
PURPLE = "#a855f7"
TEAL   = "#14b8a6"
PINK   = "#ec4899"
LINE_COLORS = [BLUE, YELLOW, GREEN, PURPLE, TEAL, PINK]

# ── HEADER ───────────────────────────────────────────────────
import base64
with open("youthvolt_logo-removebg-textless.png", "rb") as f:
    icon_b64 = base64.b64encode(f.read()).decode()

st.markdown(f"""
<div style='display:flex;align-items:center;gap:8px;padding:16px 0 8px 0;'>
    <img src='data:image/png;base64,{icon_b64}' style='height:68px;width:68px;object-fit:contain;flex-shrink:0;'/>
    <div style='display:flex;flex-direction:column;justify-content:center;'>
        <div style='font-family:Poppins,sans-serif;font-size:22px;font-weight:700;line-height:1.2;'>
            <span style='color:#1c8ecf;'>Project Youth</span><span style='color:#fbc212;'>Volt</span>
        </div>
        <div style='font-family:Quicksand,sans-serif;font-size:13px;color:#1c8ecf;font-weight:600;letter-spacing:0.04em;margin-top:2px;'>
            Energy Efficiency Dashboard
        </div>
    </div>
</div>
<hr style='margin:0 0 8px 0;border:none;border-top:1px solid #e2e8f0;'/>
""", unsafe_allow_html=True)

st.markdown("---")

# ── NAVIGATION ───────────────────────────────────────────────
page = st.radio("", ["Overview", "School Analysis", "Household Analysis", "MRV & Data Quality"],
    horizontal=True, label_visibility="collapsed")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# PAGE 1: OVERVIEW
# ══════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown("### Overview")

    # Summary cards
    st.markdown('<div class="section-label">Project Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        n_classes = sc_clean['Class'].nunique() if not sc_clean.empty and 'Class' in sc_clean.columns else 0
        st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Total Classes</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1c8ecf;'>{n_classes}</div></div>""", unsafe_allow_html=True)
    with c2:
        n_hh = hh_clean['Household ID'].nunique() if not hh_clean.empty and 'Household ID' in hh_clean.columns else 0
        st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Total Households</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1c8ecf;'>{n_hh}</div></div>""", unsafe_allow_html=True)
    with c3:
        n_days = sc_daily['Date'].nunique() if not sc_daily.empty and 'Date' in sc_daily.columns else 0
        st.markdown(f"""<div style='background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Days Recorded</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1a2333;'>{n_days}</div></div>""", unsafe_allow_html=True)
    with c4:
        phase_bg = "#e8f4fc" if "School" in current_phase else "#fef6d8"
        phase_color = "#1c8ecf" if "School" in current_phase else "#c9980e"
        st.markdown(f"""<div style='background:{phase_bg};border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Current Phase</div><div style='font-family:Poppins,sans-serif;font-size:16px;font-weight:700;color:{phase_color};'>{current_phase}</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Key results
    st.markdown('<div class="section-label">Key Results</div>', unsafe_allow_html=True)
    sc_eff = None
    if not sc_summary.empty and 'efficiency_pct' in sc_summary.columns and sc_summary['efficiency_pct'].notna().any():
        b_overall = sc_summary['baseline_avg'].mean()
        i_overall = sc_summary['intervention_avg'].mean()
        sc_eff = round((b_overall - i_overall) / b_overall * 100, 1) if b_overall else None

    hh_eff = None
    if not hh_summary.empty and 'efficiency_pct' in hh_summary.columns and hh_summary['efficiency_pct'].notna().any():
        hh_eff = round(hh_summary['efficiency_pct'].mean(), 1)

    overall = round((sc_eff + hh_eff) / 2, 1) if sc_eff is not None and hh_eff is not None else None

    k1, k2, k3 = st.columns(3)
    with k1:
        val = f"{sc_eff}%" if sc_eff is not None else "No data yet"
        st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>School Efficiency</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1c8ecf;'>{val}</div></div>""", unsafe_allow_html=True)
    with k2:
        val = f"{hh_eff}%" if hh_eff is not None else "No data yet"
        st.markdown(f"""<div style='background:#fef6d8;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Household Efficiency</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#c9980e;'>{val}</div></div>""", unsafe_allow_html=True)
    with k3:
        val = f"{overall}%" if overall is not None else "No data yet"
        st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Overall Efficiency</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1570a6;'>{val}</div></div>""", unsafe_allow_html=True)

    st.markdown("<small style='color:#64748b'>* HH = Household</small>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Comparison chart
    st.markdown('<div class="section-label">Baseline vs Intervention — Average Usage</div>', unsafe_allow_html=True)

    chart_data = []
    if not sc_summary.empty and 'baseline_avg' in sc_summary.columns:
        chart_data.append({"Category":"School Baseline", "Value":round(sc_summary['baseline_avg'].mean(),2), "Phase":"Baseline"})
    if not sc_summary.empty and 'intervention_avg' in sc_summary.columns and sc_summary['intervention_avg'].notna().any():
        chart_data.append({"Category":"School Intervention", "Value":round(sc_summary['intervention_avg'].mean(),2), "Phase":"Intervention"})
    if not hh_summary.empty and 'baseline_daily_avg' in hh_summary.columns and hh_summary['baseline_daily_avg'].notna().any():
        chart_data.append({"Category":"HH Baseline", "Value":round(hh_summary['baseline_daily_avg'].mean(),2), "Phase":"Baseline"})
    if not hh_summary.empty and 'intervention_daily_avg' in hh_summary.columns and hh_summary['intervention_daily_avg'].notna().any():
        chart_data.append({"Category":"HH Intervention", "Value":round(hh_summary['intervention_daily_avg'].mean(),2), "Phase":"Intervention"})

    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = px.bar(df_chart, x="Category", y="Value",
            color="Phase",
            color_discrete_map={"Baseline": YELLOW, "Intervention": BLUE},
            template="simple_white")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(
            font_family="Quicksand",
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(t=20,b=20,l=0,r=0),
            legend_title_text="",
            xaxis_title="", yaxis_title="Avg Usage"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 No data collected yet. Charts will appear once data is submitted.")

# ══════════════════════════════════════════════════════════════
# PAGE 2: SCHOOL ANALYSIS
# ══════════════════════════════════════════════════════════════
elif page == "School Analysis":
    st.markdown("### School Analysis")

    if sc_clean.empty:
        st.info("📭 No school data collected yet.")
    else:
        # Leaderboard
        st.markdown('<div class="section-label">🏆 Class Leaderboard</div>', unsafe_allow_html=True)
        if not sc_summary.empty and 'rank' in sc_summary.columns and sc_summary['rank'].notna().any():
            lb = sc_summary.sort_values('rank').copy()
            lb['Rank'] = lb['rank'].apply(lambda x: "🥇" if x==1 else "🥈" if x==2 else "🥉" if x==3 else f"#{int(x)}")
            lb['Avg Fans ON']   = lb['baseline_avg'].apply(lambda x: round(x/2,1) if pd.notna(x) else "—")
            lb['Avg Lights ON'] = lb['baseline_avg'].apply(lambda x: round(x/2,1) if pd.notna(x) else "—")
            lb['Efficiency %']  = lb['efficiency_pct'].apply(lambda x: f"{x}%" if pd.notna(x) else "—")
            lb['Score']         = lb['score'].apply(lambda x: int(x) if pd.notna(x) else "—")
            st.dataframe(
                lb[['Rank','Class','Avg Fans ON','Avg Lights ON','Efficiency %','Score']],
                hide_index=True, use_container_width=True
            )
        else:
            st.info("📭 Leaderboard available after intervention data is collected.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Usage trend
        st.markdown('<div class="section-label">Usage Trend by Class — Avg Devices ON per Day</div>', unsafe_allow_html=True)
        if not sc_daily.empty and 'Date' in sc_daily.columns and 'Class' in sc_daily.columns:
            pivot = sc_daily.pivot_table(index='Date', columns='Class', values='avg_devices', aggfunc='mean').reset_index()
            fig = go.Figure()
            for i, cls in enumerate([c for c in pivot.columns if c != 'Date']):
                fig.add_trace(go.Scatter(
                    x=pivot['Date'], y=pivot[cls], name=cls,
                    line=dict(color=LINE_COLORS[i % len(LINE_COLORS)], width=2),
                    mode='lines'
                ))
            fig.update_layout(
                font_family="Quicksand", plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=20,b=20,l=0,r=0),
                xaxis_title="Date", yaxis_title="Avg Devices ON",
                legend_title_text="Class"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📭 Trend chart will appear once data is collected.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Avg fans & lights by class
        st.markdown('<div class="section-label">Average Fans & Lights ON by Class</div>', unsafe_allow_html=True)
        if not sc_daily.empty:
            avg_by_class = sc_daily.groupby('Class')[['avg_fans','avg_lights']].mean().reset_index()
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(name='Fans ON',   x=avg_by_class['Class'], y=avg_by_class['avg_fans'],   marker_color=BLUE))
            fig2.add_trace(go.Bar(name='Lights ON', x=avg_by_class['Class'], y=avg_by_class['avg_lights'], marker_color=YELLOW))
            fig2.update_layout(
                barmode='group', font_family="Quicksand",
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=20,b=20,l=0,r=0),
                xaxis_title="Class", yaxis_title="Avg Devices ON"
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Efficiency by class
        st.markdown('<div class="section-label">Efficiency % by Class (vs Own Baseline)</div>', unsafe_allow_html=True)
        if not sc_summary.empty and 'efficiency_pct' in sc_summary.columns and sc_summary['efficiency_pct'].notna().any():
            fig3 = px.bar(sc_summary, x='Class', y='efficiency_pct',
                color='Class',
                color_discrete_sequence=LINE_COLORS,
                template="simple_white")
            fig3.update_layout(
                font_family="Quicksand", plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=20,b=20,l=0,r=0),
                xaxis_title="Class", yaxis_title="Efficiency %",
                showlegend=False
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("📭 Efficiency chart available after intervention data is collected.")

# ══════════════════════════════════════════════════════════════
# PAGE 3: HOUSEHOLD ANALYSIS
# ══════════════════════════════════════════════════════════════
elif page == "Household Analysis":
    st.markdown("### Household Analysis")

    if hh_clean.empty:
        st.info("📭 No household data collected yet.")
    else:
        # KPI cards
        st.markdown('<div class="section-label">Household Energy Consumption — Baseline vs Intervention</div>', unsafe_allow_html=True)
        b_avg = round(hh_summary['baseline_daily_avg'].mean(), 2) if not hh_summary.empty and 'baseline_daily_avg' in hh_summary.columns and hh_summary['baseline_daily_avg'].notna().any() else None
        i_avg = round(hh_summary['intervention_daily_avg'].mean(), 2) if not hh_summary.empty and 'intervention_daily_avg' in hh_summary.columns and hh_summary['intervention_daily_avg'].notna().any() else None
        eff   = round(hh_summary['efficiency_pct'].mean(), 1) if not hh_summary.empty and 'efficiency_pct' in hh_summary.columns and hh_summary['efficiency_pct'].notna().any() else None

        k1, k2, k3 = st.columns(3)
        with k1:
            val = f"{b_avg} kWh/day" if b_avg else "No data yet"
            st.markdown(f"""<div style='background:#fef6d8;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Baseline Avg</div><div style='font-family:Poppins,sans-serif;font-size:22px;font-weight:700;color:#c9980e;'>{val}</div></div>""", unsafe_allow_html=True)
        with k2:
            val = f"{i_avg} kWh/day" if i_avg else "No data yet"
            st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Intervention Avg</div><div style='font-family:Poppins,sans-serif;font-size:22px;font-weight:700;color:#1c8ecf;'>{val}</div></div>""", unsafe_allow_html=True)
        with k3:
            val = f"{eff}%" if eff else "No data yet"
            st.markdown(f"""<div style='background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Avg Efficiency</div><div style='font-family:Poppins,sans-serif;font-size:22px;font-weight:700;color:#1570a6;'>{val}</div></div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Efficiency bar
        st.markdown('<div class="section-label">Average Household Efficiency</div>', unsafe_allow_html=True)
        st.caption("Average daily kWh consumption — calculated as total kWh consumed ÷ number of days per phase.")
        if eff is not None:
            fig_eff = px.bar(
                pd.DataFrame([{"Category":"Avg Efficiency","Value":eff}]),
                x="Category", y="Value",
                color_discrete_sequence=[BLUE],
                template="simple_white"
            )
            fig_eff.update_layout(
                font_family="Quicksand", plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=20,b=20,l=0,r=0),
                xaxis_title="", yaxis_title="Efficiency %", showlegend=False
            )
            st.plotly_chart(fig_eff, use_container_width=True)
        else:
            st.info("📭 Chart available after both baseline and intervention data are collected.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Scatter plot
        st.markdown('<div class="section-label">Energy Efficiency by Household — % Saved vs Baseline</div>', unsafe_allow_html=True)
        st.caption("Each dot is one household. Higher = more energy saved. Hover to see details.")
        if not hh_summary.empty and 'efficiency_pct' in hh_summary.columns and hh_summary['efficiency_pct'].notna().any():
            scatter_df = hh_summary[hh_summary['efficiency_pct'].notna()].reset_index(drop=True)
            scatter_df['x'] = range(1, len(scatter_df)+1)
            fig_sc = px.scatter(scatter_df, x='x', y='efficiency_pct',
                hover_name='Household ID',
                hover_data={'x':False, 'efficiency_pct':True},
                template="simple_white",
                color_discrete_sequence=[BLUE])
            fig_sc.update_traces(marker=dict(size=10, opacity=0.75, line=dict(width=1.5, color='white')))
            fig_sc.add_hline(y=0, line_color="#e2e8f0", line_width=2)
            fig_sc.update_layout(
                font_family="Quicksand", plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=20,b=20,l=0,r=0),
                xaxis_title="Household #", yaxis_title="Efficiency %"
            )
            st.plotly_chart(fig_sc, use_container_width=True)
        else:
            st.info("📭 Scatter plot available after intervention data is collected.")

        st.markdown("<br>", unsafe_allow_html=True)

        # Ranked table
        st.markdown('<div class="section-label">🏆 All Households — Ranked by Energy Efficiency</div>', unsafe_allow_html=True)
        if not hh_summary.empty and 'efficiency_pct' in hh_summary.columns and hh_summary['efficiency_pct'].notna().any():
            ranked = hh_summary[hh_summary['efficiency_pct'].notna()].copy()
            ranked['Rank'] = ranked['rank'].apply(lambda x: "🥇" if x==1 else "🥈" if x==2 else "🥉" if x==3 else f"#{int(x)}")
            ranked['Efficiency %'] = ranked['efficiency_pct'].apply(lambda x: f"{x}%")
            ranked['Baseline Avg (kWh/day)'] = ranked['baseline_daily_avg']
            ranked['Intervention Avg (kWh/day)'] = ranked['intervention_daily_avg']
            st.dataframe(
                ranked[['Rank','Household ID','Baseline Avg (kWh/day)','Intervention Avg (kWh/day)','Efficiency %']],
                hide_index=True, use_container_width=True
            )
        else:
            st.info("📭 Rankings available after intervention data is collected.")

# ══════════════════════════════════════════════════════════════
# PAGE 4: MRV & DATA QUALITY
# ══════════════════════════════════════════════════════════════
elif page == "MRV & Data Quality":
    st.markdown("### MRV & Data Quality")

    # Data volume
    st.markdown('<div class="section-label">Data Volume</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        v = len(sc_raw) + len(hh_raw)
        st.markdown(f"""<div style='background:#e8f4fc;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Total Entries</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1c8ecf;'>{v}</div></div>""", unsafe_allow_html=True)
    with m2:
        n_days = sc_daily['Date'].nunique() if not sc_daily.empty and 'Date' in sc_daily.columns else 0
        st.markdown(f"""<div style='background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Days Recorded</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1a2333;'>{n_days}</div></div>""", unsafe_allow_html=True)
    with m3:
        n_cls = sc_clean['Class'].nunique() if not sc_clean.empty and 'Class' in sc_clean.columns else 0
        st.markdown(f"""<div style='background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Classes Tracked</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1a2333;'>{n_cls}</div></div>""", unsafe_allow_html=True)
    with m4:
        n_hh = hh_clean['Household ID'].nunique() if not hh_clean.empty and 'Household ID' in hh_clean.columns else 0
        st.markdown(f"""<div style='background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05);'><div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;color:#64748b;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px;'>Households Tracked</div><div style='font-family:Poppins,sans-serif;font-size:24px;font-weight:700;color:#1a2333;'>{n_hh}</div></div>""", unsafe_allow_html=True)

    st.caption("Each school day = 3 observations per class (Morning, Midday, End of Day). Entries and observations are the same count.")
    st.markdown("<br>", unsafe_allow_html=True)

    # Completeness
    st.markdown('<div class="section-label">Data Completeness</div>', unsafe_allow_html=True)
    if not sc_daily.empty and 'slots' in sc_daily.columns:
        complete = (sc_daily['slots'] == 3).sum()
        total    = len(sc_daily)
        pct      = round(complete / total * 100, 1) if total else 0
        fig_pie = px.pie(
            values=[pct, 100-pct],
            names=["Complete","Missing"],
            color_discrete_sequence=[BLUE, "#e2e8f0"],
            hole=0.4
        )
        fig_pie.update_layout(
            font_family="Quicksand", paper_bgcolor="white",
            margin=dict(t=20,b=20,l=0,r=0)
        )
        col_pie, col_stats = st.columns([1,1])
        with col_pie:
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_stats:
            st.metric("Complete entries", f"{pct}%")
            st.metric("Missing entries",  f"{round(100-pct,1)}%")
        st.caption("Completeness = entries actually recorded ÷ entries expected across all classes and all days.")
    else:
        st.info("📭 Completeness data will appear once school observations are collected.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Calendar heatmap
    st.markdown('<div class="section-label">Data Collection Calendar — Entries per Day</div>', unsafe_allow_html=True)
    if not sc_daily.empty and 'Date' in sc_daily.columns:
        cal = sc_daily.groupby('Date')['slots'].sum().reset_index()
        cal.columns = ['Date','Entries']
        fig_cal = px.bar(cal, x='Date', y='Entries',
            color='Entries',
            color_continuous_scale=[[0,'#f1f5f9'],[0.5,'#fde48a'],[1,'#1c8ecf']],
            template="simple_white")
        fig_cal.update_layout(
            font_family="Quicksand", plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(t=20,b=20,l=0,r=0),
            xaxis_title="Date", yaxis_title="Entries",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_cal, use_container_width=True)
    else:
        st.info("📭 Calendar will appear once data is collected.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Anomaly log
    st.markdown('<div class="section-label">Anomaly Log — Entries with Notes</div>', unsafe_allow_html=True)
    anomalies = []
    if not sc_clean.empty and 'Notes' in sc_clean.columns:
        sc_anomalies = sc_clean[sc_clean['Notes'].notna() & (sc_clean['Notes'].str.strip() != '')][['Date','Class','Notes']].copy()
        sc_anomalies.columns = ['Date','Source','Note']
        anomalies.append(sc_anomalies)
    if not hh_clean.empty and 'Notes' in hh_clean.columns:
        hh_anomalies = hh_clean[hh_clean['Notes'].notna() & (hh_clean['Notes'].str.strip() != '')][['Date','Household ID','Notes']].copy()
        hh_anomalies.columns = ['Date','Source','Note']
        anomalies.append(hh_anomalies)

    if anomalies:
        all_anomalies = pd.concat(anomalies).sort_values('Date', ascending=False)
        st.dataframe(all_anomalies, hide_index=True, use_container_width=True)
    else:
        st.info("📭 No anomalies flagged yet. Notes from your forms will appear here.")
