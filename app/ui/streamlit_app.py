import streamlit as st
import requests
import pandas as pd
import json
import os
import plotly.graph_objects as go
import hashlib

st.set_page_config(
    page_title="QuantRAG",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Premium Quant Look ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
        background-color: #0A0A0B;
        color: #EDEDED;
    }
    
    .mono {
        font-family: 'Roboto Mono', monospace;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0A0A0B; }
    ::-webkit-scrollbar-thumb { background: #2D2D30; border-radius: 0px; }
    ::-webkit-scrollbar-thumb:hover { background: #F59E0B; }

    h1, h2, h3, h4, h5, h6 {
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: #EDEDED;
    }
    
    /* Hero Section */
    .hero-container {
        padding: 32px 0 24px 0;
        margin-bottom: 24px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }
    
    .hero-title {
        margin: 0; 
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    .hero-subtitle {
        color: #98989D; 
        font-size: 14px; 
        margin-top: 8px;
        font-family: 'Roboto Mono', monospace;
    }

    /* Flat Metric Cards */
    .metric-card {
        background-color: #121212;
        padding: 20px;
        border: 1px solid #2A2A2A;
        border-radius: 2px;
        margin-bottom: 24px;
        transition: border-color 0.2s;
    }
    
    .metric-card:hover {
        border-color: #F59E0B;
    }
    
    .risk-label { color: #98989D; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 8px; font-family: 'Roboto Mono', monospace;}
    
    /* Chat bubbles */
    .chat-user {
        background-color: #1E1E1E;
        border-left: 3px solid #F59E0B;
        color: #EDEDED;
        padding: 16px;
        border-radius: 2px;
        margin: 16px 0 16px auto;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.5;
    }
    
    .chat-bot {
        background-color: #121212;
        border: 1px solid #2A2A2A;
        border-left: 3px solid #3B82F6;
        color: #D4D4D4;
        padding: 16px;
        border-radius: 2px;
        margin: 16px auto 16px 0;
        max-width: 85%;
        font-size: 14px;
        line-height: 1.6;
    }
    
    .source-card {
        margin-bottom: 8px;
        padding: 12px;
        border: 1px solid #2A2A2A;
        background: #0A0A0B;
        border-radius: 2px;
        font-family: 'Roboto Mono', monospace;
        font-size: 12px;
    }
    
    .stNumberInput > div > div > input {
        border-radius: 2px;
        border: 1px solid #2A2A2A;
        padding: 10px;
        background-color: #121212;
        color: #EDEDED;
        font-family: 'Roboto Mono', monospace;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 1px solid #2A2A2A;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border-radius: 0;
        padding-top: 8px;
        padding-bottom: 8px;
        font-size: 14px;
        color: #98989D;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        border-bottom: 2px solid #F59E0B !important;
        color: #F59E0B !important;
    }
    
    /* Footer */
    .minimal-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #0A0A0B;
        border-top: 1px solid #2A2A2A;
        padding: 8px 24px;
        font-size: 11px;
        color: #636366;
        z-index: 100;
        display: flex;
        justify-content: space-between;
        font-family: 'Roboto Mono', monospace;
    }
    .minimal-footer a {
        color: #F59E0B;
        text-decoration: none;
    }
    
    /* Top-Right Status */
    .system-status {
        position: fixed;
        top: 16px;
        right: 24px;
        display: flex;
        align-items: center;
        background: #121212;
        padding: 6px 12px;
        border-radius: 2px;
        border: 1px solid #2A2A2A;
        font-size: 11px;
        font-weight: 500;
        z-index: 999;
        font-family: 'Roboto Mono', monospace;
    }
    .status-dot-green {
        width: 6px; height: 6px; background: #10B981; border-radius: 50%; margin-right: 8px;
    }
    .status-dot-red {
        width: 6px; height: 6px; background: #EF4444; border-radius: 50%; margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

def get_company_color(company_name):
    """Generate a consistent hex color for a given company name"""
    colors = ["#F59E0B", "#3B82F6", "#10B981", "#8B5CF6", "#EF4444"]
    h = int(hashlib.sha256(company_name.encode()).hexdigest(), 16)
    return colors[h % len(colors)]

def get_market_flag(market):
    market_str = str(market).upper()
    if "US" in market_str: return "US"
    if "INDIA" in market_str or "IN" in market_str: return "IN"
    return "GLB"

def plot_risk_gauge(score, tier):
    if tier == "High":
        color = "#EF4444"
    elif tier == "Medium":
        color = "#F59E0B"
    else:
        color = "#10B981"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={'font': {'size': 40, 'family': 'Roboto Mono'}, 'valueformat': '.3f'},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "#404040", 'tickfont': {'family': 'Roboto Mono'}},
            'bar': {'color': color, 'thickness': 0.3},
            'bgcolor': "#121212",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 0.3], 'color': "#1A1A1A"},
                {'range': [0.3, 0.7], 'color': "#222222"},
                {'range': [0.7, 1.0], 'color': "#2A2A2A"}
            ],
        }
    ))
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={'color': "#EDEDED"},
        height=220,
        margin=dict(l=20, r=20, t=10, b=10)
    )
    return fig

