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
    .render-container {
        display: flex; 
        justify-content: center; 
        align-items: center;
        padding: 20px; 
        background: #1f2937; 
        border-radius: 8px;
        height: 600px; 
        overflow: hidden; 
        position: relative;
    }
    .device-frame {
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        border-radius: 8px;
        overflow: hidden;
        background: white;
    }
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
    st.sidebar.error(f"❌ API Key error: {str(e)}")

# Session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_url', 'flows', 
            'flow_index', 'similarities', 'loading_done', 'zoom1', 'zoom2', 'screenshot_cache',
            'show_serp_modal', 'show_landing_modal']:
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
        elif key in ['show_serp_modal', 'show_landing_modal']:
            st.session_state[key] = False
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

import json, re

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

def get_screenshot(url):
    """Get screenshot using screenshotone.com API"""
    if url in st.session_state.screenshot_cache:
        return st.session_state.screenshot_cache[url]
    
    try:
        api_url = f"https://api.screenshotone.com/take?access_key=XpP0JW6EU5SA&url={quote(url)}&viewport_width=1440&viewport_height=900&device_scale_factor=1&format=jpg&image_quality=80&block_ads=true&block_cookie_banners=true&block_trackers=true&cache=true&cache_ttl=2592000"
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200 and len(response.content) > 5000:
            img_base64 = base64.b64encode(response.content).decode()
            st.session_state.screenshot_cache[url] = img_base64
            return img_base64
    except:
        pass
    
    return None

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

