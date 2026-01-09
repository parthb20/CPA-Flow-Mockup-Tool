import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, quote
import re
from io import StringIO
import time
import base64

# Page config
st.set_page_config(page_title="CPA Flow Analysis", page_icon="📊", layout="wide")

# Custom CSS - COMPLETE LIGHT MODE with DARKER FONTS
st.markdown("""
    <style>
    /* Background */
    .main { background-color: #f8fafc; }
    .stApp { background-color: #f8fafc; }
    [data-testid="stSidebar"] { display: none; }
    
    /* All text elements - DARKER for better visibility */
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {
        color: #0f172a !important;
        font-weight: 500 !important;
    }
    
    /* Headings even bolder */
    h1, h2, h3 {
        font-weight: 700 !important;
    }
    
    /* Dropdowns and select boxes */
    [data-baseweb="select"] {
        background-color: white !important;
    }
    [data-baseweb="select"] > div {
        background-color: white !important;
        border-color: #cbd5e1 !important;
    }
    [data-baseweb="select"] * {
        color: #0f172a !important;
        font-weight: 500 !important;
    }
    
    /* Input fields */
    input, textarea, select {
        background-color: white !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
        font-weight: 500 !important;
    }
    
    /* ALL Buttons - Light Mode */
    .stButton > button {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #3b82f6 !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #2563eb !important;
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: white !important;
        border-bottom: 2px solid #e2e8f0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #475569 !important;
        background-color: white !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #3b82f6 !important;
        border-bottom-color: #3b82f6 !important;
        font-weight: 700 !important;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-weight: 600 !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        font-weight: 600 !important;
    }
    .streamlit-expanderContent {
        background-color: white !important;
        border: 1px solid #e2e8f0 !important;
        border-top: none !important;
    }
    
    /* Radio buttons */
    .stRadio > label {
        color: #0f172a !important;
        font-weight: 600 !important;
    }
    .stRadio [role="radiogroup"] label {
        color: #0f172a !important;
        background-color: white !important;
        border: 1px solid #cbd5e1 !important;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600 !important;
    }
    .stRadio [role="radiogroup"] label:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
    }
    
    /* Divider */
    hr {
        border-color: #e2e8f0 !important;
    }
    
    /* Custom cards */
    .metric-card {
        background: white;
        padding: 15px; 
        border-radius: 8px; 
        border: 2px solid #e2e8f0;
        margin: 10px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .similarity-excellent { border-color: #22c55e; background: rgba(34, 197, 94, 0.08); }
    .similarity-good { border-color: #3b82f6; background: rgba(59, 130, 246, 0.08); }
    .similarity-moderate { border-color: #eab308; background: rgba(234, 179, 8, 0.08); }
    .similarity-poor { border-color: #ef4444; background: rgba(239, 68, 68, 0.08); }
    
    .info-box {
        background: white;
        padding: 16px; 
        border-radius: 8px; 
        border: 1px solid #cbd5e1;
        border-left: 4px solid #3b82f6;
        margin: 15px 0;
        line-height: 1.8;
        font-size: 15px;
        color: #0f172a;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-weight: 500;
    }
    .info-label { 
        font-weight: 700; 
        color: #3b82f6;
    }
    
    .table-header {
        display: flex;
        padding: 12px 8px;
        border-bottom: 2px solid #cbd5e1;
        margin-bottom: 10px;
        font-weight: 700;
        font-size: 13px;
        color: #334155;
        background: white;
        border-radius: 6px 6px 0 0;
        border: 1px solid #e2e8f0;
        border-bottom: 2px solid #cbd5e1;
    }
    
    .explanation-box {
        background: white;
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #c4b5fd;
        border-left: 3px solid #8b5cf6;
        margin: 10px 0;
        font-size: 13px;
        line-height: 1.6;
        color: #0f172a;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-weight: 500;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #3b82f6 !important;
    }
    
    /* Caption */
    .stCaptionContainer {
        color: #475569 !important;
        font-weight: 500 !important;
    }
    
    /* Code blocks */
    .stCodeBlock {
        background-color: #f1f5f9 !important;
        border: 1px solid #cbd5e1 !important;
    }
    code {
        color: #0f172a !important;
        background-color: #f1f5f9 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Config
FILE_A_ID = "1bwdj-rAAp6I1SbO27BTFD2eLiv6V5vsB"
FILE_B_ID = "1QpQhZhXFFpQWm_xhVGDjdpgRM3VMv57L"

try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
except Exception as e:
    API_KEY = ""

# Session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_url', 'flows', 
            'flow_index', 'similarities', 'loading_done', 'screenshot_cache']:
    if key not in st.session_state:
        if key == 'flows':
            st.session_state[key] = []
        elif key == 'flow_index':
            st.session_state[key] = 0
        elif key == 'loading_done':
            st.session_state[key] = False
        elif key == 'screenshot_cache':
            st.session_state[key] = {}
        else:
            st.session_state[key] = None

def load_csv_from_gdrive(file_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            response = requests.get(url, timeout=30)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text), dtype=str)
    except:
        return None

def load_json_from_gdrive(file_id):
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except:
        return None

def safe_float(value, default=0.0):
    try:
        return float(value) if pd.notna(value) else default
    except:
        return default

def safe_int(value, default=0):
    try:
        return int(float(value)) if pd.notna(value) else default
    except:
        return default

def calculate_metrics(df):
    df['impressions'] = df['impressions'].apply(safe_float)
    df['clicks'] = df['clicks'].apply(safe_float)
    df['conversions'] = df['conversions'].apply(safe_float)
    df['ctr'] = df.apply(lambda x: (x['clicks'] / x['impressions'] * 100) if x['impressions'] > 0 else 0, axis=1)
    df['cvr'] = df.apply(lambda x: (x['conversions'] / x['clicks'] * 100) if x['clicks'] > 0 else 0, axis=1)
    return df

def calculate_campaign_averages(df):
    total_impressions = df['impressions'].sum()
    total_clicks = df['clicks'].sum()
    total_conversions = df['conversions'].sum()
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
    return avg_ctr, avg_cvr

def get_quadrant(ctr, cvr, avg_ctr, avg_cvr):
    if ctr >= avg_ctr and cvr >= avg_cvr:
        return 'High Performing', '#22c55e'
    elif ctr >= avg_ctr and cvr < avg_cvr:
        return 'Low CVR', '#eab308'
    elif ctr < avg_ctr and cvr >= avg_cvr:
        return 'Niche', '#3b82f6'
    else:
        return 'Underperforming', '#ef4444'

def call_similarity_api(prompt):
    if not API_KEY:
        return {
            "error": True,
            "status_code": "no_api_key",
            "body": "FASTROUTER_API_KEY not found in Streamlit secrets"
        }
    response = requests.post(
        "https://go.fastrouter.ai/api/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        json={
            "model": "anthropic/claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000
        },
        timeout=30
    )

    if response.status_code != 200:
        return {
            "error": True,
            "status_code": response.status_code,
            "body": response.text
        }

    raw = response.json()['choices'][0]['message']['content']

    try:
        match = re.search(r'\{[\s\S]*\}', raw)
        return json.loads(match.group())
    except:
        return {
            "error": True,
            "status_code": "bad_json",
            "body": raw[:500]
        }

def fetch_page_content(url):
    if not url or pd.isna(url) or str(url).lower() == 'null':
        return ""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
            element.decompose()
        return soup.get_text(separator=' ', strip=True)[:3000]
    except:
        return ""

def calculate_similarities(flow_data):
    keyword = flow_data.get('keyword_term', '')
    ad_title = flow_data.get('ad_title', '')
    ad_desc = flow_data.get('ad_description', '')
    ad_text = f"{ad_title} {ad_desc}"
    adv_url = flow_data.get('reporting_destination_url', '')
    
    results = {}
    
    kwd_to_ad_prompt = f"""Evaluate keyword-to-ad match.
KEYWORD: "{keyword}"
AD: "{ad_text}"
Score (0.0-1.0): KEYWORD_MATCH (15%), TOPIC_MATCH (35%), INTENT_MATCH (50%)
Return JSON: {{"intent":"","keyword_match":0.0,"topic_match":0.0,"intent_match":0.0,"final_score":0.0,"band":"excellent/good/moderate/weak/poor","reason":"brief"}}"""
    
    results['kwd_to_ad'] = call_similarity_api(kwd_to_ad_prompt)
    time.sleep(1)
    
    if adv_url and pd.notna(adv_url) and str(adv_url).lower() != 'null' and str(adv_url).strip():
        page_text = fetch_page_content(adv_url)
        
        if page_text:
            ad_to_page_prompt = f"""Evaluate ad-to-page match.
AD: "{ad_text}"
PAGE: "{page_text}"
Score (0.0-1.0): TOPIC_MATCH (30%), BRAND_MATCH (20%), PROMISE_MATCH (50%)
Return JSON: {{"topic_match":0.0,"brand_match":0.0,"promise_match":0.0,"final_score":0.0,"band":"excellent/good/moderate/weak/poor","reason":"brief"}}"""
            
            results['ad_to_page'] = call_similarity_api(ad_to_page_prompt)
            time.sleep(1)
            
            kwd_to_page_prompt = f"""Evaluate keyword-to-page match.
KEYWORD: "{keyword}"
PAGE: "{page_text}"
Score (0.0-1.0): TOPIC_MATCH (40%), ANSWER_QUALITY (60%)
Return JSON: {{"intent":"","topic_match":0.0,"answer_quality":0.0,"final_score":0.0,"band":"excellent/good/moderate/weak/poor","reason":"brief"}}"""
            
            results['kwd_to_page'] = call_similarity_api(kwd_to_page_prompt)
    
    return results

def render_similarity_card(title, data, explanation, calculation_details):
    if not data:
        st.error(f"{title}: API Error")
        return
    
    if "error" in data:
        if data.get("status_code") == "no_api_key":
            st.error(f"{title}: Add FASTROUTER_API_KEY to secrets")
        else:
            st.error(f"{title}: API failed")
            st.code({
                "status_code": data.get("status_code"),
                "body": data.get("body")
            })
            return
    
    score = data.get('final_score', 0)
    band = data.get('band', 'unknown')
    reason = data.get('reason', 'N/A')
    
    if score >= 0.8:
        css_class, color = 'similarity-excellent', '#22c55e'
    elif score >= 0.6:
        css_class, color = 'similarity-good', '#3b82f6'
    elif score >= 0.4:
        css_class, color = 'similarity-moderate', '#eab308'
    else:
        css_class, color = 'similarity-poor', '#ef4444'
    
    # Show calculation explanation first
    st.markdown(f"""
    <div class="explanation-box">
        <strong>📊 How This Score Is Calculated:</strong><br>
        {calculation_details}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card {css_class}">
        <h4 style="margin:0; color: #475569; font-size: 12px; font-weight: 700;">{title}</h4>
        <h2 style="margin: 8px 0; color: {color}; font-weight: 700;">{score:.1%}</h2>
        <p style="margin:0; color: #475569; font-size: 11px; font-weight: 600;">{band.upper()}</p>
        <p style="margin:8px 0 4px 0; color: #334155; font-size: 10px; font-weight: 500;">{reason[:80]}</p>
        <p style="margin:8px 0 0 0; color: #64748b; font-size: 9px; font-style: italic; font-weight: 500;">{explanation}</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Detailed Score Breakdown"):
        for key, value in data.items():
            if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
            elif key not in ['final_score', 'band', 'reason']:
                st.caption(f"**{key.replace('_', ' ').title()}:** {value}")

def generate_serp_mockup(flow_data, serp_templates):
    """Use actual SERP HTML with keyword/ad replacement"""
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    
    if serp_templates and len(serp_templates) > 0:
        try:
            html = serp_templates[0].get('code', '')
            
            # Replace keyword in header
            html = re.sub(
                r'(Sponsored results for:\s*["\'])([^"\']*?)(["\'])', 
                f'\\1{keyword}\\3', 
                html
            )
            
            # Replace ad details
            html = re.sub(r'(<div class="url">)[^<]*(</div>)', f'\\1{ad_url}\\2', html, count=1)
            html = re.sub(r'(<div class="title">)[^<]*(</div>)', f'\\1{ad_title}\\2', html, count=1)
            html = re.sub(r'(<div class="desc">)[^<]*(</div>)', f'\\1{ad_desc}\\2', html, count=1)
            
            return html
        except Exception as e:
            pass
    
    # Fallback
    return f"""<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; background: #fff; }}
.header-text {{ color: #70757a; font-size: 13px; margin-bottom: 20px; }}
.url {{ color: #202124; font-size: 14px; }}
.title {{ color: #1a0dab; font-size: 20px; margin: 5px 0; line-height: 1.3; }}
.desc {{ color: #4d5156; font-size: 14px; line-height: 1.58; margin-top: 4px; }}
.ad-badge {{ display: inline-block; padding: 2px 6px; background: #f1f3f4; border-radius: 3px; font-size: 11px; color: #5f6368; margin-bottom: 8px; }}
</style>
</head><body>
<div class="header-text">Sponsored results for: "{keyword}"</div>
<div class="ad-badge">Ad</div>
<div class="url">{ad_url}</div>
<div class="title">{ad_title}</div>
<div class="desc">{ad_desc}</div>
</body></html>"""

def render_device_preview(content, device):
    """Render at ACTUAL device width - no scaling, let responsive design work"""
    # Real device widths - matching actual devices
    dims = {
        'mobile': 393,      # iPhone 14 Pro actual width
        'tablet': 820,      # iPad Air width
        'laptop': 1440      # MacBook Pro width
    }
    device_w = dims[device]
    
    # Container height - fixed for scrolling
    container_height = 700
    
    # Device-specific frame styling
    if device == 'mobile':
        frame_style = "border-radius: 30px; border: 12px solid #94a3b8;"
    elif device == 'tablet':
        frame_style = "border-radius: 20px; border: 14px solid #94a3b8;"
    else:
        frame_style = "border-radius: 8px; border: 8px solid #94a3b8;"
    
    # Properly encode content for srcdoc - escape HTML entities
    import html as html_lib
    encoded_content = html_lib.escape(content)
    
    # Render at ACTUAL width - this lets the website's responsive CSS work properly
    html = f"""
    <div style="display: flex; justify-content: center; align-items: center; 
                background: #e2e8f0; border-radius: 12px; padding: 30px; 
                min-height: {container_height + 80}px; overflow: hidden;">
        <div style="width: {device_w}px; height: {container_height}px; 
                    {frame_style}
                    box-shadow: 0 20px 60px rgba(0,0,0,0.2); 
                    overflow: hidden; 
                    background: white; position: relative;">
            <iframe srcdoc="{encoded_content}" 
                    style="width: 100%; height: 100%; border: none; display: block; margin: 0; padding: 0;"
                    sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
                    scrolling="yes">
            </iframe>
        </div>
    </div>
    """
    
    return html, container_height + 110
# Auto-load data
if not st.session_state.loading_done:
    with st.spinner("Loading data..."):
        st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
        st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
        st.session_state.loading_done = True

st.title("📊 CPA Flow Analysis")

if st.session_state.data_a is not None:
    df = st.session_state.data_a
    
    col1, col2 = st.columns(2)
    with col1:
        advertisers = ['-- Select Advertiser --'] + sorted(df['Advertiser_Name'].dropna().unique().tolist())
        selected_advertiser = st.selectbox("Advertiser", advertisers)
    
    if selected_advertiser and selected_advertiser != '-- Select Advertiser --':
        with col2:
            campaigns = ['-- Select Campaign --'] + sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique().tolist())
            selected_campaign = st.selectbox("Campaign", campaigns)
        
        if selected_campaign and selected_campaign != '-- Select Campaign --':
            campaign_df = df[(df['Advertiser_Name'] == selected_advertiser) & (df['Campaign_Name'] == selected_campaign)].copy()
            campaign_df = calculate_metrics(campaign_df)
            avg_ctr, avg_cvr = calculate_campaign_averages(campaign_df)
            
            st.divider()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Impressions", f"{safe_int(campaign_df['impressions'].sum()):,}")
            c2.metric("Clicks", f"{safe_int(campaign_df['clicks'].sum()):,}")
            c3.metric("Conversions", f"{safe_int(campaign_df['conversions'].sum()):,}")
            c4.metric("CTR", f"{avg_ctr:.2f}%")
            c5.metric("CVR", f"{avg_cvr:.2f}%")
            
            st.divider()
            st.subheader("🔑 Step 1: Pick a Keyword")
            st.markdown("""
            <div class="info-box">
                👉 <strong>What you need to do:</strong> Choose which keyword you want to check. 
                You can click on bubbles in the chart OR use the table below. <br><br>
                💡 <strong>Colors explained:</strong> <span style="color:#22c55e">●</span> Green = Above average performance | <span style="color:#ef4444">●</span> Red = Below average performance
            </div>
            """, unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📊 Chart View", "📋 Table View"])
            
            keyword_agg = campaign_df.groupby('keyword_term').agg({
                'impressions': 'sum', 'clicks': 'sum', 'conversions': 'sum'
            }).reset_index()
            keyword_agg['ctr'] = keyword_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
            keyword_agg['cvr'] = keyword_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
            
            with tab1:
                bubble_data = keyword_agg.nlargest(20, 'clicks').reset_index(drop=True)
                
                fig = go.Figure()
                for idx, row in bubble_data.iterrows():
                    quadrant, color = get_quadrant(row['ctr'], row['cvr'], avg_ctr, avg_cvr)
                    fig.add_trace(go.Scatter(
                        x=[row['ctr']], y=[row['cvr']], mode='markers',
                        marker=dict(size=max(20, min(70, row['clicks']/10)), color=color, 
                                   line=dict(width=2, color='white')),
                        name=row['keyword_term'],
                        hovertemplate='<b>%{fullData.name}</b><br>CTR: %{x:.2f}%<br>CVR: %{y:.2f}%<br>' + 
                                     f"Impressions: {int(row['impressions'])}<br>Clicks: {int(row['clicks'])}<br>Conversions: {int(row['conversions'])}<extra></extra>",
                        customdata=[[row['keyword_term']]]
                    ))
                
                fig.add_hline(y=avg_cvr, line_dash="dash", line_color="gray", opacity=0.5)
                fig.add_vline(x=avg_ctr, line_dash="dash", line_color="gray", opacity=0.5)
                fig.update_layout(xaxis_title="CTR (%)", yaxis_title="CVR (%)", height=400,
                    showlegend=False, plot_bgcolor='white', paper_bgcolor='white',
                    font=dict(color='#0f172a', size=12, family="Arial, sans-serif"), hovermode='closest',
                    xaxis=dict(gridcolor='#e2e8f0', title_font=dict(size=14, color='#0f172a')), 
                    yaxis=dict(gridcolor='#e2e8f0', title_font=dict(size=14, color='#0f172a')))
                
                event = st.plotly_chart(fig, use_container_width=True, key="bubble", on_select="rerun")
                
                if event and 'selection' in event and 'points' in event['selection'] and len(event['selection']['points']) > 0:
                    point = event['selection']['points'][0]
                    if 'customdata' in point and point['customdata']:
                        clicked_keyword = point['customdata'][0]
                        if clicked_keyword != st.session_state.selected_keyword:
                            st.session_state.selected_keyword = clicked_keyword
                            st.session_state.selected_url = None
                            st.session_state.similarities = {}
                            st.rerun()
            
            with tab2:
                f1, f2, f3 = st.columns(3)
                keyword_filter = f1.selectbox("Show me:", ['all keywords', 'best performers', 'worst performers'], key='kw_filter')
                keyword_limit = f2.selectbox("How many:", [5, 10, 25, 50], key='kw_limit')
                keyword_sort = f3.selectbox("Sort by:", ['clicks', 'conversions', 'ctr', 'cvr', 'impressions'], key='kw_sort')
                
                filtered_keywords = keyword_agg.copy()
                if keyword_filter == 'best performers':
                    filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] >= avg_ctr) & (filtered_keywords['cvr'] >= avg_cvr)]
                elif keyword_filter == 'worst performers':
                    filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] < avg_ctr) & (filtered_keywords['cvr'] < avg_cvr)]
                
                filtered_keywords = filtered_keywords.sort_values(keyword_sort, ascending=False).head(keyword_limit).reset_index(drop=True)
                
                st.markdown("""
                <div class="table-header">
                    <div style="flex: 0.4;"></div>
                    <div style="flex: 3.5;">Keyword</div>
                    <div style="flex: 1.2; text-align: center;">Impr.</div>
                    <div style="flex: 1.2; text-align: center;">Clicks</div>
                    <div style="flex: 1.2; text-align: center;">Conv.</div>
                    <div style="flex: 1.2; text-align: center;">CTR %</div>
                    <div style="flex: 1.2; text-align: center;">CVR %</div>
                </div>
                """, unsafe_allow_html=True)
                
                for idx, row in filtered_keywords.iterrows():
                    cols = st.columns([0.4, 3.5, 1.2, 1.2, 1.2, 1.2, 1.2])
                    is_selected = (row['keyword_term'] == st.session_state.selected_keyword)
                    if cols[0].button("✓" if is_selected else "○", key=f"kw_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_keyword = row['keyword_term']
                            st.session_state.selected_url = None
                            st.session_state.similarities = {}
                            st.rerun()
                    cols[1].write(row['keyword_term'])
                    cols[2].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['impressions']):,}</div>", unsafe_allow_html=True)
                    cols[3].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['clicks']):,}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['conversions']):,}</div>", unsafe_allow_html=True)
                    ctr_color = '#16a34a' if row['ctr'] >= avg_ctr else '#dc2626'
                    cols[5].markdown(f"<div style='text-align:center;color:{ctr_color};font-weight:700;'>{row['ctr']:.2f}%</div>", unsafe_allow_html=True)
                    cvr_color = '#16a34a' if row['cvr'] >= avg_cvr else '#dc2626'
                    cols[6].markdown(f"<div style='text-align:center;color:{cvr_color};font-weight:700;'>{row['cvr']:.2f}%</div>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword:
                st.divider()
                st.subheader(f"🔗 Step 2: Pick Where The Ad Showed")
                st.markdown(f"""
                <div class="info-box">
                    👉 <strong>What you need to do:</strong> Now pick which website your ad appeared on. 
                    Different websites can give different results. <br><br>
                    💡 <strong>Colors explained:</strong> <span style="color:#16a34a">●</span> Green = Above average performance | <span style="color:#dc2626">●</span> Red = Below average performance
                </div>
                """, unsafe_allow_html=True)
                
                keyword_urls = campaign_df[campaign_df['keyword_term'] == st.session_state.selected_keyword]
                url_agg = keyword_urls.groupby('publisher_url').agg({
                    'clicks': 'sum', 'conversions': 'sum', 'impressions': 'sum'
                }).reset_index()
                url_agg['ctr'] = url_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                url_agg['cvr'] = url_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                f1, f2, f3 = st.columns(3)
                url_filter = f1.selectbox("Show me:", ['all websites', 'best performers', 'worst performers'], key='url_filter')
                url_limit = f2.selectbox("How many:", [5, 10, 25, 50], key='url_limit')
                url_sort = f3.selectbox("Sort by:", ['clicks', 'conversions', 'ctr', 'cvr', 'impressions'], key='url_sort')
                
                filtered_urls = url_agg.copy()
                if url_filter == 'best performers':
                    filtered_urls = filtered_urls[(filtered_urls['ctr'] >= avg_ctr) & (filtered_urls['cvr'] >= avg_cvr)]
                elif url_filter == 'worst performers':
                    filtered_urls = filtered_urls[(filtered_urls['ctr'] < avg_ctr) & (filtered_urls['cvr'] < avg_cvr)]
                
                filtered_urls = filtered_urls.sort_values(url_sort, ascending=False).head(url_limit).reset_index(drop=True)
                
                st.markdown("""
                <div class="table-header">
                    <div style="flex: 0.4;"></div>
                    <div style="flex: 3.5;">Website</div>
                    <div style="flex: 1.2; text-align: center;">Impr.</div>
                    <div style="flex: 1.2; text-align: center;">Clicks</div>
                    <div style="flex: 1.2; text-align: center;">Conv.</div>
                    <div style="flex: 1.2; text-align: center;">CTR %</div>
                    <div style="flex: 1.2; text-align: center;">CVR %</div>
                </div>
                """, unsafe_allow_html=True)
                
                for idx, row in filtered_urls.iterrows():
                    cols = st.columns([0.4, 3.5, 1.2, 1.2, 1.2, 1.2, 1.2])
                    is_selected = (row['publisher_url'] == st.session_state.selected_url)
                    if cols[0].button("✓" if is_selected else "○", key=f"url_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_url = row['publisher_url']
                            st.session_state.similarities = {}
                            st.rerun()
                    display_url = row['publisher_url'][:45] + '...' if len(str(row['publisher_url'])) > 45 else row['publisher_url']
                    cols[1].write(display_url)
                    cols[2].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['impressions']):,}</div>", unsafe_allow_html=True)
                    cols[3].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['clicks']):,}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div style='text-align:center; color:#0f172a; font-weight:500;'>{int(row['conversions']):,}</div>", unsafe_allow_html=True)
                    ctr_color = '#16a34a' if row['ctr'] >= avg_ctr else '#dc2626'
                    cols[5].markdown(f"<div style='text-align:center;color:{ctr_color};font-weight:700;'>{row['ctr']:.2f}%</div>", unsafe_allow_html=True)
                    cvr_color = '#16a34a' if row['cvr'] >= avg_cvr else '#dc2626'
                    cols[6].markdown(f"<div style='text-align:center;color:{cvr_color};font-weight:700;'>{row['cvr']:.2f}%</div>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword and st.session_state.selected_url:
                st.divider()
                
                flows = campaign_df[
                    (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                    (campaign_df['publisher_url'] == st.session_state.selected_url)
                ].sort_values('clicks', ascending=False).head(5)
                
                st.session_state.flows = flows.to_dict('records')
                
                if len(st.session_state.flows) > 0:
                    st.subheader("📊 Step 3: Analyze The Flow")
                    
                    # Explain what a flow is
                    st.markdown("""
                    <div class="info-box">
                        <strong>🔄 What is a "Flow"?</strong><br>
                        A <strong>Flow</strong> represents one complete user journey, which includes:<br>
                        • <strong>1 Keyword</strong> (what the user searched for)<br>
                        • <strong>1 Publisher URL</strong> (the website where the ad appeared)<br>
                        • <strong>1 SERP Template</strong> (how the ad looked in search results)<br>
                        • <strong>1 Advertiser Landing Page</strong> (where the user went after clicking)<br><br>
                        Each flow represents a unique combination of these 4 elements. Different combinations can perform differently!
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("""
                    <div class="info-box">
                        💡 <strong>Understanding Similarity Scores:</strong><br>
                        We calculate 3 similarity scores to check if everything in your flow matches properly:<br>
                        • <span style="color:#16a34a">■</span> <strong>80-100%</strong> = Excellent | <span style="color:#3b82f6">■</span> <strong>60-80%</strong> = Good<br>
                        • <span style="color:#eab308">■</span> <strong>40-60%</strong> = Needs improvement | <span style="color:#dc2626">■</span> <strong>Below 40%</strong> = Fix immediately
                    </div>
                    """, unsafe_allow_html=True)
                    
                    nav_cols = st.columns(min(5, len(st.session_state.flows)))
                    
                    for i, flow in enumerate(st.session_state.flows[:5]):
                        with nav_cols[i]:
                            is_selected = i == st.session_state.flow_index
                            if st.button(f"Flow {i+1}\n{safe_int(flow.get('clicks',0))} clicks\n{safe_float(flow.get('cvr',0)):.1f}% CVR", 
                                        key=f"flow_{i}", type="primary" if is_selected else "secondary"):
                                st.session_state.flow_index = i
                                st.session_state.similarities = {}
                                st.rerun()
                    
                    current_flow = st.session_state.flows[st.session_state.flow_index]
                    
                    if not st.session_state.similarities:
                        if not API_KEY:
                            st.warning("⚠️ API key not set up. Contact your admin to add FASTROUTER_API_KEY.")
                        else:
                            with st.spinner("Calculating similarity scores..."):
                                st.session_state.similarities = calculate_similarities(current_flow)

                    st.divider()
                    
                    # Card 1: SERP
                    st.subheader("🔍 Search Results Page")
                    st.caption("How your ad appears in search results")
                    
                    card1_left, card1_right = st.columns([7, 3])
                    
                    with card1_left:
                        device1 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev1', index=0)
                        serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
                        preview_html, height = render_device_preview(serp_html, device1)
                        st.components.v1.html(preview_html, height=height, scrolling=False)
                    
                    with card1_right:
                        st.markdown(f"""
                        <div class="info-box">
                            <div class="info-label">Search Term:</div> {current_flow.get('keyword_term', 'N/A')}<br><br>
                            <div class="info-label">Ad Headline:</div> {current_flow.get('ad_title', 'N/A')}<br><br>
                            <div class="info-label">Ad Text:</div> {current_flow.get('ad_description', 'N/A')[:100]}<br><br>
                            <div class="info-label">Display URL:</div> {current_flow.get('ad_display_url', 'N/A')}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("**Keyword → Ad Similarity Score**")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('kwd_to_ad'),
                                "Compares the user's search term with your ad copy",
                                "We compare the <strong>keyword</strong> with <strong>ad title + description</strong>.<br>" +
                                "Formula: 15% keyword match + 35% topic match + 50% intent match = Final Score"
                            )
                    
                    st.divider()
                    
                    # Card 2: Landing Page
                    st.subheader("🎯 Landing Page")
                    st.caption("Where users go after clicking")
                    
                    card2_left, card2_right = st.columns([7, 3])
                    
                    with card2_left:
                        device2 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev2', index=0)
                        dest_url = current_flow.get('reporting_destination_url', '')
                        
                        if dest_url and pd.notna(dest_url) and str(dest_url).lower() != 'null':
                            st.markdown(f"🔗 [Open in New Tab]({dest_url})")
                            
                            with st.spinner("Loading page..."):
                                try:
                                    response = requests.get(dest_url, timeout=10, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                    })
                                    if response.status_code == 200:
                                        landing_html = response.text
                                        preview_html, height = render_device_preview(landing_html, device2)
                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                    else:
                                        st.error(f"⚠️ Could not load page (Error: {response.status_code})")
                                except Exception as e:
                                    st.error(f"⚠️ Could not load page. Try the link above.")
                        else:
                            st.warning("⚠️ No landing page URL found")
                    
                    with card2_right:
                        st.markdown("**Keyword → Page Similarity Score**")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('kwd_to_page'),
                                "Compares the user's search term with landing page content",
                                "We compare the <strong>keyword</strong> with <strong>landing page text</strong>.<br>" +
                                "Formula: 40% topic match + 60% answer quality = Final Score"
                            )
                        
                        st.markdown("**Ad → Page Similarity Score**")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('ad_to_page'),
                                "Compares ad promises with landing page content",
                                "We compare <strong>ad copy</strong> with <strong>landing page text</strong>.<br>" +
                                "Formula: 30% topic match + 20% brand match + 50% promise match = Final Score"
                            )
                else:
                    st.warning("No data found")
else:
    st.error("❌ Could not load data")

