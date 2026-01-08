import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, parse_qs
import re
from io import StringIO
import time
import base64
from io import BytesIO

# Page config
st.set_page_config(
    page_title="CPA Flow Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    </style>
""", unsafe_allow_html=True)

# ===== CONFIGURATION =====
FILE_A_ID = "1bwdj-rAAp6I1SbO27BTFD2eLiv6V5vsB"
FILE_B_ID = "1QpQhZhXFFpQWm_xhVGDjdpgRM3VMv57L"

# Get API key from secrets
try:
    API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
except:
    API_KEY = ""

# Initialize session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_url', 'flows', 
            'flow_index', 'similarities', 'last_keyword_url', 'loading_done']:
    if key not in st.session_state:
        if key == 'flows':
            st.session_state[key] = []
        elif key == 'flow_index':
            st.session_state[key] = 0
        elif key == 'last_keyword_url':
            st.session_state[key] = (None, None)
        elif key == 'loading_done':
            st.session_state[key] = False
        else:
            st.session_state[key] = None

# Helper Functions
def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive"""
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
    """Load JSON from Google Drive"""
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
        return None
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        if response.status_code != 200:
            return None
        data = response.json()
        text = data['content'][0]['text']
        clean_text = text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except:
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
    
    # Keyword → Ad
    kwd_to_ad_prompt = f"""Evaluate keyword-to-ad match.

KEYWORD: "{keyword}"
AD: "{ad_text}"

Detect intent from keyword:
TRANSACTIONAL: buy, price, deal, shop, apply, download, etc
NAVIGATIONAL: [brand] login, official, website, account, etc
INFORMATIONAL: how to, what is, guide, tips, why, etc
COMPARISON: best, top, vs, compare, review, alternative, etc

Brand rule: If keyword contains brand/company name:
- Brand in ad → score normally
- Brand missing → cap keyword_match≤0.3, intent_match≤0.5 (or ≤0.2 if NAVIGATIONAL)

Score components (0.0-1.0):

KEYWORD_MATCH (0.15): Lexical/entity overlap (not semantic)
1.0=all, 0.7=most, 0.4=half, 0.0=none

TOPIC_MATCH (0.35): Semantic similarity (concept overlap)
1.0=identical, 0.7=related, 0.4=loose, 0.1=unrelated

INTENT_MATCH (0.50): Goal alignment
TRANSACTIONAL→CTA=1.0|no CTA=0.2
NAVIGATIONAL→exact brand=1.0|competitor=0.1
INFORMATIONAL→content=0.9|sales=0.3
COMPARISON→options=0.9|single=0.4

Score bands: 0.0-0.2=poor, 0.2-0.4=weak, 0.4-0.6=moderate, 0.6-0.8=good, 0.8-1.0=excellent

Return JSON only (no other text):
{{"intent":"","keyword_match":0.0,"topic_match":0.0,"intent_match":0.0,"final_score":0.0,"band":"","reason":""}}

Formula: 0.15×keyword_match + 0.35×topic_match + 0.50×intent_match"""
    
    results['kwd_to_ad'] = call_similarity_api(kwd_to_ad_prompt)
    time.sleep(1)
    
    if adv_url and pd.notna(adv_url) and str(adv_url).lower() != 'null' and str(adv_url).strip():
        page_text = fetch_page_content(adv_url)
        
        if page_text:
            # Ad → Page
            ad_to_page_prompt = f"""Evaluate ad-to-page match.

AD: "{ad_text}"
PAGE: "{page_text}"

Brand rule: If ad mentions specific brand/service:
- Same brand on page → score normally
- Different brand OR generic hub → cap brand_match≤0.2

Score components (0.0-1.0):

TOPIC_MATCH (0.30): Same product/service?
1.0=exact, 0.7=related, 0.4=loose, 0.1=unrelated

BRAND_MATCH (0.20): Same company/identity?
1.0=same brand clear, 0.7=same but weak, 0.2=different brand, 0.0=generic hub/redirect

PROMISE_MATCH (0.50): Ad claims delivered?
1.0=all delivered, 0.7=mostly, 0.3=partial, 0.0=bait-and-switch

Score bands: 0.0-0.2=poor, 0.2-0.4=weak, 0.4-0.6=moderate, 0.6-0.8=good, 0.8-1.0=excellent

Return JSON only (no other text):
{{"topic_match":0.0,"brand_match":0.0,"promise_match":0.0,"final_score":0.0,"band":"","reason":""}}

Formula: 0.30×topic_match + 0.20×brand_match + 0.50×promise_match"""
            
            results['ad_to_page'] = call_similarity_api(ad_to_page_prompt)
            time.sleep(1)
            
            # Keyword → Page
            kwd_to_page_prompt = f"""Evaluate keyword-to-page match.

KEYWORD: "{keyword}"
PAGE: "{page_text}"

Detect intent from keyword:
TRANSACTIONAL: buy, price, deal, shop, order, etc
NAVIGATIONAL: [brand] login, official, website, etc
INFORMATIONAL: how to, what is, guide, tips, etc
COMPARISON: best, top, vs, compare, review, etc

Brand rule: If NAVIGATIONAL with brand and page is wrong site:
- Cap topic_match≤0.3 AND answer_quality≤0.2

Score components (0.0-1.0):

TOPIC_MATCH (0.40): Addresses keyword subject?
1.0=exact, 0.7=related, 0.4=loose, 0.1=unrelated

ANSWER_QUALITY (0.60): Satisfies detected intent?
TRANSACTIONAL→product+CTA=1.0|no CTA=0.3
NAVIGATIONAL→correct site=1.0|wrong=0.1
INFORMATIONAL→detailed=0.9|thin=0.2
COMPARISON→actual comparison=0.9|links only=0.2

Score bands: 0.0-0.2=poor, 0.2-0.4=weak, 0.4-0.6=moderate, 0.6-0.8=good, 0.8-1.0=excellent

Return JSON only (no other text):
{{"intent":"","topic_match":0.0,"answer_quality":0.0,"final_score":0.0,"band":"","reason":""}}

Formula: 0.40×topic_match + 0.60×answer_quality"""
            
            results['kwd_to_page'] = call_similarity_api(kwd_to_page_prompt)
    
    return results

def render_similarity_card(title, data):
    if not data:
        st.warning(f"{title}: N/A")
        return
    
    score = data.get('final_score', 0)
    band = data.get('band', 'unknown')
    
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
    </div>
    """, unsafe_allow_html=True)

def generate_serp_mockup(flow_data, serp_templates):
    """Generate SERP HTML mockup"""
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
    
    return f"""
    <div style="background: white; padding: 20px; border-radius: 8px;">
        <div style="color: #666; font-size: 12px; margin-bottom: 16px;">
            Sponsored results for: "{keyword}"
        </div>
        <div style="color: #006621; font-size: 12px; margin-bottom: 8px;">{ad_url}</div>
        <div style="margin-bottom: 8px;">
            <a href="#" style="color: #1a0dab; font-size: 18px; font-weight: 500; text-decoration: none;">
                {ad_title}
            </a>
        </div>
        <div style="color: #545454; font-size: 14px;">{ad_desc}</div>
    </div>
    """

# Auto-load data on first run
if not st.session_state.loading_done:
    with st.spinner("Loading campaign data..."):
        st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
        st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
        st.session_state.loading_done = True

# Main App
st.title("📊 CPA Flow Analysis")

if st.session_state.data_a is not None:
    df = st.session_state.data_a
    
    # Campaign Selection
    col1, col2 = st.columns(2)
    with col1:
        advertisers = sorted(df['Advertiser_Name'].dropna().unique())
        selected_advertiser = st.selectbox("Advertiser", advertisers, key='adv')
    with col2:
        campaigns = sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique())
        selected_campaign = st.selectbox("Campaign", campaigns, key='cmp')
    
    if selected_campaign:
        campaign_df = df[
            (df['Advertiser_Name'] == selected_advertiser) &
            (df['Campaign_Name'] == selected_campaign)
        ].copy()
        
        campaign_df = calculate_metrics(campaign_df)
        avg_ctr, avg_cvr = calculate_campaign_averages(campaign_df)
        
        st.divider()
        
        # Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Campaign CTR", f"{avg_ctr:.2f}%")
        c2.metric("Campaign CVR", f"{avg_cvr:.2f}%")
        c3.metric("Total Clicks", f"{safe_int(campaign_df['clicks'].sum()):,}")
        c4.metric("Total Conversions", f"{safe_int(campaign_df['conversions'].sum()):,}")
        
        st.divider()
        
        # Keyword Analysis
        keyword_agg = campaign_df.groupby('keyword_term').agg({
            'impressions': 'sum', 'clicks': 'sum', 'conversions': 'sum'
        }).reset_index()
        
        keyword_agg['ctr'] = keyword_agg.apply(
            lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
        keyword_agg['cvr'] = keyword_agg.apply(
            lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
        
        # Bubble Chart with clickable bubbles
        st.subheader("🔑 Keyword Performance")
        bubble_data = keyword_agg.nlargest(20, 'clicks')
        
        fig = go.Figure()
        for _, row in bubble_data.iterrows():
            quadrant, color = get_quadrant(row['ctr'], row['cvr'], avg_ctr, avg_cvr)
            fig.add_trace(go.Scatter(
                x=[row['ctr']], y=[row['cvr']],
                mode='markers',
                marker=dict(size=max(15, min(60, row['clicks']/10)), 
                           color=color, line=dict(width=2, color='white')),
                name=row['keyword_term'][:30],
                text=row['keyword_term'],
                customdata=[row['keyword_term']],
                hovertemplate='<b>%{text}</b><br>CTR: %{x:.2f}%<br>CVR: %{y:.2f}%<extra></extra>'
            ))
        
        fig.add_hline(y=avg_cvr, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=avg_ctr, line_dash="dash", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            xaxis_title="CTR (%)", yaxis_title="CVR (%)", height=500,
            showlegend=False, plot_bgcolor='#1f2937', paper_bgcolor='#1f2937',
            font=dict(color='white'),
            xaxis=dict(gridcolor='#374151'), yaxis=dict(gridcolor='#374151'),
            clickmode='event+select'
        )
        
        selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="bubble")
        
        # Handle bubble click
        if selected_points and 'selection' in selected_points and 'points' in selected_points['selection']:
            points = selected_points['selection']['points']
            if points:
                clicked_keyword = bubble_data.iloc[points[0]['point_index']]['keyword_term']
                if clicked_keyword != st.session_state.selected_keyword:
                    st.session_state.selected_keyword = clicked_keyword
                    st.session_state.flow_index = 0
                    st.session_state.similarities = {}
                    st.rerun()
        
        # Filters
        st.subheader("📋 Keyword & URL Selection")
        left, right = st.columns([6, 4])
        
        with left:
            f1, f2, f3 = st.columns(3)
            keyword_filter = f1.selectbox("Filter Keywords", ['all', 'best', 'worst'])
            keyword_limit = f2.selectbox("Show", [10, 25, 50, 100])
            keyword_sort = f3.selectbox("Sort by", ['clicks', 'ctr', 'cvr'])
            
            filtered_keywords = keyword_agg.copy()
            if keyword_filter == 'best':
                filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] >= avg_ctr) & (filtered_keywords['cvr'] >= avg_cvr)]
            elif keyword_filter == 'worst':
                filtered_keywords = filtered_keywords[(filtered_keywords['ctr'] < avg_ctr) & (filtered_keywords['cvr'] < avg_cvr)]
            
            filtered_keywords = filtered_keywords.sort_values(keyword_sort, ascending=False).head(keyword_limit)
            
            display_df = filtered_keywords[['keyword_term', 'clicks', 'ctr', 'cvr']].copy()
            display_df.columns = ['Keyword', 'Clicks', 'CTR (%)', 'CVR (%)']
            display_df['CTR (%)'] = display_df['CTR (%)'].apply(lambda x: f"{x:.2f}")
            display_df['CVR (%)'] = display_df['CVR (%)'].apply(lambda x: f"{x:.2f}")
            
            selected_kwd = st.dataframe(display_df, use_container_width=True, hide_index=True, 
                                       on_select="rerun", selection_mode="single-row")
            
            if selected_kwd and len(selected_kwd['selection']['rows']) > 0:
                idx = selected_kwd['selection']['rows'][0]
                new_keyword = filtered_keywords.iloc[idx]['keyword_term']
                if new_keyword != st.session_state.selected_keyword:
                    st.session_state.selected_keyword = new_keyword
                    st.session_state.flow_index = 0
                    st.session_state.similarities = {}
        
        with right:
            url_agg = campaign_df.groupby('publisher_url').agg({
                'impressions': 'sum', 'clicks': 'sum', 'conversions': 'sum'
            }).reset_index()
            url_agg['ctr'] = url_agg.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
            url_agg['cvr'] = url_agg.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
            
            url_agg = url_agg.sort_values('clicks', ascending=False).head(25)
            url_agg['display_url'] = url_agg['publisher_url'].apply(lambda x: x[:40] + '...' if len(str(x)) > 40 else x)
            
            display_url_df = url_agg[['display_url', 'clicks']].copy()
            display_url_df.columns = ['Publisher URL', 'Clicks']
            
            selected_url_idx = st.dataframe(display_url_df, use_container_width=True, hide_index=True,
                                           on_select="rerun", selection_mode="single-row")
            
            if selected_url_idx and len(selected_url_idx['selection']['rows']) > 0:
                idx = selected_url_idx['selection']['rows'][0]
                new_url = url_agg.iloc[idx]['publisher_url']
                if new_url != st.session_state.selected_url:
                    st.session_state.selected_url = new_url
                    st.session_state.flow_index = 0
                    st.session_state.similarities = {}
        
        # Flow Analysis
        if st.session_state.selected_keyword and st.session_state.selected_url:
            st.divider()
            st.header("📈 Flow Analysis")
            
            flows = campaign_df[
                (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                (campaign_df['publisher_url'] == st.session_state.selected_url)
            ].sort_values('clicks', ascending=False).head(5)
            
            non_null = flows[
                flows['reporting_destination_url'].notna() & 
                (flows['reporting_destination_url'].str.lower() != 'null') &
                (flows['reporting_destination_url'] != '')
            ]
            
            st.session_state.flows = (non_null if len(non_null) > 0 else flows).to_dict('records')
            
            if len(st.session_state.flows) > 0:
                current_flow = st.session_state.flows[st.session_state.flow_index]
                
                # Auto-calculate similarities
                if not st.session_state.similarities or st.session_state.similarities.get('flow_id') != current_flow.get('creative_id'):
                    if API_KEY:
                        with st.spinner("Analyzing similarities..."):
                            st.session_state.similarities = calculate_similarities(current_flow)
                            st.session_state.similarities['flow_id'] = current_flow.get('creative_id')
                
                # Card 1: SERP with Keyword→Ad similarity
                st.subheader("📄 Card 1: Search Results")
                card1_left, card1_right = st.columns([7, 3])
                
                with card1_left:
                    serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
                    zoom1 = st.slider("Zoom", 50, 200, 100, 10, key="zoom1", format="%d%%")
                    st.components.v1.html(f"<div style='transform: scale({zoom1/100}); transform-origin: top left;'>{serp_html}</div>", 
                                        height=int(600 * zoom1/100), scrolling=True)
                
                with card1_right:
                    st.markdown("**Keyword → Ad Match**")
                    if st.session_state.similarities:
                        render_similarity_card("Keyword → Ad", st.session_state.similarities.get('kwd_to_ad'))
                    
                    st.markdown("**SERP Details**")
                    st.text(f"Keyword: {current_flow.get('keyword_term', 'N/A')[:30]}...")
                    st.text(f"Title: {current_flow.get('ad_title', 'N/A')[:30]}...")
                
                st.divider()
                
                # Card 2: Landing Page with Keyword→Page and Ad→Page
                st.subheader("🌐 Card 2: Landing Page")
                card2_left, card2_right = st.columns([7, 3])
                
                with card2_left:
                    dest_url = current_flow.get('reporting_destination_url', '')
                    if dest_url and pd.notna(dest_url) and str(dest_url).lower() != 'null':
                        zoom2 = st.slider("Zoom", 50, 200, 100, 10, key="zoom2", format="%d%%")
                        st.components.v1.iframe(dest_url, width=int(900 * zoom2/100), 
                                               height=int(600 * zoom2/100), scrolling=True)
                    else:
                        st.warning("⚠️ No landing page URL")
                
                with card2_right:
                    st.markdown("**Keyword → Page**")
                    if st.session_state.similarities:
                        render_similarity_card("Keyword → Page", st.session_state.similarities.get('kwd_to_page'))
                    
                    st.markdown("**Ad → Page**")
                    if st.session_state.similarities:
                        render_similarity_card("Ad → Page", st.session_state.similarities.get('ad_to_page'))
                    
                    st.markdown("**Performance**")
                    st.metric("Clicks", f"{safe_int(current_flow.get('clicks', 0)):,}")
                    st.metric("CTR", f"{safe_float(current_flow.get('ctr', 0)):.2f}%")
            else:
                st.warning("No flows found")
else:
    st.error("❌ Failed to load data from Google Drive")
