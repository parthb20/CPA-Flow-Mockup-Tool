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

# Custom CSS - COMPLETE LIGHT MODE
st.markdown("""
    <style>
    /* Background */
    .main { background-color: #f8fafc !important; }
    .stApp { background-color: #f8fafc !important; }
    [data-testid="stSidebar"] { display: none; }
    
    /* Force light backgrounds everywhere */
    [data-testid="stExpander"],
    [data-testid="stExpander"] > div,
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary {
        background: white !important;
    }
    
    /* All text elements */
    h1, h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {
        color: #0f172a !important;
        font-weight: 500 !important;
        font-size: 16px !important;
    }
    
    h1 { font-weight: 700 !important; font-size: 32px !important; }
    h2 { font-weight: 700 !important; font-size: 26px !important; }
    h3 { font-weight: 700 !important; font-size: 22px !important; }
    
    /* Dropdowns */
    [data-baseweb="select"] { background-color: white !important; }
    [data-baseweb="select"] > div { background-color: white !important; border-color: #cbd5e1 !important; }
    [data-baseweb="select"] * { color: #0f172a !important; font-weight: 500 !important; font-size: 16px !important; }
    [role="listbox"] { background-color: white !important; }
    [role="option"] { background-color: white !important; color: #0f172a !important; }
    [role="option"]:hover { background-color: #f1f5f9 !important; }
    [role="option"][aria-selected="true"] { background-color: #e0f2fe !important; color: #0369a1 !important; }
    
    /* Input fields */
    input, textarea, select {
        background-color: white !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
        font-weight: 500 !important;
        font-size: 16px !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 600 !important;
        font-size: 16px !important;
    }
    .stButton > button:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4) !important;
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background: white !important;
        color: #64748b !important;
        border: 2px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #f8fafc !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    
    /* Checkbox-style buttons */
    .checkbox-btn {
        width: 24px !important;
        height: 24px !important;
        min-width: 24px !important;
        padding: 0 !important;
        border-radius: 3px !important;
        font-size: 14px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background-color: white !important; border-bottom: 2px solid #e2e8f0 !important; }
    .stTabs [data-baseweb="tab"] { color: #475569 !important; background-color: white !important; font-weight: 600 !important; }
    .stTabs [aria-selected="true"] { color: #3b82f6 !important; border-bottom-color: #3b82f6 !important; font-weight: 700 !important; }
    
    /* Metrics - COLORED BOXES */
    [data-testid="stMetric"] {
        background: white;
        padding: 16px;
        border-radius: 8px;
        border: 2px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-weight: 700 !important;
        font-size: 28px !important;
    }
    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Individual metric colors */
    [data-testid="stMetric"]:nth-of-type(1) {
        border-left: 4px solid #8b5cf6;
        background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
    }
    [data-testid="stMetric"]:nth-of-type(2) {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }
    [data-testid="stMetric"]:nth-of-type(3) {
        border-left: 4px solid #10b981;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }
    [data-testid="stMetric"]:nth-of-type(4) {
        border-left: 4px solid #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }
    [data-testid="stMetric"]:nth-of-type(5) {
        border-left: 4px solid #ef4444;
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    }
    
    /* Expander */
    [data-testid="stExpander"] {
        background-color: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
    }
    [data-testid="stExpander"] details {
        background-color: white !important;
    }
    [data-testid="stExpander"] summary {
        background-color: white !important;
        color: #0f172a !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
    }
    [data-testid="stExpander"] summary:hover {
        background-color: #f8fafc !important;
    }
    .streamlit-expanderHeader {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        font-weight: 600 !important;
    }
    .streamlit-expanderHeader:hover {
        background-color: #f8fafc !important;
    }
    .streamlit-expanderContent {
        background-color: white !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
        border-top: none !important;
        padding: 12px !important;
    }
    .streamlit-expanderContent * { 
        color: #0f172a !important; 
        background-color: transparent !important;
    }
    .streamlit-expanderContent [data-testid="stMetricLabel"] { color: #64748b !important; }
    .streamlit-expanderContent [data-testid="stMetricValue"] { color: #0f172a !important; }
    
    /* Radio buttons */
    .stRadio > label { color: #0f172a !important; font-weight: 600 !important; }
    .stRadio [role="radiogroup"] label {
        color: #0f172a !important;
        background-color: white !important;
        border: 1px solid #cbd5e1 !important;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600 !important;
    }
    .stRadio [role="radiogroup"] label:hover {
        background-color: #f1f5f9 !important;
        border-color: #94a3b8 !important;
    }
    
    /* Divider */
    hr { border-color: #e2e8f0 !important; }
    
    
    .info-box {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        padding: 18px; 
        border-radius: 8px; 
        border: 1px solid #bae6fd;
        border-left: 4px solid #3b82f6;
        margin: 15px 0;
        line-height: 1.8;
        font-size: 16px;
        color: #0f172a !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-weight: 500;
    }
    .info-box p, .info-box div, .info-box span {
        color: #0f172a !important;
        background: transparent !important;
    }
    .info-box a {
        color: #3b82f6;
        text-decoration: underline;
        font-weight: 600;
    }
    .info-box a:hover { color: #2563eb; }
    .info-label { 
        font-weight: 700; 
        color: #3b82f6;
        font-size: 16px;
    }
    
    /* Table with visible boundaries */
    .table-header {
        display: flex;
        padding: 14px 8px;
        font-weight: 700;
        font-size: 15px;
        color: #0f172a;
        background: #f1f5f9;
        border-radius: 8px 8px 0 0;
        border: 2px solid #cbd5e1;
        border-bottom: 3px solid #94a3b8;
    }
    .table-row {
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        margin: 6px 0;
        padding: 8px;
        background: white;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    
    .flow-diagram {
        background: white;
        padding: 20px;
        border-radius: 8px;
        border: 2px solid #cbd5e1;
        margin: 15px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
    }
    .flow-step {
        background: #f1f5f9;
        padding: 12px 16px;
        border-radius: 6px;
        border: 2px solid #cbd5e1;
        font-weight: 600;
        color: #0f172a;
        text-align: center;
        flex: 1;
        min-width: 120px;
    }
    .flow-arrow {
        font-size: 24px;
        color: #3b82f6;
        font-weight: 700;
    }
    
    .stSpinner > div { border-top-color: #3b82f6 !important; }
    .stCaptionContainer { color: #475569 !important; font-weight: 500 !important; }
    </style>
""", unsafe_allow_html=True)