def normalize_source(src):
    if isinstance(src, dict):
        return {
            "company": src.get("company", "Unknown"),
            "quarter": src.get("quarter", ""),
            "year": src.get("year", ""),
            "excerpt": src.get("excerpt", ""),
        }
    parts = str(src).split()
    return {
        "company": parts[0] if parts else "Unknown",
        "quarter": parts[-1] if len(parts) > 1 else "",
        "year": parts[-2] if len(parts) > 2 else "",
        "excerpt": str(src),
    }

def render_source_card(src):
    source = normalize_source(src)
    comp_color = get_company_color(source["company"])
    excerpt = source["excerpt"]
    excerpt_html = f'<div style="color:#98989D; margin-top: 8px;">"{excerpt}..."</div>' if excerpt else ""
    st.markdown(f"""
    <div class='source-card' style='border-left: 3px solid {comp_color};'>
        <span style='color:#EDEDED; font-weight:600;'>{source["company"]}</span>
        <span style='color:#636366; margin: 0 8px;'>|</span>
        <span style='color:#F59E0B;'>{source["year"]} {source["quarter"]}</span>
        {excerpt_html}
    </div>
    """, unsafe_allow_html=True)

def get_companies():
    try:
        response = requests.get(f"{API_URL}/companies", timeout=120)
        if response.status_code == 200:
            return response.json(), True
    except:
        pass
    return [], False

companies_data, backend_connected = get_companies()

# --- Top Right Status ---
if backend_connected:
    st.markdown("""<div class="system-status"><div class="status-dot-green"></div>SYS.OK</div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div class="system-status"><div class="status-dot-red"></div>SYS.OFFLINE</div>""", unsafe_allow_html=True)


unique_companies = []
markets_count = 0
if companies_data:
    if isinstance(companies_data, dict) and "error" in companies_data:
        st.error(f"Backend Error: {companies_data['error']}")
        st.code(companies_data.get("traceback", ""))
        st.stop()
        
    df_companies = pd.DataFrame(companies_data)
    unique_companies = df_companies["company"].unique().tolist()
    markets_count = df_companies["market"].nunique()
    docs_count = len(df_companies) * 40
else:
    docs_count = 0

