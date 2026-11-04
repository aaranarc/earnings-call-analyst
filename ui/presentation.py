"""Optional visual styling and charts. All interactions remain native Streamlit/Python."""
import altair as alt
import pandas as pd
import streamlit as st

LIME = '#DDEB91'
BLUE = '#AFC0E1'
MUTED = '#B9B9C2'


def apply_design():
    # Appearance only: deleting this block leaves a functional native Streamlit app.
    st.html('''<style>
    .stApp {background:#111113;color:#F3F3F5}
    [data-testid="stSidebar"] {background:#19191C;border-right:1px solid #303036}
    [data-testid="stSidebar"] h1 {font-size:2rem;letter-spacing:-.07em}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding:.7rem .8rem;border-radius:12px;margin-bottom:.25rem;min-height:44px}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background:#2A2A2E;color:#DDEB91}
    .block-container {padding-top:2.2rem;max-width:1560px;padding-bottom:3rem}
    h1 {font-size:2.35rem!important;letter-spacing:-.055em;line-height:1.12!important}
    h2 {font-size:1.45rem!important;letter-spacing:-.035em}
    h3 {font-size:1.08rem!important;letter-spacing:-.02em}
    [data-testid="stMetric"] {background:#202024;border:1px solid #303036;
        border-radius:20px;padding:1.2rem 1.35rem;min-height:124px}
    [data-testid="stMetricValue"] {font-family:ui-monospace,monospace;font-size:2.2rem;
        font-variant-numeric:tabular-nums;letter-spacing:-.07em}
    [data-testid="stMetricLabel"] {color:#B9B9C2}
    [data-testid="stVerticalBlockBorderWrapper"] {border-radius:20px!important}
    [data-testid="stExpander"] {border-radius:14px;background:#1C1C20}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color:#B9B9C2}
    button[kind="primary"],button[kind="primary"] p {color:#111113!important}
    [data-testid="stForm"] {border-color:#35353D;border-radius:20px;background:#1C1C20}
    .stButton>button,.stDownloadButton>button {border-radius:12px;min-height:44px}
    a {color:#DDEB91}
    @media(max-width:640px){.block-container{padding:1rem 1rem 3rem}
        h1{font-size:1.9rem!important}[data-testid="stMetric"]{min-height:100px}}
    </style>''')


def chart_style(chart):
    return chart.configure_view(stroke=None).configure_axis(
        labelColor=MUTED, titleColor=MUTED, gridColor='#303036', domain=False,
        labelFontSize=11, titleFontSize=11).configure_legend(labelColor=MUTED, titleColor=MUTED)


def coverage_grid(companies):
    """One cell per registered fiscal quarter; absent transcripts stay explicit."""
    periods = sorted({d['fiscal_label'] for c in companies for d in c['documents']},
                     key=lambda p: (int(p[-2:]), int(p[1])))
    rows = [{'Company': c['symbol'], 'Quarter': period,
             'Coverage': 'Available' if any(d['fiscal_label'] == period for d in c['documents']) else 'Not ingested'}
            for c in companies for period in periods]
    chart = alt.Chart(pd.DataFrame(rows)).mark_rect(cornerRadius=5, stroke='#202024', strokeWidth=5).encode(
        x=alt.X('Quarter:O', sort=periods, axis=alt.Axis(labelAngle=0, title=None)),
        y=alt.Y('Company:N', sort=[c['symbol'] for c in companies], title=None),
        color=alt.Color('Coverage:N', scale=alt.Scale(domain=['Available', 'Not ingested'],
                         range=['#A9B66C', '#2C2C31']), legend=alt.Legend(orient='bottom')),
        tooltip=['Company:N', 'Quarter:N', 'Coverage:N']).properties(height=310)
    st.altair_chart(chart_style(chart), width='stretch', theme=None)


def corpus_ring(companies):
    rows = [{'Sector': c['sector'].replace('_', ' ').title(), 'Calls': len(c['documents'])} for c in companies]
    chart = alt.Chart(pd.DataFrame(rows)).mark_arc(innerRadius=73, outerRadius=100, cornerRadius=3).encode(
        theta=alt.Theta('sum(Calls):Q'), color=alt.Color('Sector:N',
            scale=alt.Scale(range=[LIME, BLUE, '#888594']), legend=alt.Legend(orient='bottom', title=None)),
        tooltip=['Sector:N', alt.Tooltip('sum(Calls):Q', title='Transcripts')]).properties(height=280)
    st.altair_chart(chart_style(chart), width='stretch', theme=None)


def timeline(milestones):
    rows = [dict(m, index=i + 1) for i, m in enumerate(milestones)]
    chart = alt.Chart(pd.DataFrame(rows)).mark_line(point=alt.OverlayMarkDef(size=130), color=LIME).encode(
        x=alt.X('period_end:T', title='Reported quarter'),
        y=alt.Y('index:Q', title=None, axis=None, scale=alt.Scale(domain=[0, len(rows) + 1])),
        tooltip=['period:N', 'stage:N', 'label:N']).properties(height=160)
    st.altair_chart(chart_style(chart), width='stretch', theme=None)