def render_similarity_card(title, data):
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
    
    st.markdown(f"""
    <div class="metric-card {css_class}">
        <h4 style="margin:0; color: #d1d5db; font-size: 12px;">{title}</h4>
        <h2 style="margin: 8px 0; color: {color};">{score:.1%}</h2>
        <p style="margin:0; color: #9ca3af; font-size: 11px;">{band.upper()}</p>
        <p style="margin:8px 0 0 0; color: #d1d5db; font-size: 10px;">{reason[:80]}</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Score Breakdown"):
        for key, value in data.items():
            if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
            elif key not in ['final_score', 'band', 'reason']:
                st.caption(f"**{key.replace('_', ' ').title()}:** {value}")

def generate_serp_mockup(flow_data, serp_templates):
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    
    if serp_templates and len(serp_templates) > 0:
        try:
            html = serp_templates[0].get('code', '')
            html = re.sub(r'<div class="header_text">Sponsored results for: "[^"]*"</div>', 
                         f'<div class="header_text">Sponsored results for: "{keyword}"</div>', html)
            html = re.sub(r'<div class="url">[^<]*</div>', f'<div class="url">{ad_url}</div>', html, count=1)
            html = re.sub(r'<div class="title">[^<]*</div>', f'<div class="title">{ad_title}</div>', html, count=1)
            html = re.sub(r'<div class="desc">[^<]*</div>', f'<div class="desc">{ad_desc}</div>', html, count=1)
            return html
        except:
            pass
    
    return f"""<!DOCTYPE html><html><head><style>
body {{ margin: 0; padding: 40px 20px; font-family: Arial, sans-serif; background: #fff; }}
.ad-container {{ max-width: 600px; margin: 0 auto; }}
.url {{ color: #1a73e8; font-size: 14px; margin-bottom: 2px; }}
.title {{ color: #1a0dab; font-size: 20px; margin: 4px 0 8px; line-height: 1.3; cursor: pointer; font-weight: 400; }}
.title:hover {{ text-decoration: underline; }}
.desc {{ color: #4d5156; font-size: 14px; line-height: 1.58; }}
.ad-badge {{ display: inline-block; padding: 2px 6px; background: #f1f3f4; border-radius: 3px; font-size: 11px; color: #5f6368; margin-bottom: 8px; }}
</style></head><body>
<div class="ad-container">
<div class="ad-badge">Ad</div>
<div class="url">{ad_url}</div>
<div class="title">{ad_title}</div>
<div class="desc">{ad_desc}</div>
</div>
</body></html>"""

def render_device_preview(content, device, zoom, is_iframe=False, url=""):
    """Render with proper centered scaling based on device"""
    dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
    device_w, device_h = dims[device]
    
    # Container size
    container_w = 1200
    container_h = 550
    
    # Calculate scale to fit nicely in container
    if device == 'mobile':
        target_display_h = 450  # Target display height for mobile
    elif device == 'tablet':
        target_display_h = 480
    else:  # laptop
        target_display_h = 500
    
    base_scale = target_display_h / device_h
    
    # Apply user zoom
    final_scale = base_scale * (zoom / 100)
    
    # Calculate final display dimensions
    display_w = int(device_w * final_scale)
    display_h = int(device_h * final_scale)
    
    if is_iframe:
        inner_content = f'<iframe src="{url}" width="{device_w}" height="{device_h}" style="border:none; background:white;" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>'
    else:
        inner_content = content
    
    html = f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 20px; background: #1f2937; border-radius: 8px; height: {container_h}px; overflow: hidden;">
        <div style="box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius: 8px; overflow: hidden; background: white;">
            <div style="width: {device_w}px; height: {device_h}px; transform: scale({final_scale}); transform-origin: top left;">
                {inner_content}
            </div>
        </div>
    </div>
    """
    return html, container_h + 40
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
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CTR", f"{avg_ctr:.2f}%")
            c2.metric("CVR", f"{avg_cvr:.2f}%")
            c3.metric("Clicks", f"{safe_int(campaign_df['clicks'].sum()):,}")
            c4.metric("Conversions", f"{safe_int(campaign_df['conversions'].sum()):,}")
            
            st.divider()
            st.subheader("🔑 Keyword Selection")
            
            tab1, tab2 = st.tabs(["📊 Bubble Chart", "📋 Table View"])
            
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
                                     f"Clicks: {int(row['clicks'])}<extra></extra>",
                        customdata=[[row['keyword_term']]]
                    ))
                
                fig.add_hline(y=avg_cvr, line_dash="dash", line_color="gray", opacity=0.5)
                fig.add_vline(x=avg_ctr, line_dash="dash", line_color="gray", opacity=0.5)
                fig.update_layout(xaxis_title="CTR (%)", yaxis_title="CVR (%)", height=400,
                    showlegend=False, plot_bgcolor='#1f2937', paper_bgcolor='#1f2937',
                    font=dict(color='white'), hovermode='closest',
                    xaxis=dict(gridcolor='#374151'), yaxis=dict(gridcolor='#374151'))
                
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
                keyword_filter = f1.selectbox("Filter", ['all', 'best', 'worst'], key='kw_filter')
                keyword_limit = f2.selectbox("Show", [5, 10, 25, 50], key='kw_limit')
                keyword_sort = f3.selectbox("Sort", ['clicks', 'ctr', 'cvr'], key='kw_sort')
                
                filtered_keywords = keyword_agg.copy()
                if keyword_filter == 'best':
                    filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] >= avg_ctr) & (filtered_keywords['cvr'] >= avg_cvr)]
                elif keyword_filter == 'worst':
                    filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] < avg_ctr) & (filtered_keywords['cvr'] < avg_cvr)]
                
                filtered_keywords = filtered_keywords.sort_values(keyword_sort, ascending=False).head(keyword_limit).reset_index(drop=True)
                
                for idx, row in filtered_keywords.iterrows():
                    cols = st.columns([0.5, 4, 1.5, 1.5, 1.5])
                    is_selected = (row['keyword_term'] == st.session_state.selected_keyword)
                    if cols[0].button("✓" if is_selected else "○", key=f"kw_{idx}", use_container_width=True):
                        
                        if not is_selected:
                            st.session_state.selected_keyword = row['keyword_term']
                            st.session_state.selected_url = None
                            st.session_state.similarities = {}
                            st.rerun()
                    cols[1].write(row['keyword_term'])
                    cols[2].write(f"{int(row['clicks']):,}")
                    ctr_color = '#00ff00' if row['ctr'] >= avg_ctr else '#ff4444'
                    cols[3].markdown(f"<span style='color:{ctr_color}'>{row['ctr']:.2f}%</span>", unsafe_allow_html=True)
                    cvr_color = '#00ff00' if row['cvr'] >= avg_cvr else '#ff4444'
                    cols[4].markdown(f"<span style='color:{cvr_color}'>{row['cvr']:.2f}%</span>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword:
                st.divider()
                st.subheader(f"🔗 URLs for: {st.session_state.selected_keyword}")
                
                keyword_urls = campaign_df[campaign_df['keyword_term'] == st.session_state.selected_keyword]
                url_agg = keyword_urls.groupby('publisher_url').agg({
                    'clicks': 'sum', 'conversions': 'sum', 'impressions': 'sum'
                }).reset_index()
                url_agg['ctr'] = url_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                url_agg['cvr'] = url_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                f1, f2, f3 = st.columns(3)
                url_filter = f1.selectbox("Filter", ['all', 'best', 'worst'], key='url_filter')
                url_limit = f2.selectbox("Show", [5, 10, 25, 50], key='url_limit')
                url_sort = f3.selectbox("Sort", ['clicks', 'ctr', 'cvr'], key='url_sort')
                
                filtered_urls = url_agg.copy()
                if url_filter == 'best':
                    filtered_urls = filtered_urls[(filtered_urls['ctr'] >= avg_ctr) & (filtered_urls['cvr'] >= avg_cvr)]
                elif url_filter == 'worst':
                    filtered_urls = filtered_urls[(filtered_urls['ctr'] < avg_ctr) & (filtered_urls['cvr'] < avg_cvr)]
                
                filtered_urls = filtered_urls.sort_values(url_sort, ascending=False).head(url_limit).reset_index(drop=True)
                
                for idx, row in filtered_urls.iterrows():
                    cols = st.columns([0.5, 4, 1.5, 1.5, 1.5])
                    is_selected = (row['publisher_url'] == st.session_state.selected_url)
                    if cols[0].button("✓" if is_selected else "○", key=f"url_{idx}", use_container_width=True):
                        if not is_selected:
                            st.session_state.selected_url = row['publisher_url']
                            st.session_state.similarities = {}
                            st.rerun()
                    display_url = row['publisher_url'][:60] + '...' if len(str(row['publisher_url'])) > 60 else row['publisher_url']
                    cols[1].write(display_url)
                    cols[2].write(f"{int(row['clicks']):,}")
                    ctr_color = '#00ff00' if row['ctr'] >= avg_ctr else '#ff4444'
                    cols[3].markdown(f"<span style='color:{ctr_color}'>{row['ctr']:.2f}%</span>", unsafe_allow_html=True)
                    cvr_color = '#00ff00' if row['cvr'] >= avg_cvr else '#ff4444'
                    cols[4].markdown(f"<span style='color:{cvr_color}'>{row['cvr']:.2f}%</span>", unsafe_allow_html=True)
            
            if st.session_state.selected_keyword and st.session_state.selected_url:
                st.divider()
                
                flows = campaign_df[
                    (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                    (campaign_df['publisher_url'] == st.session_state.selected_url)
                ].sort_values('clicks', ascending=False).head(5)
                
                st.session_state.flows = flows.to_dict('records')
                
                if len(st.session_state.flows) > 0:
                    st.subheader("📈 Flow Statistics")
                    nav_cols = st.columns(5)
                    
                    for i, flow in enumerate(st.session_state.flows):
                        with nav_cols[i]:
                            is_selected = i == st.session_state.flow_index
                            if st.button(f"Flow {i+1}\n{safe_int(flow.get('clicks',0))} clicks\nCTR: {safe_float(flow.get('ctr',0)):.1f}%\nCVR: {safe_float(flow.get('cvr',0)):.1f}%", 
                                        key=f"flow_{i}", type="primary" if is_selected else "secondary"):
                                st.session_state.flow_index = i
                                st.session_state.similarities = {}
                                st.rerun()
                    
                    current_flow = st.session_state.flows[st.session_state.flow_index]
                    
                    if not st.session_state.similarities:
                        if not API_KEY:
                            st.warning("⚠️ FASTROUTER_API_KEY not set in secrets.")
                        else:
                            with st.spinner("Analyzing..."):
                                st.session_state.similarities = calculate_similarities(current_flow)

                    st.divider()
                    
                    # Card 1: SERP
                    st.subheader("📄 Card 1: Search Results")
                    card1_left, card1_right = st.columns([7, 3])
                    
                    with card1_left:
                        ctrl_cols = st.columns([1, 1, 1, 4, 1])
                        if ctrl_cols[0].button("➖", key="z1m"):
                            st.session_state.zoom1 = max(30, st.session_state.zoom1 - 10)
                            st.rerun()
                        if ctrl_cols[1].button("➕", key="z1p"):
                            st.session_state.zoom1 = min(200, st.session_state.zoom1 + 10)
                            st.rerun()
                        ctrl_cols[2].caption(f"{st.session_state.zoom1}%")
                        if ctrl_cols[4].button("⛶ Expand", key="exp_serp"):
                            st.session_state.show_serp_modal = True
                            st.rerun()
                        
                        device1 = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev1', index=0)
                        serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
                        preview_html, height = render_device_preview(serp_html, device1, st.session_state.zoom1)
                        st.components.v1.html(preview_html, height=height, scrolling=False)
                    
                    with card1_right:
                        st.markdown(f"""
                        <div class="info-box">
                            <div class="info-label">Keyword:</div> {current_flow.get('keyword_term', 'N/A')}<br><br>
                            <div class="info-label">Ad Title:</div> {current_flow.get('ad_title', 'N/A')}<br><br>
                            <div class="info-label">Description:</div> {current_flow.get('ad_description', 'N/A')[:100]}<br><br>
                            <div class="info-label">Display URL:</div> {current_flow.get('ad_display_url', 'N/A')}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("**Keyword → Ad Match**")
                        if st.session_state.similarities:
                            render_similarity_card("Match Score", st.session_state.similarities.get('kwd_to_ad'))
                    
                    # SERP Modal
                    if st.session_state.show_serp_modal:
                        @st.dialog("Search Results Preview", width="large")
                        def show_serp_popup():
                            ctrl_cols = st.columns([1, 1, 1, 6])
                            if ctrl_cols[0].button("➖", key="z1m_modal"):
                                st.session_state.zoom1 = max(30, st.session_state.zoom1 - 10)
                                st.rerun()
                            if ctrl_cols[1].button("➕", key="z1p_modal"):
                                st.session_state.zoom1 = min(200, st.session_state.zoom1 + 10)
                                st.rerun()
                            ctrl_cols[2].caption(f"{st.session_state.zoom1}%")
                            
                            device_modal = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev1_modal', index=0)
                            serp_html_modal = generate_serp_mockup(current_flow, st.session_state.data_b)
                            
                            # Larger scale for modal
                            dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
                            device_w, device_h = dims[device_modal]
                            modal_scale = 0.9 * (st.session_state.zoom1 / 100)
                            final_w = int(device_w * modal_scale)
                            final_h = int(device_h * modal_scale)
                            
                            modal_html = f"""
                            <div style="display:flex; justify-content:center; align-items:center; padding:20px; background:#1f2937; border-radius:8px; min-height:700px;">
                                <div style="box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius:8px; overflow:hidden; background:white; width:{final_w}px; height:{final_h}px;">
                                    <div style="width:{device_w}px; height:{device_h}px; transform:scale({modal_scale}); transform-origin:top left;">
                                        {serp_html_modal}
                                    </div>
                                </div>
                            </div>
                            """
                            st.components.v1.html(modal_html, height=final_h + 100, scrolling=True)
                            
                            if st.button("Close", key="close_serp_modal"):
                                st.session_state.show_serp_modal = False
                                st.rerun()
                        
                        show_serp_popup()
                    
                    st.divider()
                    
                    # Card 2: Landing Page
                    st.subheader("🌐 Card 2: Landing Page")
                    card2_left, card2_right = st.columns([7, 3])
                    
                    with card2_left:
                        ctrl_cols = st.columns([1, 1, 1, 4, 1])
                        if ctrl_cols[0].button("➖", key="z2m"):
                            st.session_state.zoom2 = max(30, st.session_state.zoom2 - 10)
                            st.rerun()
                        if ctrl_cols[1].button("➕", key="z2p"):
                            st.session_state.zoom2 = min(200, st.session_state.zoom2 + 10)
                            st.rerun()
                        ctrl_cols[2].caption(f"{st.session_state.zoom2}%")
                        if ctrl_cols[4].button("⛶ Expand", key="exp_landing"):
                            st.session_state.show_landing_modal = True
                            st.rerun()
                        
                        device2 = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev2', index=0)
                        dest_url = current_flow.get('reporting_destination_url', '')
                        
                        if dest_url and pd.notna(dest_url) and str(dest_url).lower() != 'null':
                            with st.spinner("Loading page..."):
                                screenshot = get_screenshot(dest_url)
                            
                            if screenshot:
                                dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
                                device_w, device_h = dims[device2]
                                
                                if device2 == 'mobile':
                                    base_scale = 0.55
                                elif device2 == 'tablet':
                                    base_scale = 0.75
                                else:
                                    base_scale = 0.65
                                
                                final_scale = base_scale * (st.session_state.zoom2 / 100)
                                final_w = int(device_w * final_scale)
                                final_h = int(device_h * final_scale)
                                
                                img_html = f"""
                                <div class="render-container">
                                    <div class="device-frame" style="width:{final_w}px; height:{final_h}px; margin:auto;">
                                        <img src="data:image/jpeg;base64,{screenshot}" 
                                             style="width:100%; height:100%; object-fit:contain;">
                                    </div>
                                </div>
                                """
                                st.components.v1.html(img_html, height=640, scrolling=False)
                            else:
                                preview_html, height = render_device_preview("", device2, st.session_state.zoom2, is_iframe=True, url=dest_url)
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                        else:
                            st.warning("⚠️ No landing page URL available")
                    
                    with card2_right:
                        dest_url = current_flow.get('reporting_destination_url', 'N/A')
                        st.markdown(f"""
                        <div class="info-box">
                            <div class="info-label">Landing Page:</div><br>
                            {dest_url[:80]}...
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("**Keyword → Page Match**")
                        if st.session_state.similarities:
                            render_similarity_card("Match Score", st.session_state.similarities.get('kwd_to_page'))
                        
                        st.markdown("**Ad → Page Match**")
                        if st.session_state.similarities:
                            render_similarity_card("Match Score", st.session_state.similarities.get('ad_to_page'))
                    
                    # Landing Page Modal
                    if st.session_state.show_landing_modal:
                        @st.dialog("Landing Page Preview", width="large")
                        def show_landing_popup():
                            ctrl_cols = st.columns([1, 1, 1, 6])
                            if ctrl_cols[0].button("➖", key="z2m_modal"):
                                st.session_state.zoom2 = max(30, st.session_state.zoom2 - 10)
                                st.rerun()
                            if ctrl_cols[1].button("➕", key="z2p_modal"):
                                st.session_state.zoom2 = min(200, st.session_state.zoom2 + 10)
                                st.rerun()
                            ctrl_cols[2].caption(f"{st.session_state.zoom2}%")
                            
                            device_modal = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev2_modal', index=0)
                            dest_url_modal = current_flow.get('reporting_destination_url', '')
                            
                            if dest_url_modal and pd.notna(dest_url_modal) and str(dest_url_modal).lower() != 'null':
                                screenshot_modal = get_screenshot(dest_url_modal)
                                
                                if screenshot_modal:
                                    dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
                                    device_w, device_h = dims[device_modal]
                                    modal_scale = 0.9 * (st.session_state.zoom2 / 100)
                                    final_w = int(device_w * modal_scale)
                                    final_h = int(device_h * modal_scale)
                                    
                                    modal_html = f"""
                                    <div style="display:flex; justify-content:center; align-items:center; padding:20px; background:#1f2937; border-radius:8px; min-height:700px;">
                                        <div style="box-shadow: 0 8px 32px rgba(0,0,0,0.6); border-radius:8px; overflow:hidden; background:white; width:{final_w}px; height:{final_h}px;">
                                            <img src="data:image/jpeg;base64,{screenshot_modal}" style="width:100%; height:100%; object-fit:contain;">
                                        </div>
                                    </div>
                                    """
                                    st.components.v1.html(modal_html, height=final_h + 100, scrolling=True)
                            
                            if st.button("Close", key="close_landing_modal"):
                                st.session_state.show_landing_modal = False
                                st.rerun()
                        
                        show_landing_popup()
                else:
                    st.warning("No flows found")
else:
    st.error("❌ Failed to load data")