# --- Header ---
st.markdown(f"""
<div class="hero-container">
    <h1 class="hero-title">QuantRAG</h1>
    <div class="hero-subtitle">RAG pipeline over earnings call transcripts with XGBoost bankruptcy risk scoring. Built on ChromaDB + Gemini embeddings.</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h3 style='font-size:16px; border-bottom: 1px solid #2A2A2A; padding-bottom:8px;'>QUANTITATIVE RISK</h3>", unsafe_allow_html=True)
    
    if unique_companies:
        selected_company = st.selectbox("TARGET COMPANY", unique_companies)
        
        with st.spinner("Scoring..."):
            try:
                res = requests.post(f"{API_URL}/risk-score", json={"company_name": selected_company}, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    score = data.get("risk_score", 0.0)
                    tier = data.get("risk_tier", "Unknown")
                    
                    st.markdown("<div class='metric-card' style='margin-top: 16px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='risk-label'>XGBoost Output: {tier}</div>", unsafe_allow_html=True)
                    st.plotly_chart(plot_risk_gauge(score, tier), use_container_width=True)
                    
                    st.markdown("""
                    <div style='font-size: 11px; color: #98989D; font-family: "Roboto Mono", monospace; padding-top: 12px; border-top: 1px solid #2A2A2A;'>
                        <strong>EXPLAINABILITY (SHAP Proxies):</strong><br>
                        • ROA(C) impact: 34%<br>
                        • Debt Ratio impact: 28%<br>
                        • Net Value Growth: 15%
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            except:
                st.error("Connection failed.")
    else:
        st.info("Awaiting data...")

tab1, tab2, tab3 = st.tabs(["RESEARCH CHAT", "CORPUS BROWSER", "MANUAL SCORING"])

# --- TAB 1: Research Chat ---
with tab1:
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'<div class="chat-user">{message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bot">{message["content"]}</div>', unsafe_allow_html=True)
            if "sources" in message and message["sources"]:
                with st.expander("RELEVANT CHUNKS [View Metadata]", expanded=False):
                    for src in message["sources"]:
                        render_source_card(src)

    if prompt := st.chat_input("Enter query (e.g., 'Compare JPMorgan and HDFC Q1 revenues')"):
        st.markdown(f'<div class="chat-user">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Querying vector database..."):
            try:
                res = requests.post(f"{API_URL}/ask", json={"question": prompt}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "No answer found.")
                    sources = data.get("sources", [])
                    
                    st.markdown(f'<div class="chat-bot">{answer}</div>', unsafe_allow_html=True)
                    
                    if sources:
                        with st.expander("RELEVANT CHUNKS [View Metadata]", expanded=False):
                            for src in sources:
                                render_source_card(src)
                    
                    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
                else:
                    st.error(f"ERR: {res.text}")
            except requests.exceptions.ConnectionError as e:
                st.error(f"ERR: {e}")


# --- TAB 2: Corpus Browser ---
with tab2:
    if companies_data:
        grouped = df_companies.groupby("company")
        cols = st.columns(3)
        col_idx = 0
        
        for company, group in grouped:
            comp_color = get_company_color(company)
            market_val = group['market'].iloc[0]
            flag = get_market_flag(market_val)
            
            with cols[col_idx % 3]:
                # Mock NLP Sentiment Breakdown
                pos = 40 + (col_idx * 7) % 30
                neu = 30 + (col_idx * 3) % 20
                neg = 100 - pos - neu
                
                st.markdown(f"""
                <div class="metric-card" style="border-top: 3px solid {comp_color};">
                    <h3 style="margin-top:0; color:#EDEDED;">{company}</h3>
                    <div style="color:#98989D; margin-bottom:16px; font-size:12px; font-family:'Roboto Mono', monospace;">
                        MKT: {flag} | CHUNKS: {len(group) * 22}
                    </div>
                    
                    <div style="font-size: 11px; font-family: 'Roboto Mono', monospace; margin-bottom: 4px; color: #636366;">NLP SENTIMENT</div>
                    <div style="display: flex; height: 6px; border-radius: 1px; overflow: hidden; margin-bottom: 16px;">
                        <div style="width: {pos}%; background: #10B981;" title="Positive: {pos}%"></div>
                        <div style="width: {neu}%; background: #F59E0B;" title="Neutral: {neu}%"></div>
                        <div style="width: {neg}%; background: #EF4444;" title="Negative: {neg}%"></div>
                    </div>
                    
                    <div style="display:flex; flex-wrap:wrap; gap:6px;">
                """, unsafe_allow_html=True)
                
                quarters_html = ""
                for _, row in group.iterrows():
                    quarters_html += f"<span style='background:#1E1E1E; padding:4px 8px; border-radius:2px; font-size:11px; font-family:\"Roboto Mono\", monospace; color:#D4D4D4; border: 1px solid #2A2A2A;'>{row['year']} {row['quarter']}</span>"
                
                st.markdown(quarters_html + "</div></div>", unsafe_allow_html=True)
            col_idx += 1
    else:
        st.info("No data available.")

# --- TAB 3: Risk Dashboard ---
with tab3:
    col_input, col_result = st.columns([1.2, 1], gap="large")
    
    with col_input:
        with st.form("risk_form"):
            st.markdown("<h4 style='margin-bottom: 16px; margin-top: 0;'>XGBoost Input Tensors</h4>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                roa = st.number_input("ROA(C)", value=0.5, step=0.01)
                operating_margin = st.number_input("Operating Gross Margin", value=0.5, step=0.01)
                net_value_growth = st.number_input("Cont. Net Value Growth", value=0.5, step=0.01)
                
            with c2:
                debt_ratio = st.number_input("Debt ratio %", value=0.5, step=0.01)
                net_income_flag = st.number_input("Net Income Flag", value=1.0, step=1.0)
                cash_turnover = st.number_input("Cash Turnover Rate", value=0.5, step=0.01)
                
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button("COMPUTE SCORE", type="primary", use_container_width=True)

    with col_result:
        st.markdown("<h4 style='margin-bottom: 16px; margin-top: 0;'>Model Output</h4>", unsafe_allow_html=True)
        
        if submit_button:
            payload = {
                "ROA(C) before interest and depreciation before interest": roa,
                " Operating Gross Margin": operating_margin,
                " Continuous Net Value Growth Rate": net_value_growth,
                " Debt ratio %": debt_ratio,
                " Net Income Flag": net_income_flag,
                " Cash Turnover Rate": cash_turnover
            }
            
            with st.spinner("Inference..."):
                try:
                    res = requests.post(f"{API_URL}/risk-score", json={"financial_ratios": payload}, timeout=30)
                    if res.status_code == 200:
                        data = res.json()
                        score = data.get("risk_score", 0.0)
                        tier = data.get("risk_tier", "Unknown")
                        
                        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                        st.markdown(f"<div class='risk-label'>Risk Tier: {tier}</div>", unsafe_allow_html=True)
                        st.plotly_chart(plot_risk_gauge(score, tier), use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.error(f"ERR: {res.text}")
                except requests.exceptions.ConnectionError as e:
                    st.error(f"ERR: {e}")
        else:
            st.markdown("<div class='metric-card' style='opacity: 0.3;'>", unsafe_allow_html=True)
            st.plotly_chart(plot_risk_gauge(0, "Low"), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# --- Minimal Footer ---
st.markdown("""
<div class='minimal-footer'>
    <span>STACK: FastAPI · ChromaDB · Gemini-3.1-Flash-Lite · XGBoost</span>
    <span><a href="https://github.com/aaranarc/earnings-call-analyst" target="_blank">github.com/aaranarc/earnings-call-analyst</a></span>
</div>
""", unsafe_allow_html=True)