# Config
FILE_A_ID = "1BKBE7zW9LWtaReBrft0l-zTo62GSPHQB"
FILE_B_ID = "1QpQhZhXFFpQWm_xhVGDjdpgRM3VMv57L"

try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
except Exception as e:
    API_KEY = ""

# Session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_domain', 'selected_url', 'flows', 
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
        # Try as Google Sheets export
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            # Try direct download
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            response = requests.get(url, timeout=30)
        if response.status_code != 200:
            # Try alternative direct download URL
            url = f"https://drive.google.com/u/0/uc?id={file_id}&export=download"
            response = requests.get(url, timeout=30)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text), dtype=str)
    except Exception as e:
        st.error(f"Error loading CSV: {str(e)}")
        st.error(f"Status code: {response.status_code if 'response' in locals() else 'N/A'}")
        st.error(f"File ID: {file_id}")
        return None

def load_json_from_gdrive(file_id):
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            data = [data]
        return data
    except Exception as e:
        st.error(f"Error loading SERP templates: {str(e)}")
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
    
    # Keyword → Ad
    kwd_to_ad_prompt = f"""Score ad relevance to keyword. Judge meaning, not keyword stuffing. Penalize deceptive content.

KEYWORD: "{keyword}"
AD: "{ad_text}"

**Intent:** TRANSACTIONAL (buy/hire) | NAVIGATIONAL (brand+site) | INFORMATIONAL (how/what) | COMPARISON (best/vs)

**Penalties:**
- Brand mismatch: keyword has brand, ad doesn't → keyword_match≤0.3, topic_match≤0.4, intent_match≤0.5
- Wrong product: ad promotes different core product → topic_match=0.1, final_score≤0.3

**Scores (0.0–1.0):**
KEYWORD_MATCH (15%): Term overlap | 1.0=all | 0.7=most | 0.4=some | 0.0=none
TOPIC_MATCH (35%): Same subject? | 1.0=identical | 0.7=close | 0.4=loose | 0.1=unrelated
INTENT_MATCH (50%): Satisfies intent?
- TRANS: CTA/offer? 1.0=yes | 0.3=no
- NAV: Correct brand? 1.0=yes | 0.1=no
- INFO: Educational? 0.9=yes | 0.3=sales-only
- COMP: Multiple options? 0.9=yes | 0.4=single

**Bands:** 0.8–1.0=excellent | 0.6–0.8=good | 0.4–0.6=moderate | 0.2–0.4=weak | 0.0–0.2=poor

JSON only: {{"intent":"","keyword_match":0.0,"topic_match":0.0,"intent_match":0.0,"final_score":0.0,"band":"","reason":""}}
**Reason:** Max 125 characters explaining the score.
Formula: 0.15×K + 0.35×T + 0.50×I"""
    
    results['kwd_to_ad'] = call_similarity_api(kwd_to_ad_prompt)
    time.sleep(1)
    
    if adv_url and pd.notna(adv_url) and str(adv_url).lower() != 'null' and str(adv_url).strip():
        page_text = fetch_page_content(adv_url)
        
        if page_text:
            # Ad → Page
            ad_to_page_prompt = f"""Score page vs ad promises. Judge meaning, not keyword stuffing. Penalize deceptive content.

AD: "{ad_text}"
PAGE: "{page_text}"

**Penalties:**
- Dead page: error/parking/forced redirect to different site/no real content → ALL=0.0
- Brand hijack: ad brand ≠ page brand AND page is affiliate/comparison/different company → brand_match≤0.2, promise_match≤0.4

**Scores (0.0–1.0):**
TOPIC_MATCH (30%): Same product/service? | 1.0=exact | 0.7=related | 0.4=loose | 0.1=different
BRAND_MATCH (20%): Same company? | 1.0=same brand clearly shown | 0.7=same brand, less prominent | 0.2=different company | 0.0=bait-switch
PROMISE_MATCH (50%): Ad claims delivered on page? 
- Check: same service/offer, CTA available, claims verifiable
- 1.0=all delivered | 0.7=most delivered | 0.4=partially delivered | 0.1=not delivered
- Note: Form-based access still counts as delivered if service is accessible

**Bands:** 0.8–1.0=excellent | 0.6–0.8=good | 0.4–0.6=moderate | 0.2–0.4=weak | 0.0–0.2=poor

JSON only: {{"topic_match":0.0,"brand_match":0.0,"promise_match":0.0,"final_score":0.0,"band":"","reason":""}}
**Reason:** Max 125 characters explaining the score.
Formula: 0.30×T + 0.20×B + 0.50×P"""
            
            results['ad_to_page'] = call_similarity_api(ad_to_page_prompt)
            time.sleep(1)
            
            # Keyword → Page
            kwd_to_page_prompt = f"""Score page relevance to keyword. Judge meaning, not keyword stuffing. Penalize deceptive/thin content.

KEYWORD: "{keyword}"
PAGE: "{page_text}"

**Intent:** TRANSACTIONAL (buy/hire) | NAVIGATIONAL (brand+site) | INFORMATIONAL (how/what) | COMPARISON (best/vs)

**Penalties:**
- NAV mismatch: nav keyword, wrong site → both≤0.2
- Brand mismatch: brand keyword, different brand → both≤0.4
- Thin content: SEO filler/arbitrage → utility_match≤0.3

**Scores (0.0–1.0):**
TOPIC_MATCH (40%): Page covers topic? | 1.0=exact focus | 0.7=close | 0.4=mentioned | 0.1=no
UTILITY_MATCH (60%): Enables user goal?
- TRANS: Product+action? 1.0=yes | 0.3=no
- NAV: Correct destination? 1.0=yes | 0.1=no
- INFO: Teaches topic? 1.0=yes | 0.4=vague
- COMP: Comparison data? 1.0=yes | 0.4=single

Ask: Can user complete their task?

**Bands:** 0.8–1.0=excellent | 0.6–0.8=good | 0.4–0.6=moderate | 0.2–0.4=weak | 0.0–0.2=poor

JSON only: {{"intent":"","topic_match":0.0,"utility_match":0.0,"final_score":0.0,"band":"","reason":""}}
**Reason:** Max 125 characters explaining the score.
Formula: 0.40×T + 0.60×U"""
            
            results['kwd_to_page'] = call_similarity_api(kwd_to_page_prompt)
    
    return results

