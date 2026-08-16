import streamlit as st
import requests
import pandas as pd
import json
import os
import plotly.graph_objects as go
import hashlib

st.set_page_config(
    page_title="Earnings Call Analyst",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Premium Look ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0A0A0B; 
    }
    ::-webkit-scrollbar-thumb {
        background: #2D2D30; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #10B981; 
    }

    h1, h2, h3, h4, h5, h6 {
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: #EDEDED;
    }
    
    /* Reveal animation for title */
    @keyframes revealText {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    .hero-title {
        animation: revealText 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
    }

    /* Animated gradient mesh background for Hero */
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .hero-container {
        background: linear-gradient(-45deg, #0A0A0B, #062f21, #0a4d33, #0A0A0B);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
        padding: 40px 32px 24px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    
    /* Pulsing Live Dot */
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.2);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        color: #10B981;
        margin-bottom: 16px;
    }
    .pulse-dot {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse-green 2s infinite;
    }

    .metric-card {
        background-color: #161618;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 24px;
        text-align: center;
        transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
        position: relative;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(16, 185, 129, 0.5);
        box-shadow: 0 12px 30px rgba(16, 185, 129, 0.08), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    
    .risk-high { color: #FF453A; font-size: 56px; font-weight: 700; line-height: 1.2; }
    .risk-medium { color: #FF9F0A; font-size: 56px; font-weight: 700; line-height: 1.2; }
    .risk-low { color: #32D74B; font-size: 56px; font-weight: 700; line-height: 1.2; }
    .risk-label { color: #98989D; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 8px;}
    
    hr {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 32px 0;
    }
    
    @keyframes fadeInChat {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .chat-user {
        background-color: #10B981;
        color: #0A0A0B;
        padding: 16px 20px;
        border-radius: 16px 16px 4px 16px;
        margin: 16px 0 16px auto;
        max-width: 80%;
        font-size: 15px;
        line-height: 1.5;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
        animation: fadeInChat 0.3s ease-out forwards;
    }
    
    .chat-bot {
        background-color: #1C1C1E;
        border: 1px solid rgba(255,255,255,0.1);
        color: #E5E5EA;
        padding: 16px 20px;
        border-radius: 16px 16px 16px 4px;
        margin: 16px auto 16px 0;
        max-width: 80%;
        font-size: 15px;
        line-height: 1.6;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        animation: fadeInChat 0.4s ease-out forwards;
    }
    
    .stNumberInput > div > div > input {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        padding: 12px;
        background-color: #1C1C1E;
        color: #EDEDED;
    }
    
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
    }

    /* Custom Callouts */
    .callout-success {
        background: rgba(50, 215, 75, 0.1);
        border-left: 4px solid #32D74B;
        padding: 16px;
        border-radius: 8px;
        color: #EDEDED;
    }
    .callout-warning {
        background: rgba(255, 159, 10, 0.1);
        border-left: 4px solid #FF9F0A;
        padding: 16px;
        border-radius: 8px;
        color: #EDEDED;
    }
    .callout-danger {
        background: rgba(255, 69, 58, 0.1);
        border-left: 4px solid #FF453A;
        padding: 16px;
        border-radius: 8px;
        color: #EDEDED;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        border-bottom-color: #10B981 !important;
        color: #10B981 !important;
    }
    
    /* Chat Input Send Button Polish */
    [data-testid="stChatInputSubmitButton"] {
        transition: transform 0.2s ease, background-color 0.2s ease;
        border-radius: 50%;
    }
    [data-testid="stChatInputSubmitButton"]:hover {
        background-color: rgba(16, 185, 129, 0.1);
        transform: scale(1.1);
    }
    [data-testid="stChatInputSubmitButton"] svg {
        fill: #10B981;
    }
    
    /* Minimal Footer */
    .minimal-footer {
        position: fixed;
        bottom: 16px;
        right: 24px;
        font-size: 11px;
        color: #636366;
        z-index: 100;
        letter-spacing: 0.5px;
    }
    
    /* Top-Right Status */
    .system-status {
        position: fixed;
        top: 24px;
        right: 24px;
        display: flex;
        align-items: center;
        background: rgba(22, 22, 24, 0.8);
        backdrop-filter: blur(8px);
        padding: 6px 14px;
        border-radius: 20px;
        border: 1px solid rgba(255,255,255,0.05);
        font-size: 12px;
        font-weight: 500;
        z-index: 999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .status-dot-green {
        width: 8px; height: 8px; background: #32D74B; border-radius: 50%; margin-right: 8px;
        box-shadow: 0 0 8px rgba(50, 215, 75, 0.6);
    }
    .status-dot-red {
        width: 8px; height: 8px; background: #FF453A; border-radius: 50%; margin-right: 8px;
        box-shadow: 0 0 8px rgba(255, 69, 58, 0.6);
    }
</style>
""", unsafe_allow_html=True)


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

def get_company_color(company_name):
    """Generate a consistent hex color for a given company name"""
    colors = ["#10B981", "#3B82F6", "#8B5CF6", "#F59E0B", "#EF4444", "#EC4899", "#14B8A6"]
    h = int(hashlib.sha256(company_name.encode()).hexdigest(), 16)
    return colors[h % len(colors)]

def get_market_flag(market):
    market_str = str(market).upper()
    if "US" in market_str: return "🇺🇸"
    if "INDIA" in market_str or "IN" in market_str: return "🇮🇳"
    return "🌍"

def plot_risk_gauge(score, tier):
    if tier == "High":
        color = "#FF453A"
    elif tier == "Medium":
        color = "#FF9F0A"
    else:
        color = "#32D74B"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.2)"},
            'bar': {'color': color, 'thickness': 0.8}, # Thicker arc
            'bgcolor': "rgba(255,255,255,0.02)",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 0.3], 'color': "rgba(50, 215, 75, 0.1)"},
                {'range': [0.3, 0.7], 'color': "rgba(255, 159, 10, 0.1)"},
                {'range': [0.7, 1.0], 'color': "rgba(255, 69, 58, 0.1)"}
            ],
        }
    ))
    
    # Simulate a glow effect implicitly with vibrant colors and thick bar
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={'color': "white", 'family': "Inter"},
        height=300,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    return fig

def get_companies():
    try:
        response = requests.get(f"{API_URL}/companies", timeout=30)
        if response.status_code == 200:
            return response.json(), True
    except:
        pass
    return [], False

companies_data, backend_connected = get_companies()

# --- Top Right Status ---
if backend_connected:
    st.markdown("""<div class="system-status"><div class="status-dot-green"></div>Backend: Connected</div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div class="system-status"><div class="status-dot-red"></div>Backend: Offline</div>""", unsafe_allow_html=True)


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
    docs_count = len(df_companies) * 40 # Mocking the doc count based on quarters
else:
    docs_count = 0

# --- Header ---
st.markdown(f"""
<div class="hero-container">
    <div class="live-badge"><div class="pulse-dot"></div>{len(unique_companies)} companies · {markets_count} markets · Live</div>
    <h1 class="hero-title" style="margin: 0; font-size: 48px;">Earnings Call Analyst</h1>
    <p class="hero-title" style="color:#98989D; font-size:18px; margin-top:12px; animation-delay: 0.2s;">Intelligent retrieval and quantitative risk scoring for corporate transcripts.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📊 Quantitative Risk")
    st.markdown("Select a company to view its predicted bankruptcy risk score alongside your research.")
    
    if unique_companies:
        selected_company = st.selectbox("Company", unique_companies)
        
        with st.spinner("Fetching live data & Scoring..."):
            try:
                res = requests.post(f"{API_URL}/risk-score", json={"company_name": selected_company}, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    score = data.get("risk_score", 0.0)
                    tier = data.get("risk_tier", "Unknown")
                    
                    st.markdown("<div class='metric-card' style='padding: 16px; margin-top: 16px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='risk-label' style='text-align: center;'>Risk Tier: {tier}</div>", unsafe_allow_html=True)
                    st.plotly_chart(plot_risk_gauge(score, tier), use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if tier == "High":
                        st.markdown("""<div class='callout-danger' style='font-size: 13px;'><strong>⚠️ High Risk Detected</strong></div>""", unsafe_allow_html=True)
                    elif tier == "Medium":
                        st.markdown("""<div class='callout-warning' style='font-size: 13px;'><strong>⚠️ Elevated Risk</strong></div>""", unsafe_allow_html=True)
                    else:
                        st.markdown("""<div class='callout-success' style='font-size: 13px;'><strong>✅ Low Risk</strong></div>""", unsafe_allow_html=True)
            except:
                st.error("Could not reach backend.")
    else:
        st.info("No companies loaded yet.")

tab1, tab2, tab3 = st.tabs(["Corpus Browser", "Research Chat", "Risk Dashboard (Manual)"])

# --- TAB 1: Corpus Browser ---
with tab1:
    st.markdown("<h3 style='margin-bottom: 24px;'>Loaded Transcripts</h3>", unsafe_allow_html=True)
    
    if companies_data:
        grouped = df_companies.groupby("company")
        cols = st.columns(3)
        col_idx = 0
        
        for company, group in grouped:
            comp_color = get_company_color(company)
            market_val = group['market'].iloc[0]
            flag = get_market_flag(market_val)
            
            with cols[col_idx % 3]:
                st.markdown(f"""
                <div class="metric-card" style="text-align: left; border-top: 4px solid {comp_color};">
                    <h3 style="margin-top:0; color:#EDEDED;">{company}</h3>
                    <p style="color:#98989D; margin-bottom:16px; font-size:13px; text-transform: uppercase; letter-spacing: 1px;">
                        {flag} MARKET: {market_val}
                    </p>
                    <div style="display:flex; flex-wrap:wrap; gap:8px;">
                """, unsafe_allow_html=True)
                
                quarters_html = ""
                for _, row in group.iterrows():
                    quarters_html += f"<span style='background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:16px; font-size:12px; color:#EDEDED; font-weight:500; border: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;' onmouseover=\"this.style.background='{comp_color}33'\" onmouseout=\"this.style.background='rgba(255,255,255,0.05)'\">{row['year']} {row['quarter']}</span>"
                
                st.markdown(quarters_html + "</div></div>", unsafe_allow_html=True)
            col_idx += 1
    else:
        if backend_connected:
            st.info("No transcripts loaded yet. Please run the ingestion pipeline.")
        else:
            st.error("Could not reach backend to load transcripts.")


# --- TAB 2: Research Chat ---
with tab2:
    st.markdown("<h3 style='margin-bottom: 24px;'>Research Assistant</h3>", unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'<div class="chat-user">{message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bot">{message["content"]}</div>', unsafe_allow_html=True)
            if "sources" in message and message["sources"]:
                with st.expander("View Sources", expanded=False):
                    for src in message["sources"]:
                        comp_color = get_company_color(src['company'])
                        st.markdown(f"""
                        <div style='margin-bottom: 12px; padding-left: 12px; border-left: 3px solid {comp_color}; background: rgba(255,255,255,0.02); padding: 12px; border-radius: 0 8px 8px 0;'>
                            <strong style='color:#EDEDED;'>{src['company']}</strong> 
                            <span style='background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;'>{src['year']} {src['quarter']}</span>
                            <br><span style='color:#98989D; font-family: monospace; font-size: 13px; display: inline-block; margin-top: 8px;'>"{src['excerpt']}..."</span>
                        </div>
                        """, unsafe_allow_html=True)

    if prompt := st.chat_input("Ask a question (e.g. 'Compare JPMorgan and HDFC Q1 revenues')"):
        st.markdown(f'<div class="chat-user">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Analyzing transcripts..."):
            try:
                res = requests.post(f"{API_URL}/ask", json={"question": prompt}, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "No answer found.")
                    sources = data.get("sources", [])
                    
                    st.markdown(f'<div class="chat-bot">{answer}</div>', unsafe_allow_html=True)
                    
                    if sources:
                        with st.expander("View Sources", expanded=False):
                            for src in sources:
                                comp_color = get_company_color(src['company'])
                                st.markdown(f"""
                                <div style='margin-bottom: 12px; padding-left: 12px; border-left: 3px solid {comp_color}; background: rgba(255,255,255,0.02); padding: 12px; border-radius: 0 8px 8px 0;'>
                                    <strong style='color:#EDEDED;'>{src['company']}</strong> 
                                    <span style='background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;'>{src['year']} {src['quarter']}</span>
                                    <br><span style='color:#98989D; font-family: monospace; font-size: 13px; display: inline-block; margin-top: 8px;'>"{src['excerpt']}..."</span>
                                </div>
                                """, unsafe_allow_html=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
                else:
                    if not res.text.strip():
                        st.error(f"Error: Backend returned an empty response (Status {res.status_code}). This usually means the server ran out of memory or crashed.")
                    else:
                        st.error(f"Error: {res.text}")
            except requests.exceptions.ConnectionError as e:
                st.error(f"Could not reach backend. Error: {e}")


# --- TAB 3: Risk Dashboard ---
with tab3:
    st.markdown("<h3 style='margin-bottom: 8px;'>Quantitative Risk Scoring</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#98989D; margin-bottom: 32px;'>Input key financial ratios to predict bankruptcy risk based on the XGBoost model.</p>", unsafe_allow_html=True)
    
    col_input, col_result = st.columns([1.2, 1], gap="large")
    
    with col_input:
        
        with st.form("risk_form"):
            st.markdown("<h4 style='margin-bottom: 16px; margin-top: 0;'>Financial Inputs</h4>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            
            with c1:
                roa = st.number_input("ROA(C) before interest & dep", value=0.5, step=0.01)
                operating_margin = st.number_input("Operating Gross Margin", value=0.5, step=0.01)
                net_value_growth = st.number_input("Continuous Net Value Growth", value=0.5, step=0.01)
                
            with c2:
                debt_ratio = st.number_input("Debt ratio %", value=0.5, step=0.01)
                net_income_flag = st.number_input("Net Income Flag", value=1.0, step=1.0)
                cash_turnover = st.number_input("Cash Turnover Rate", value=0.5, step=0.01)
                
            st.markdown("<br>", unsafe_allow_html=True)
            submit_button = st.form_submit_button("Calculate Risk Score", type="primary", use_container_width=True)

    with col_result:
        st.markdown("<h4 style='margin-bottom: 16px; margin-top: 0;'>Analysis Result</h4>", unsafe_allow_html=True)
        
        if submit_button:
            payload = {
                "ROA(C) before interest and depreciation before interest": roa,
                " Operating Gross Margin": operating_margin,
                " Continuous Net Value Growth Rate": net_value_growth,
                " Debt ratio %": debt_ratio,
                " Net Income Flag": net_income_flag,
                " Cash Turnover Rate": cash_turnover
            }
            
            with st.spinner("Scoring..."):
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
                        
                        if tier == "High":
                            st.markdown("""<div class='callout-danger'><strong>⚠️ High Risk Detected</strong><br>This company exhibits high risk indicators similar to historical bankruptcy patterns.</div>""", unsafe_allow_html=True)
                        elif tier == "Medium":
                            st.markdown("""<div class='callout-warning'><strong>⚠️ Elevated Risk</strong><br>This company shows elevated risk indicators. Monitor closely.</div>""", unsafe_allow_html=True)
                        else:
                            st.markdown("""<div class='callout-success'><strong>✅ Low Risk</strong><br>This company's ratios align with healthy historical benchmarks.</div>""", unsafe_allow_html=True)
                            
                    else:
                        st.error(f"Error: {res.text}")
                except requests.exceptions.ConnectionError as e:
                    st.error(f"Could not reach backend. Error: {e}")
        else:
            st.markdown("<div class='metric-card' style='opacity: 0.5;'>", unsafe_allow_html=True)
            st.markdown("<div class='risk-label'>Risk Tier: Pending</div>", unsafe_allow_html=True)
            st.plotly_chart(plot_risk_gauge(0, "Low"), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Submit the form to generate a score.")

# --- Minimal Footer ---
st.markdown("<div class='minimal-footer'>Built with FastAPI · ChromaDB · Llama 3.3 · XGBoost</div>", unsafe_allow_html=True)
