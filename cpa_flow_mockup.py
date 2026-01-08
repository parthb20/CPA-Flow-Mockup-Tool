import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
import re
from io import StringIO
import time

# Page config
st.set_page_config(page_title="CPA Flow Analysis", page_icon="📊", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #111827; }
    .stApp { background-color: #111827; }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        padding: 15px; border-radius: 8px; border: 2px solid #4b5563; margin: 10px 0;
    }
    .similarity-excellent { border-color: #22c55e; background: rgba(34, 197, 94, 0.1); }
    .similarity-good { border-color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
    .similarity-moderate { border-color: #eab308; background: rgba(234, 179, 8, 0.1); }
    .similarity-poor { border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
    .render-container {
        display: flex; justify-content: center; align-items: flex-start;
        padding: 20px; background: #1f2937; border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# Config
FILE_A_ID = "1bwdj-rAAp6I1SbO27BTFD2eLiv6V5vsB"
FILE_B_ID = "1QpQhZhXFFpQWm_xhVGDjdpgRM3VMv57L"

# Fix API key loading - Using OpenAI
try:
    API_KEY = st.secrets.get("OPENAI_API_KEY", st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
    if API_KEY:
        st.sidebar.success("✅ API Key loaded")
    else:
        st.sidebar.warning("⚠️ No API key found")
except Exception as e:
    API_KEY = ""
    st.sidebar.error(f"❌ API Key error: {str(e)}")

# Session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_url', 'flows', 
            'flow_index', 'similarities', 'loading_done', 'zoom1', 'zoom2']:
    if key not in st.session_state:
        if key == 'flows':
            st.session_state[key] = []
        elif key == 'flow_index':
            st.session_state[key] = 0
        elif key in ['zoom1', 'zoom2']:
            st.session_state[key] = 100
        elif key == 'loading_done':
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

def call_similarity_api(prompt):
    if not API_KEY:
        st.sidebar.warning("⚠️ No API key - skipping analysis")
        return None
    try:
        # Using OpenAI API
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000
            },
            timeout=30
        )
        if response.status_code != 200:
            st.sidebar.error(f"API Error: {response.status_code} - {response.text[:100]}")
            return None
        data = response.json()
        text = data['choices'][0]['message']['content']
        clean_text = text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        st.sidebar.error(f"API Exception: {str(e)}")
        return None

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

def render_similarity_card(title, data):
    if not data:
        st.error(f"{title}: API unavailable")
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

def generate_serp_mockup(flow_data, serp_templates):
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    
    if serp_templates and len(serp_templates) > 0:
        try:
            html = serp_templates[0].get('code', '')
            html = re.sub(r'Sponsored results for: "[^"]*"', f'Sponsored results for: "{keyword}"', html)
            html = re.sub(r'<div class="url">[^<]*</div>', f'<div class="url">{ad_url}</div>', html, count=1)
            html = re.sub(r'<div class="title">[^<]*</div>', f'<div class="title">{ad_title}</div>', html, count=1)
            html = re.sub(r'<div class="desc">[^<]*</div>', f'<div class="desc">{ad_desc}</div>', html, count=1)
            return html
        except:
            pass
    
    return f"""<div style="background: white; padding: 20px; border-radius: 8px; width: 100%; box-sizing: border-box;">
        <div style="color: #666; font-size: 12px; margin-bottom: 16px;">Sponsored: "{keyword}"</div>
        <div style="color: #006621; font-size: 12px; margin-bottom: 8px;">{ad_url}</div>
        <div style="margin-bottom: 8px;"><a href="#" style="color: #1a0dab; font-size: 18px; font-weight: 500; text-decoration: none;">{ad_title}</a></div>
        <div style="color: #545454; font-size: 14px;">{ad_desc}</div></div>"""

# Auto-load
if not st.session_state.loading_done:
    with st.spinner("Loading..."):
        st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
        st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
        st.session_state.loading_done = True

st.title("📊 CPA Flow Analysis")

if st.session_state.data_a is not None:
    df = st.session_state.data_a
    
    col1, col2 = st.columns(2)
    with col1:
        advertisers = sorted(df['Advertiser_Name'].dropna().unique())
        selected_advertiser = st.selectbox("Advertiser", advertisers)
    with col2:
        campaigns = sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique())
        selected_campaign = st.selectbox("Campaign", campaigns)
    
    if selected_campaign:
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
        
        # Keyword Section
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
                    x=[row['ctr']], y=[row['cvr']],
                    mode='markers',
                    marker=dict(size=max(20, min(70, row['clicks']/10)), color=color, 
                               line=dict(width=2, color='white')),
                    name=row['keyword_term'],
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                 'CTR: %{x:.2f}%<br>' +
                                 'CVR: %{y:.2f}%<br>' +
                                 f"Clicks: {int(row['clicks'])}" +
                                 '<extra></extra>',
                    customdata=[[row['keyword_term']]]
                ))
            
            fig.add_hline(y=avg_cvr, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=avg_ctr, line_dash="dash", line_color="gray", opacity=0.5)
            
            fig.update_layout(
                xaxis_title="CTR (%)", yaxis_title="CVR (%)", height=400,
                showlegend=False, plot_bgcolor='#1f2937', paper_bgcolor='#1f2937',
                font=dict(color='white'), hovermode='closest',
                xaxis=dict(gridcolor='#374151'), yaxis=dict(gridcolor='#374151')
            )
            
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
            keyword_filter = f1.selectbox("Filter", ['all', 'best', 'worst'])
            keyword_limit = f2.selectbox("Show", [10, 25, 50])
            keyword_sort = f3.selectbox("Sort", ['clicks', 'ctr', 'cvr'])
            
            filtered_keywords = keyword_agg.copy()
            if keyword_filter == 'best':
                filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] >= avg_ctr) & (filtered_keywords['cvr'] >= avg_cvr)]
            elif keyword_filter == 'worst':
                filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] < avg_ctr) & (filtered_keywords['cvr'] < avg_cvr)]
            
            filtered_keywords = filtered_keywords.sort_values(keyword_sort, ascending=False).head(keyword_limit)
            
            # Single clickable table
            display_df = filtered_keywords[['keyword_term', 'clicks', 'ctr', 'cvr']].copy()
            display_df['Keyword'] = display_df['keyword_term']
            display_df['Clicks'] = display_df['clicks'].apply(lambda x: f"{int(x):,}")
            display_df['CTR %'] = display_df.apply(
                lambda row: f"<span style='color: {'green' if row['ctr'] >= avg_ctr else 'red'}'>{row['ctr']:.2f}%</span>", 
                axis=1
            )
            display_df['CVR %'] = display_df.apply(
                lambda row: f"<span style='color: {'green' if row['cvr'] >= avg_cvr else 'red'}'>{row['cvr']:.2f}%</span>", 
                axis=1
            )
            
            # Show colored table
            st.markdown(
                display_df[['Keyword', 'Clicks', 'CTR %', 'CVR %']].to_html(escape=False, index=False), 
                unsafe_allow_html=True
            )
            
            st.write("")  # Spacing
            
            # Interactive selection table
            selected_kwd = st.dataframe(
                filtered_keywords[['keyword_term', 'clicks']].reset_index(drop=True), 
                use_container_width=True, hide_index=True, 
                on_select="rerun", selection_mode="single-row", key="kwd_table",
                column_config={
                    "keyword_term": "Select Keyword",
                    "clicks": st.column_config.NumberColumn("Clicks", format="%d")
                }
            )
            
            if selected_kwd and len(selected_kwd['selection']['rows']) > 0:
                idx = selected_kwd['selection']['rows'][0]
                new_keyword = filtered_keywords.iloc[idx]['keyword_term']
                if new_keyword != st.session_state.selected_keyword:
                    st.session_state.selected_keyword = new_keyword
                    st.session_state.selected_url = None
                    st.session_state.similarities = {}
        
        # URL Selection (filtered by keyword)
        if st.session_state.selected_keyword:
            st.divider()
            st.subheader(f"🔗 URLs for: {st.session_state.selected_keyword}")
            
            keyword_urls = campaign_df[campaign_df['keyword_term'] == st.session_state.selected_keyword]
            url_agg = keyword_urls.groupby('publisher_url').agg({'clicks': 'sum', 'conversions': 'sum'}).reset_index()
            url_agg = url_agg.sort_values('clicks', ascending=False).head(25)
            url_agg['display'] = url_agg['publisher_url'].apply(lambda x: x[:70] + '...' if len(str(x)) > 70 else x)
            
            display_url_df = url_agg[['display', 'clicks']].copy()
            display_url_df.columns = ['Publisher URL', 'Clicks']
            
            selected_url_idx = st.dataframe(display_url_df, use_container_width=True, hide_index=True,
                                           on_select="rerun", selection_mode="single-row", key="url_table")
            
            if selected_url_idx and len(selected_url_idx['selection']['rows']) > 0:
                idx = selected_url_idx['selection']['rows'][0]
                new_url = url_agg.iloc[idx]['publisher_url']
                if new_url != st.session_state.selected_url:
                    st.session_state.selected_url = new_url
                    st.session_state.similarities = {}
        
        # Flow Analysis
        if st.session_state.selected_keyword and st.session_state.selected_url:
            st.divider()
            
            flows = campaign_df[
                (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                (campaign_df['publisher_url'] == st.session_state.selected_url)
            ].sort_values('clicks', ascending=False).head(5)
            
            st.session_state.flows = flows.to_dict('records')
            
            if len(st.session_state.flows) > 0:
                # Flow stats at top
                st.subheader("📈 Flow Statistics")
                nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([2,2,2,2,2])
                
                for i, flow in enumerate(st.session_state.flows):
                    col = [nav_col1, nav_col2, nav_col3, nav_col4, nav_col5][i]
                    with col:
                        is_selected = i == st.session_state.flow_index
                        button_type = "primary" if is_selected else "secondary"
                        if st.button(f"Flow {i+1}\n{safe_int(flow.get('clicks',0))} clicks\nCTR: {safe_float(flow.get('ctr',0)):.1f}%\nCVR: {safe_float(flow.get('cvr',0)):.1f}%", 
                                    key=f"flow_{i}", type=button_type):
                            st.session_state.flow_index = i
                            st.session_state.similarities = {}
                            st.rerun()
                
                current_flow = st.session_state.flows[st.session_state.flow_index]
                
                if not st.session_state.similarities and API_KEY:
                    with st.spinner("Analyzing..."):
                        st.session_state.similarities = calculate_similarities(current_flow)
                
                st.divider()
                
                # Card 1: SERP
                st.subheader("📄 Card 1: Search Results")
                
                # Zoom controls at top
                z1_col1, z1_col2, z1_col3 = st.columns([1, 1, 8])
                with z1_col1:
                    if st.button("➖", key="z1m", help="Zoom Out"):
                        st.session_state.zoom1 = max(50, st.session_state.zoom1 - 10)
                        st.rerun()
                with z1_col2:
                    if st.button("➕", key="z1p", help="Zoom In"):
                        st.session_state.zoom1 = min(150, st.session_state.zoom1 + 10)
                        st.rerun()
                with z1_col3:
                    st.caption(f"Zoom: {st.session_state.zoom1}%")
                
                card1_left, card1_right = st.columns([7, 3])
                
                with card1_left:
                    device1 = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev1', index=0)
                    
                    serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
                    
                    dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
                    device_w, device_h = dims[device1]
                    
                    scale = st.session_state.zoom1 / 100
                    scaled_w = int(device_w * scale)
                    scaled_h = int(device_h * scale)
                    
                    render_html = f"""
                    <div style="display: flex; justify-content: center; align-items: flex-start; padding: 20px; background: #1f2937; border-radius: 8px;">
                        <div style="width:{scaled_w}px; height:{scaled_h}px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.5);">
                            <div style="transform:scale({scale}); transform-origin:top left; width:{device_w}px; height:{device_h}px;">
                                {serp_html}
                            </div>
                        </div>
                    </div>
                    """
                    
                    st.components.v1.html(render_html, height=scaled_h + 50, scrolling=False)
                    
                    # Add fullscreen link
                    serp_data_url = f"data:text/html;charset=utf-8,{serp_html.replace('#', '%23')}"
                    st.markdown(f'<a href="{serp_data_url}" target="_blank" class="fullscreen-link">🔍 Open Fullscreen</a>', unsafe_allow_html=True)
                
                with card1_right:
                    st.markdown("**Keyword → Ad**")
                    if st.session_state.similarities:
                        render_similarity_card("Match Score", st.session_state.similarities.get('kwd_to_ad'))
                
                st.divider()
                
                # Card 2: Landing Page
                st.subheader("🌐 Card 2: Landing Page")
                
                # Zoom controls at top
                z2_col1, z2_col2, z2_col3 = st.columns([1, 1, 8])
                with z2_col1:
                    if st.button("➖", key="z2m", help="Zoom Out"):
                        st.session_state.zoom2 = max(50, st.session_state.zoom2 - 10)
                        st.rerun()
                with z2_col2:
                    if st.button("➕", key="z2p", help="Zoom In"):
                        st.session_state.zoom2 = min(150, st.session_state.zoom2 + 10)
                        st.rerun()
                with z2_col3:
                    st.caption(f"Zoom: {st.session_state.zoom2}%")
                
                card2_left, card2_right = st.columns([7, 3])
                
                with card2_left:
                    device2 = st.radio("Device", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev2', index=2)
                    dest_url = current_flow.get('reporting_destination_url', '')
                    
                    if dest_url and pd.notna(dest_url) and str(dest_url).lower() != 'null':
                        dims = {'mobile': (375, 667), 'tablet': (768, 1024), 'laptop': (1440, 900)}
                        device_w, device_h = dims[device2]
                        scale = st.session_state.zoom2 / 100
                        scaled_w = int(device_w * scale)
                        scaled_h = int(device_h * scale)
                        
                        iframe_html = f"""
                        <div style="display: flex; justify-content: center; align-items: flex-start; padding: 20px; background: #1f2937; border-radius: 8px;">
                            <div style="box-shadow:0 4px 20px rgba(0,0,0,0.5);">
                                <iframe src="{dest_url}" width="{scaled_w}" height="{scaled_h}" 
                                        style="border:none; background:white;"></iframe>
                            </div>
                        </div>
                        """
                        st.components.v1.html(iframe_html, height=scaled_h + 50, scrolling=False)
                        
                        st.markdown(f'<a href="{dest_url}" target="_blank" class="fullscreen-link">🔗 Open in New Tab</a>', unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ No URL")
                
                with card2_right:
                    # Display Landing Page URL
                    dest_url = current_flow.get('reporting_destination_url', 'N/A')
                    st.markdown("**Landing Page URL**")
                    st.markdown(f'<div class="url-display">{dest_url}</div>', unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    st.markdown("**Keyword → Page**")
                    if st.session_state.similarities:
                        render_similarity_card("Match Score", st.session_state.similarities.get('kwd_to_page'))
                    
                    st.markdown("**Ad → Page**")
                    if st.session_state.similarities:
                        render_similarity_card("Match Score", st.session_state.similarities.get('ad_to_page'))
            else:
                st.warning("No flows")
else:
    st.error("❌ Failed to load data")