def get_similarity_label(score):
    """Convert score to simple label with range"""
    if score >= 0.8:
        return "Excellent Match (0.8-1.0)", "#22c55e"
    elif score >= 0.6:
        return "Good Match (0.6-0.8)", "#3b82f6"
    elif score >= 0.4:
        return "Moderate Match (0.4-0.6)", "#eab308"
    elif score >= 0.2:
        return "Weak Match (0.2-0.4)", "#f97316"
    else:
        return "Poor Match (0.0-0.2)", "#ef4444"

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
    reason = data.get('reason', 'N/A')
    
    label, color = get_similarity_label(score)
    
    with st.expander("📊 How This Score Is Calculated", expanded=False):
        st.markdown(calculation_details, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="margin: 20px 0;">
        <h3 style="margin:0 0 16px 0; color: #0f172a; font-size: 20px; font-weight: 700;">{title}</h3>
        <div style="display: inline-block; padding: 16px 24px; border-radius: 8px; border: 3px solid {color}; background: linear-gradient(135deg, {color}15, {color}08);">
            <div style="font-size: 48px; font-weight: 700; color: {color}; line-height: 1;">{score:.1%}</div>
        </div>
        <p style="margin: 12px 0 4px 0; color: {color}; font-size: 16px; font-weight: 700;">{label}</p>
        <p style="margin: 8px 0 0 0; color: #475569; font-size: 14px; font-weight: 500; max-width: 600px;">{reason}</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Detailed Score Breakdown"):
        for key, value in data.items():
            if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
            elif key not in ['final_score', 'band', 'reason']:
                st.caption(f"**{key.replace('_', ' ').title()}:** {value}")

def generate_serp_mockup(flow_data, serp_templates):
    """Generate SERP HTML"""
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    
    if serp_templates and len(serp_templates) > 0:
        try:
            html = serp_templates[0].get('code', '')
            
            html = html.replace('min-device-width', 'min-width')
            html = html.replace('max-device-width', 'max-width')
            html = html.replace('min-device-height', 'min-height')
            html = html.replace('max-device-height', 'max-height')
            html = re.sub(r'min-height\s*:\s*calc\(100[sv][vh]h?[^)]*\)\s*;?', '', html, flags=re.IGNORECASE)
            
            html = re.sub(r'Sponsored results for:\s*"[^"]*"', f'Sponsored results for: "{keyword}"', html)
            html = re.sub(r'(<div class="url">)[^<]*(</div>)', f'\\1{ad_url}\\2', html, count=1)
            html = re.sub(r'(<div class="title">)[^<]*(</div>)', f'\\1{ad_title}\\2', html, count=1)
            html = re.sub(r'(<div class="desc">)[^<]*(</div>)', f'\\1{ad_desc}\\2', html, count=1)
            
            return html
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    return ""

def render_device_preview(content, device, use_url=False):
    """Render HTML content or URL with realistic device UI chrome
    
    Args:
        content: HTML content string or URL
        device: 'mobile', 'tablet', or 'laptop'
        use_url: If True, treats content as URL and uses iframe src instead of srcdoc
    """
    # Real device dimensions to match actual devices
    if device == 'mobile':
        device_w = 390  # iPhone 14 Pro width
        container_height = 844  # iPhone 14 Pro height (tall portrait)
        frame_style = "border-radius: 40px; border: 10px solid #000000;"
        scale = 0.7  # Scale down to fit better
        
        # Mobile status bar and browser chrome
        device_chrome = f"""
        <!-- Status Bar -->
        <div style="background: #000; color: white; padding: 6px 20px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 500;">
            <div>9:41</div>
            <div style="display: flex; gap: 4px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋 100%</span>
            </div>
        </div>
        <!-- Browser Bar -->
        <div style="background: #f7f7f7; border-bottom: 1px solid #d1d1d1; padding: 8px 12px; display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; background: white; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid #e0e0e0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #666; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">beenverified.com</span>
                <span style="font-size: 16px;">🔄</span>
            </div>
        </div>
        """
        
        bottom_nav = """
        <!-- Bottom Navigation -->
        <div style="position: absolute; bottom: 0; left: 0; right: 0; background: #f7f7f7; border-top: 1px solid #d1d1d1; padding: 8px; display: flex; justify-content: space-around; align-items: center;">
            <div style="text-align: center; font-size: 20px;">◀️</div>
            <div style="text-align: center; font-size: 20px;">▶️</div>
            <div style="text-align: center; font-size: 20px;">↻</div>
            <div style="text-align: center; font-size: 20px;">⊞</div>
        </div>
        """
        
    elif device == 'tablet':
        device_w = 820  # iPad Air width
        container_height = 1180  # iPad Air height (portrait mode)
        frame_style = "border-radius: 16px; border: 12px solid #1f2937;"
        scale = 0.5  # Scale down to fit
        
        # Tablet UI chrome
        device_chrome = f"""
        <!-- Status Bar -->
        <div style="background: #000; color: white; padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500;">
            <div style="display: flex; gap: 12px;">
                <span>9:41 AM</span>
                <span>Wed Jan 12</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋 100%</span>
            </div>
        </div>
        <!-- Browser Bar -->
        <div style="background: #f0f0f0; border-bottom: 1px solid #d0d0d0; padding: 12px 16px; display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px;">◀️</span>
            <span style="font-size: 20px;">▶️</span>
            <span style="font-size: 20px;">↻</span>
            <div style="flex: 1; background: white; border-radius: 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;">
                <span style="font-size: 18px;">🔒</span>
                <span style="color: #666; font-size: 15px; flex: 1;">beenverified.com</span>
            </div>
            <span style="font-size: 20px;">⊞</span>
            <span style="font-size: 20px;">⋮</span>
        </div>
        """
        
        bottom_nav = ""
        
    else:  # laptop
        device_w = 1440  # Standard laptop width
        container_height = 900  # Standard laptop height (16:10)
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        scale = 0.5  # Scale down to fit
        
        # Laptop browser chrome
        device_chrome = f"""
        <!-- Browser Window Chrome -->
        <div style="background: #e8e8e8; padding: 12px 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #d0d0d0;">
            <div style="display: flex; gap: 8px;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f57;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #28c840;"></div>
            </div>
            <span style="font-size: 18px; margin-left: 8px;">◀️</span>
            <span style="font-size: 18px;">▶️</span>
            <span style="font-size: 18px; margin-right: 8px;">↻</span>
            <div style="flex: 1; background: white; border-radius: 6px; padding: 8px 16px; display: flex; align-items: center; gap: 12px; border: 1px solid #d0d0d0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #333; font-size: 14px; flex: 1;">https://beenverified.com</span>
                <span style="font-size: 16px;">⭐</span>
            </div>
            <span style="font-size: 18px; margin-left: 8px;">⊞</span>
            <span style="font-size: 18px;">⋮</span>
        </div>
        """
        
        bottom_nav = ""
    
    # Calculate scaled dimensions for display
    display_w = int(device_w * scale)
    display_h = int(container_height * scale)
    
    if use_url:
        # Use iframe src for direct URL loading (for landing pages)
        iframe_tag = f'<iframe src="{content}" style="width: 100%; height: 100%; border: none;"></iframe>'
        
        # Create device wrapper with chrome
        full_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width={device_w}, initial-scale=1.0">
            <style>
                body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
                .device-chrome {{ width: 100%; background: white; position: fixed; top: 0; left: 0; right: 0; z-index: 100; }}
                .content-area {{ position: absolute; top: {'90px' if device == 'mobile' else '60px' if device == 'tablet' else '52px'}; bottom: {'50px' if device == 'mobile' else '0'}; left: 0; right: 0; }}
                .bottom-nav {{ position: fixed; bottom: 0; left: 0; right: 0; background: #f7f7f7; border-top: 1px solid #d1d1d1; padding: 8px; display: flex; justify-content: space-around; z-index: 100; }}
            </style>
        </head>
        <body>
            <div class="device-chrome">
                {device_chrome}
            </div>
            <div class="content-area">
                {iframe_tag}
            </div>
            {f'<div class="bottom-nav">{bottom_nav}</div>' if device == 'mobile' else ''}
        </body>
        </html>
        """
    else:
        # Use srcdoc for HTML content (for SERP)
        full_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width={device_w}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <style>
                body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
                .device-chrome {{ width: 100%; background: white; }}
                .content-area {{ height: calc(100vh - {'90px' if device == 'mobile' else '60px' if device == 'tablet' else '52px'}); overflow-y: auto; }}
            </style>
        </head>
        <body>
            <div class="device-chrome">
                {device_chrome}
            </div>
            <div class="content-area">
                {content}
            </div>
            {bottom_nav if device == 'mobile' else ''}
        </body>
        </html>
        """
    
    escaped = full_content.replace("'", "&apos;").replace('"', '&quot;')
    
    html = f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 20px; 
                background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); 
                border-radius: 12px; min-height: {display_h + 40}px;">
        <div style="width: {display_w}px; height: {display_h}px; 
                    {frame_style} overflow: hidden; background: #000;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2); position: relative;">
            <iframe srcdoc='{escaped}' 
                    style="width: {device_w}px; height: {container_height}px; border: none; 
                           transform: scale({scale}); transform-origin: 0 0; display: block; background: white;"
                    sandbox="allow-same-origin allow-scripts allow-popups allow-forms">
            </iframe>
        </div>
    </div>
    """
    
    return html, display_h + 60

def make_url_clickable(url):
    """Convert URL string to clickable hyperlink"""
    if not url or pd.isna(url) or str(url).lower() == 'null':
        return 'N/A'
    url_display = url[:60] + "..." if len(str(url)) > 60 else url
    return f'<a href="{url}" target="_blank" style="color:#3b82f6; text-decoration:underline; font-weight:600;">{url_display}</a>'

# Auto-load data
if not st.session_state.loading_done:
    with st.spinner("Loading data..."):
        st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
        st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
        st.session_state.loading_done = True

st.title("📊 CPA Flow Analysis")

if st.session_state.data_a is not None and len(st.session_state.data_a) > 0:
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
            
            st.markdown("### 📊 Overall Campaign Stats")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Impressions", f"{safe_int(campaign_df['impressions'].sum()):,}")
            c2.metric("Clicks", f"{safe_int(campaign_df['clicks'].sum()):,}")
            c3.metric("Conversions", f"{safe_int(campaign_df['conversions'].sum()):,}")
            c4.metric("CTR", f"{avg_ctr:.2f}%")
            c5.metric("CVR", f"{avg_cvr:.2f}%")
            
            st.divider()
            st.subheader("🔑 Step 1: Pick a Keyword")
            
            st.info("👉 **What you need to do:** Choose which keyword you want to analyze.\n\n📊 **Chart View:** Visual bubble chart showing keyword performance. Larger bubbles = more clicks. Click any bubble to select that keyword.\n\n📋 **Table View:** Detailed data table with all metrics. Use filters to find specific keywords. Click the checkbox to select a keyword.\n\n💡 **Table Colors:** 🟢 Green = Above average CTR/CVR | 🔴 Red = Below average CTR/CVR")
            
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
                
                # Add bright, visible average lines with labels
                fig.add_hline(y=avg_cvr, line_dash="dash", line_color="#ef4444", line_width=3, opacity=0.8,
                             annotation_text=f"AVG CVR: {avg_cvr:.2f}%", 
                             annotation_position="right",
                             annotation=dict(font_size=14, font_color="#ef4444", font_weight="bold"))
                fig.add_vline(x=avg_ctr, line_dash="dash", line_color="#3b82f6", line_width=3, opacity=0.8,
                             annotation_text=f"AVG CTR: {avg_ctr:.2f}%",
                             annotation_position="top",
                             annotation=dict(font_size=14, font_color="#3b82f6", font_weight="bold"))
                
                fig.update_layout(
                    xaxis_title="<b>CTR (%)</b>", 
                    yaxis_title="<b>CVR (%)</b>", 
                    height=500,
                    showlegend=False, 
                    plot_bgcolor='white', 
                    paper_bgcolor='white',
                    font=dict(color='#0f172a', size=16, family="Arial, sans-serif", weight='bold'), 
                    hovermode='closest',
                    xaxis=dict(gridcolor='#e2e8f0', title_font=dict(size=18, color='#0f172a', weight='bold')), 
                    yaxis=dict(gridcolor='#e2e8f0', title_font=dict(size=18, color='#0f172a', weight='bold'))
                )
                
                event = st.plotly_chart(fig, use_container_width=True, key="bubble", on_select="rerun")
                
                if event and 'selection' in event and 'points' in event['selection'] and len(event['selection']['points']) > 0:
                    point = event['selection']['points'][0]
                    if 'customdata' in point and point['customdata']:
                        clicked_keyword = point['customdata'][0]
                        if clicked_keyword != st.session_state.selected_keyword:
                            st.session_state.selected_keyword = clicked_keyword
                            st.session_state.selected_domain = None
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
                    
                    if cols[0].button("■" if is_selected else "□", key=f"kw_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_keyword = row['keyword_term']
                            st.session_state.selected_domain = None
                            st.session_state.selected_url = None
                            st.session_state.similarities = {}
                            st.rerun()
                    
                    cols[1].markdown(f"<div class='table-row' style='padding:8px;'>{row['keyword_term']}</div>", unsafe_allow_html=True)
                    cols[2].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['impressions']):,}</div>", unsafe_allow_html=True)
                    cols[3].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['clicks']):,}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['conversions']):,}</div>", unsafe_allow_html=True)
                    
                    ctr_bg = 'rgba(22, 163, 74, 0.15)' if row['ctr'] >= avg_ctr else 'rgba(220, 38, 38, 0.15)'
                    ctr_color = '#16a34a' if row['ctr'] >= avg_ctr else '#dc2626'
                    cols[5].markdown(f"<div class='table-row' style='text-align:center; background:{ctr_bg}; color:{ctr_color}; font-weight:700;'>{row['ctr']:.2f}%</div>", unsafe_allow_html=True)
                    
                    cvr_bg = 'rgba(22, 163, 74, 0.15)' if row['cvr'] >= avg_cvr else 'rgba(220, 38, 38, 0.15)'
                    cvr_color = '#16a34a' if row['cvr'] >= avg_cvr else '#dc2626'
                    cols[6].markdown(f"<div class='table-row' style='text-align:center; background:{cvr_bg}; color:{cvr_color}; font-weight:700;'>{row['cvr']:.2f}%</div>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword:
                st.divider()
                st.subheader(f"🔗 Step 2: Pick Publisher Domain")
                
                st.info("👉 **What you need to do:** Now pick which publisher domain your ad appeared on. Different publisher domains can give different results.\n\n💡 **Colors explained:** 🟢 Green = Above average performance | 🔴 Red = Below average performance")
                
                keyword_domains = campaign_df[campaign_df['keyword_term'] == st.session_state.selected_keyword]
                domain_agg = keyword_domains.groupby('publisher_domain').agg({
                    'clicks': 'sum', 'conversions': 'sum', 'impressions': 'sum'
                }).reset_index()
                domain_agg['ctr'] = domain_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                domain_agg['cvr'] = domain_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                f1, f2, f3 = st.columns(3)
                domain_filter = f1.selectbox("Show me:", ['all publisher domains', 'best performers', 'worst performers'], key='domain_filter')
                domain_limit = f2.selectbox("How many:", [5, 10, 25, 50], key='domain_limit')
                domain_sort = f3.selectbox("Sort by:", ['clicks', 'conversions', 'ctr', 'cvr', 'impressions'], key='domain_sort')
                
                filtered_domains = domain_agg.copy()
                if domain_filter == 'best performers':
                    filtered_domains = filtered_domains[(filtered_domains['ctr'] >= avg_ctr) & (filtered_domains['cvr'] >= avg_cvr)]
                elif domain_filter == 'worst performers':
                    filtered_domains = filtered_domains[(filtered_domains['ctr'] < avg_ctr) & (filtered_domains['cvr'] < avg_cvr)]
                
                filtered_domains = filtered_domains.sort_values(domain_sort, ascending=False).head(domain_limit).reset_index(drop=True)
                
                st.markdown("""
                <div class="table-header">
                    <div style="flex: 0.4;"></div>
                    <div style="flex: 3.5;">Publisher Domain</div>
                    <div style="flex: 1.2; text-align: center;">Impr.</div>
                    <div style="flex: 1.2; text-align: center;">Clicks</div>
                    <div style="flex: 1.2; text-align: center;">Conv.</div>
                    <div style="flex: 1.2; text-align: center;">CTR %</div>
                    <div style="flex: 1.2; text-align: center;">CVR %</div>
                </div>
                """, unsafe_allow_html=True)
                
                for idx, row in filtered_domains.iterrows():
                    cols = st.columns([0.4, 3.5, 1.2, 1.2, 1.2, 1.2, 1.2])
                    is_selected = (row['publisher_domain'] == st.session_state.selected_domain)
                    
                    if cols[0].button("■" if is_selected else "□", key=f"domain_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_domain = row['publisher_domain']
                            st.session_state.selected_url = None
                            st.session_state.similarities = {}
                            st.rerun()
                    
                    display_domain = row['publisher_domain'][:45] + '...' if len(str(row['publisher_domain'])) > 45 else row['publisher_domain']
                    cols[1].markdown(f"<div class='table-row' style='padding:8px;'>{display_domain}</div>", unsafe_allow_html=True)
                    cols[2].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['impressions']):,}</div>", unsafe_allow_html=True)
                    cols[3].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['clicks']):,}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['conversions']):,}</div>", unsafe_allow_html=True)
                    
                    ctr_bg = 'rgba(22, 163, 74, 0.15)' if row['ctr'] >= avg_ctr else 'rgba(220, 38, 38, 0.15)'
                    ctr_color = '#16a34a' if row['ctr'] >= avg_ctr else '#dc2626'
                    cols[5].markdown(f"<div class='table-row' style='text-align:center; background:{ctr_bg}; color:{ctr_color}; font-weight:700;'>{row['ctr']:.2f}%</div>", unsafe_allow_html=True)
                    
                    cvr_bg = 'rgba(22, 163, 74, 0.15)' if row['cvr'] >= avg_cvr else 'rgba(220, 38, 38, 0.15)'
                    cvr_color = '#16a34a' if row['cvr'] >= avg_cvr else '#dc2626'
                    cols[6].markdown(f"<div class='table-row' style='text-align:center; background:{cvr_bg}; color:{cvr_color}; font-weight:700;'>{row['cvr']:.2f}%</div>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword and st.session_state.selected_domain:
                st.divider()
                st.subheader(f"🔗 Step 3: Pick Publisher URL")
                
                st.info("👉 **What you need to do:** Now pick which specific publisher URL your ad appeared on. Different URLs within the same domain can give different results.\n\n💡 **Colors explained:** 🟢 Green = Above average performance | 🔴 Red = Below average performance")
                
                domain_urls = campaign_df[
                    (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                    (campaign_df['publisher_domain'] == st.session_state.selected_domain)
                ]
                url_agg = domain_urls.groupby('publisher_url').agg({
                    'clicks': 'sum', 'conversions': 'sum', 'impressions': 'sum'
                }).reset_index()
                url_agg['ctr'] = url_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                url_agg['cvr'] = url_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                f1, f2, f3 = st.columns(3)
                url_filter = f1.selectbox("Show me:", ['all publisher URLs', 'best performers', 'worst performers'], key='url_filter')
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
                    <div style="flex: 3.5;">Publisher URL</div>
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
                    
                    if cols[0].button("■" if is_selected else "□", key=f"url_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_url = row['publisher_url']
                            st.session_state.similarities = {}
                            st.rerun()
                    
                    display_url = row['publisher_url'][:45] + '...' if len(str(row['publisher_url'])) > 45 else row['publisher_url']
                    cols[1].markdown(f"<div class='table-row' style='padding:8px;'>{display_url}</div>", unsafe_allow_html=True)
                    cols[2].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['impressions']):,}</div>", unsafe_allow_html=True)
                    cols[3].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['clicks']):,}</div>", unsafe_allow_html=True)
                    cols[4].markdown(f"<div class='table-row' style='text-align:center;'>{int(row['conversions']):,}</div>", unsafe_allow_html=True)
                    
                    ctr_bg = 'rgba(22, 163, 74, 0.15)' if row['ctr'] >= avg_ctr else 'rgba(220, 38, 38, 0.15)'
                    ctr_color = '#16a34a' if row['ctr'] >= avg_ctr else '#dc2626'
                    cols[5].markdown(f"<div class='table-row' style='text-align:center; background:{ctr_bg}; color:{ctr_color}; font-weight:700;'>{row['ctr']:.2f}%</div>", unsafe_allow_html=True)
                    
                    cvr_bg = 'rgba(22, 163, 74, 0.15)' if row['cvr'] >= avg_cvr else 'rgba(220, 38, 38, 0.15)'
                    cvr_color = '#16a34a' if row['cvr'] >= avg_cvr else '#dc2626'
                    cols[6].markdown(f"<div class='table-row' style='text-align:center; background:{cvr_bg}; color:{cvr_color}; font-weight:700;'>{row['cvr']:.2f}%</div>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword and st.session_state.selected_domain and st.session_state.selected_url:
                st.divider()
                
                flows = campaign_df[
                    (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                    (campaign_df['publisher_domain'] == st.session_state.selected_domain) &
                    (campaign_df['publisher_url'] == st.session_state.selected_url)
                ].sort_values('clicks', ascending=False).head(5)
                
                st.session_state.flows = flows.to_dict('records')
                
                if len(st.session_state.flows) > 0:
                    st.subheader("📊 Step 4: Analyze The Flow")
                    
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
                    
                    # Flow description with actual values
                    keyword_val = current_flow.get('keyword_term', 'N/A')
                    pub_domain_val = current_flow.get('publisher_domain', 'N/A')
                    pub_url_val = current_flow.get('publisher_url', 'N/A')
                    dest_val = current_flow.get('reporting_destination_url', 'N/A')
                    serp_template_val = current_flow.get('serp_template_id', current_flow.get('SERP_template_id', 'Template 1'))
                    
                    st.markdown(f"""
                    <div class="info-box">
                        <strong>🔄 What is This Flow?</strong><br><br>
                        <strong>Keyword:</strong> {keyword_val}<br>
                        <strong>Publisher Domain:</strong> {pub_domain_val}<br>
                        <strong>Publisher URL:</strong> {make_url_clickable(pub_url_val)}<br>
                        <strong>SERP Template:</strong> {serp_template_val}<br>
                        <strong>Landing Page:</strong> {make_url_clickable(dest_val)}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Visual Flow Diagram
                    keyword_short = keyword_val[:20] + '...' if len(str(keyword_val)) > 20 else keyword_val
                    pub_domain_short = pub_domain_val[:20] + '...' if len(str(pub_domain_val)) > 20 else pub_domain_val
                    pub_url_short = pub_url_val[:20] + '...' if len(str(pub_url_val)) > 20 else pub_url_val
                    dest_short = dest_val[:20] + '...' if len(str(dest_val)) > 20 else dest_val
                    serp_short = str(serp_template_val)[:15] + '...' if len(str(serp_template_val)) > 15 else str(serp_template_val)
                    
                    st.markdown(f"""
                    <div class="flow-diagram">
                        <div class="flow-step">🔍 Keyword<br><small>{keyword_short}</small></div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">🌐 Domain<br><small>{pub_domain_short}</small></div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">📰 URL<br><small>{pub_url_short}</small></div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">📄 SERP<br><small>{serp_short}</small></div>
                        <div class="flow-arrow">→</div>
                        <div class="flow-step">🎯 Landing<br><small>{dest_short}</small></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Similarity Score Explanation
                    st.info("💡 **Similarity Score Ranges:**\n\n• 🟢 **0.8 - 1.0:** Excellent Match\n• 🔵 **0.6 - 0.8:** Good Match\n• 🟡 **0.4 - 0.6:** Moderate Match\n• 🟠 **0.2 - 0.4:** Weak Match\n• 🔴 **0.0 - 0.2:** Poor Match")
                    
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
                            <div class="info-label">Search Term:</div> {current_flow.get("keyword_term", "N/A")}<br><br>
                            <div class="info-label">Ad Headline:</div> {current_flow.get("ad_title", "N/A")}<br><br>
                            <div class="info-label">Ad Text:</div> {current_flow.get("ad_description", "N/A")[:100]}<br><br>
                            <div class="info-label">Display URL:</div> {make_url_clickable(current_flow.get("ad_display_url", "N/A"))}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("### 🔗 Keyword → Ad Similarity Score")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('kwd_to_ad'),
                                "Does the ad match what the user searched for?",
                                "<strong>What we check:</strong><br>" +
                                "• Keyword Match (15%): Word overlap<br>" +
                                "• Topic Match (35%): Same subject?<br>" +
                                "• Intent Match (50%): Satisfies search intent?<br><br>" +
                                "<strong>Penalty:</strong> Brand mismatch or wrong product = lower scores"
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
                            # Display URL info
                            st.markdown(f"""
                            <div class="info-box">
                                📍 <strong>Landing Page URL:</strong> {make_url_clickable(dest_url)}<br>
                                <small>Loading page directly in iframe (some sites may block embedding)</small>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Render using iframe src (direct URL loading)
                            try:
                                preview_html, height = render_device_preview(dest_url, device2, use_url=True)
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                            except Exception as e:
                                st.error(f"⚠️ Could not render page in iframe. Site may block embedding.")
                                st.info(f"💡 Visit directly: {make_url_clickable(dest_url)}")
                        else:
                            st.warning("⚠️ No landing page URL found")
                    
                    with card2_right:
                        st.markdown("### 🔗 Ad → Page Similarity Score")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('ad_to_page'),
                                "Does the page deliver what the ad promised?",
                                "<strong>What we check:</strong><br>" +
                                "• Topic Match (30%): Same product/service?<br>" +
                                "• Brand Match (20%): Same company?<br>" +
                                "• Promise Match (50%): Ad claims delivered?<br><br>" +
                                "<strong>Penalty:</strong> Dead page, brand switch, or bait-and-switch = lower scores"
                            )
                        
                        st.markdown("### 🔗 Keyword → Page Similarity Score")
                        if st.session_state.similarities:
                            render_similarity_card(
                                "Match Score", 
                                st.session_state.similarities.get('kwd_to_page'),
                                "Does the page help the user complete their task?",
                                "<strong>What we check:</strong><br>" +
                                "• Topic Match (40%): Page covers the topic?<br>" +
                                "• Utility Match (60%): Can user complete their goal?<br><br>" +
                                "<strong>Penalty:</strong> Wrong site, brand mismatch, or thin content = lower scores"
                            )
                else:
                    st.warning("No data found")
else:
    st.error("❌ Could not load data")
    st.info("""
    **Troubleshooting:**
    1. Make sure the Google Drive file is shared with "Anyone with the link can view"
    2. Verify the file is a CSV or Google Sheet
    3. Check that the file ID is correct: `1otRz-kxnlFvqFzCT_54gdxZ1kca1MIgK`
    """)
