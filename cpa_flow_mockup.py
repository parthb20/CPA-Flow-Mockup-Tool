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

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #111827; }
    .stApp { background-color: #111827; }
    [data-testid="stSidebar"] { display: none; }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        padding: 15px; border-radius: 8px; border: 2px solid #4b5563; margin: 10px 0;
    }
    .similarity-excellent { border-color: #22c55e; background: rgba(34, 197, 94, 0.1); }
    .similarity-good { border-color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
    .similarity-moderate { border-color: #eab308; background: rgba(234, 179, 8, 0.1); }
    .similarity-poor { border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
    .info-box {
        background: #1f2937; padding: 12px; border-radius: 5px; 
        color: #d1d5db; font-size: 12px; margin: 10px 0;
        border: 1px solid #374151; line-height: 1.6;
    }
    .info-label { color: #9ca3af; font-weight: bold; }
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
            'flow_index', 'similarities', 'loading_done', 'zoom1', 'zoom2', 'screenshot_cache']:
    if key not in st.session_state:
        if key == 'flows':
            st.session_state[key] = []
        elif key == 'flow_index':
            st.session_state[key] = 0
        elif key in ['zoom1', 'zoom2']:
            st.session_state[key] = 100
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

def load_data():
    if st.session_state.data_a is None or st.session_state.data_b is None:
        with st.spinner("📥 Loading data..."):
            data_a = load_csv_from_gdrive(FILE_A_ID)
            data_b = load_json_from_gdrive(FILE_B_ID)
            
            if data_a is None or data_b is None:
                st.error("❌ Failed to load data from Google Drive")
                return False
                
            st.session_state.data_a = data_a
            st.session_state.data_b = data_b
            st.session_state.loading_done = True
    return True

def render_device_preview(content, device, zoom, is_iframe=False, url=""):
    """Render HTML properly at device dimensions with centered scaling"""
    dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
    device_w, device_h = dims[device]
    
    # Container dimensions
    container_w = 1000
    container_h = 600
    
    # Calculate scale to fit in container
    scale_w = container_w / device_w
    scale_h = container_h / device_h
    scale = min(scale_w, scale_h) * 0.85  # 85% to add padding
    
    # Apply zoom
    scale = scale * (zoom / 100)
    
    # Calculate display dimensions
    display_w = int(device_w * scale)
    display_h = int(device_h * scale)
    
    if is_iframe:
        # For external URLs
        html = f"""
        <div style="display: flex; justify-content: center; align-items: center; background: #1f2937; border-radius: 8px; padding: 20px; min-height: {container_h}px;">
            <div style="width: {display_w}px; height: {display_h}px; overflow: auto; border: 2px solid #444; border-radius: 8px; background: white; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                <iframe src="{url}" style="width: {device_w}px; height: {device_h}px; border: none; transform: scale({scale}); transform-origin: 0 0;" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
            </div>
        </div>
        """
    else:
        # For HTML content - render at actual size then scale
        html = f"""
        <div style="display: flex; justify-content: center; align-items: center; background: #1f2937; border-radius: 8px; padding: 20px; min-height: {container_h}px; overflow: hidden;">
            <div style="width: {display_w}px; height: {display_h}px; overflow: auto; border: 2px solid #444; border-radius: 8px; background: white; box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                <div style="width: {device_w}px; height: {device_h}px; transform: scale({scale}); transform-origin: 0 0; overflow: auto;">
                    {content}
                </div>
            </div>
        </div>
        """
    
    return html

def extract_serp_html(serp_data):
    """Extract clean SERP HTML from data"""
    if not serp_data or len(serp_data) == 0:
        return "<div style='padding: 20px; color: #666;'>No SERP data available</div>"
    
    # Get the HTML code
    html_code = serp_data[0].get('code', '')
    
    if not html_code:
        return "<div style='padding: 20px; color: #666;'>No HTML code found</div>"
    
    # Return the HTML as-is - it's already complete with styles
    return html_code

def render_similarity_card(title, data):
    if not data:
        st.error(f"{title}: API Error")
        return
    
    if "error" in data:
        if data.get("status_code") == "no_api_key":
            st.error(f"{title}: Add FASTROUTER_API_KEY to secrets")
        else:
            st.error(f"{title}: API failed")
        return
    
    score = data.get("score", 0)
    reasoning = data.get("reasoning", "")
    
    if score >= 0.8:
        band, color = "excellent", "#22c55e"
    elif score >= 0.6:
        band, color = "good", "#3b82f6"
    elif score >= 0.4:
        band, color = "moderate", "#eab308"
    else:
        band, color = "poor", "#ef4444"
    
    card_html = f"""
    <div class="metric-card similarity-{band}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h4 style="margin: 0; color: #f3f4f6; font-size: 14px;">{title}</h4>
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 24px; font-weight: bold; color: {color};">{score:.0%}</span>
            </div>
        </div>
        <p style="margin:0; color: #9ca3af; font-size: 11px;">{band.upper()}</p>
        <p style="margin:8px 0 0 0; color: #d1d5db; font-size: 11px; line-height: 1.4;">{reasoning}</p>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def calculate_similarity(text1, text2, metric_name):
    if not API_KEY:
        return {"error": "API key missing", "status_code": "no_api_key"}
    
    try:
        response = requests.post(
            "https://orchestrator.fast-router.com/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{
                    "role": "user",
                    "content": f"""Compare these two texts and return ONLY a JSON object with 'score' (0-1) and 'reasoning':

Text 1: {text1[:500]}
Text 2: {text2[:500]}

Return format: {{"score": 0.85, "reasoning": "explanation"}}"""
                }],
                "response_format": {"type": "json_object"}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return json.loads(content)
        return {"error": f"API returned {response.status_code}", "status_code": response.status_code}
    except Exception as e:
        return {"error": str(e), "status_code": "exception"}

def analyze_flow():
    flow = st.session_state.flows[st.session_state.flow_index]
    
    similarities = {
        'kwd_to_ad': calculate_similarity(
            flow['keyword'],
            f"{flow['ad_title']} {flow['ad_description']}",
            "Keyword to Ad"
        ),
        'ad_to_landing': calculate_similarity(
            f"{flow['ad_title']} {flow['ad_description']}",
            flow['landing_text'][:1000],
            "Ad to Landing"
        ),
        'overall': calculate_similarity(
            flow['keyword'],
            flow['landing_text'][:1000],
            "Overall"
        )
    }
    
    st.session_state.similarities = similarities

def get_flow_name(flow):
    return f"{flow['keyword'][:30]} → {flow['landing_domain']}"

def create_sankey():
    flow = st.session_state.flows[st.session_state.flow_index]
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="#1f2937", width=2),
            label=["🔍 Keyword", "📢 SERP Ad", "🌐 Landing Page"],
            color=["#3b82f6", "#8b5cf6", "#10b981"],
            customdata=[flow['keyword'][:40], flow['ad_title'][:40], flow['landing_domain']],
            hovertemplate='%{label}<br>%{customdata}<extra></extra>'
        ),
        link=dict(
            source=[0, 1],
            target=[1, 2],
            value=[1, 1],
            color=["rgba(59, 130, 246, 0.3)", "rgba(139, 92, 246, 0.3)"],
            hovertemplate='Flow<extra></extra>'
        )
    )])
    
    fig.update_layout(
        font=dict(size=14, color='#f3f4f6', family='Arial'),
        plot_bgcolor='#111827',
        paper_bgcolor='#111827',
        height=250,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    return fig

# Main UI
st.title("📊 CPA Flow Analysis")

if not load_data():
    st.stop()

data_a = st.session_state.data_a
data_b = st.session_state.data_b

# Keyword selector
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    keywords = sorted(data_a['Keyword'].dropna().unique())
    selected_kw = st.selectbox(
        "🔍 Select Keyword",
        keywords,
        index=keywords.index(st.session_state.selected_keyword) if st.session_state.selected_keyword in keywords else 0
    )

if selected_kw != st.session_state.selected_keyword:
    st.session_state.selected_keyword = selected_kw
    st.session_state.selected_url = None
    st.session_state.flows = []
    st.session_state.flow_index = 0
    st.session_state.similarities = None

kw_data = data_a[data_a['Keyword'] == selected_kw]

with col2:
    urls = sorted(kw_data['URL'].dropna().unique())
    if urls:
        selected_url = st.selectbox("🌐 Select URL", urls)
        
        if selected_url != st.session_state.selected_url:
            st.session_state.selected_url = selected_url
            st.session_state.flows = []
            st.session_state.flow_index = 0
            st.session_state.similarities = None

with col3:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Analyze", use_container_width=True, type="primary"):
        if st.session_state.selected_url:
            url_data = kw_data[kw_data['URL'] == st.session_state.selected_url].iloc[0]
            
            serp_data = [item for item in data_b if item.get('url') == st.session_state.selected_url]
            
            if serp_data:
                serp_html = extract_serp_html(serp_data)
                
                try:
                    soup = BeautifulSoup(serp_html, 'html.parser')
                    ad_titles = [tag.get_text(strip=True) for tag in soup.find_all(class_='title')]
                    ad_descs = [tag.get_text(strip=True) for tag in soup.find_all(class_='desc')]
                    
                    landing_resp = requests.get(st.session_state.selected_url, timeout=10)
                    landing_soup = BeautifulSoup(landing_resp.text, 'html.parser')
                    landing_text = landing_soup.get_text(separator=' ', strip=True)
                    landing_domain = urlparse(st.session_state.selected_url).netloc
                    
                    st.session_state.flows = [{
                        'keyword': selected_kw,
                        'serp_html': serp_html,
                        'serp_url': st.session_state.selected_url,
                        'ad_title': ad_titles[0] if ad_titles else "No title",
                        'ad_description': ad_descs[0] if ad_descs else "No description",
                        'landing_url': st.session_state.selected_url,
                        'landing_text': landing_text,
                        'landing_domain': landing_domain
                    }]
                    
                    st.session_state.flow_index = 0
                    analyze_flow()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# Display flow
if st.session_state.flows:
    flow = st.session_state.flows[st.session_state.flow_index]
    
    # Flow selector
    if len(st.session_state.flows) > 1:
        flow_names = [get_flow_name(f) for f in st.session_state.flows]
        selected_flow_name = st.selectbox("📋 Select Flow", flow_names, index=st.session_state.flow_index)
        new_index = flow_names.index(selected_flow_name)
        if new_index != st.session_state.flow_index:
            st.session_state.flow_index = new_index
            analyze_flow()
            st.rerun()
    
    # Sankey
    st.plotly_chart(create_sankey(), use_container_width=True)
    
    # Similarity scores
    if st.session_state.similarities:
        cols = st.columns(3)
        with cols[0]:
            render_similarity_card("Match Score", st.session_state.similarities.get('kwd_to_ad'))
        with cols[1]:
            render_similarity_card("Ad → Landing", st.session_state.similarities.get('ad_to_landing'))
        with cols[2]:
            render_similarity_card("Overall Flow", st.session_state.similarities.get('overall'))
    
    # Preview section
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📢 SERP Preview")
        device1 = st.radio("Device", ["mobile", "tablet", "laptop"], horizontal=True, key="device1")
        zoom1 = st.slider("Zoom", 50, 150, st.session_state.zoom1, key="zoom1")
        
        preview_html = render_device_preview(flow['serp_html'], device1, zoom1)
        st.components.v1.html(preview_html, height=650, scrolling=False)
    
    with col2:
        st.markdown("### 🌐 Landing Page Preview")
        device2 = st.radio("Device", ["mobile", "tablet", "laptop"], horizontal=True, key="device2")
        zoom2 = st.slider("Zoom", 50, 150, st.session_state.zoom2, key="zoom2")
        
        preview_html = render_device_preview("", device2, zoom2, is_iframe=True, url=flow['landing_url'])
        st.components.v1.html(preview_html, height=650, scrolling=False)
