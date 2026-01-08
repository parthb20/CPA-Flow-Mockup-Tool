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

# Page config
st.set_page_config(
    page_title="CPA Flow Mockup Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #111827; }
    .stApp { background-color: #111827; }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        padding: 20px; border-radius: 10px; border: 2px solid #4b5563; margin: 10px 0;
    }
    .similarity-excellent { border-color: #22c55e; background: rgba(34, 197, 94, 0.1); }
    .similarity-good { border-color: #3b82f6; background: rgba(59, 130, 246, 0.1); }
    .similarity-moderate { border-color: #eab308; background: rgba(234, 179, 8, 0.1); }
    .similarity-poor { border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
    </style>
""", unsafe_allow_html=True)

# ===== CONFIGURATION - UPDATE THESE WITH YOUR GOOGLE DRIVE FILE IDs =====
# For Google Sheets: Use "Anyone with link" sharing, get the FILE_ID from URL
# Format: https://docs.google.com/spreadsheets/d/FILE_ID/edit
FILE_B_ID = "1QpQhZhXFFpQWm_xhVGDjdpgRM3VMv57L"  # Replace with your File A ID
FILE_A_ID = "1bwdj-rAAp6I1SbO27BTFD2eLiv6V5vsB"  # Replace with your File B ID

# Initialize session state
for key in ['data_a', 'data_b', 'selected_keyword', 'selected_url', 'flows', 
            'flow_index', 'similarities', 'api_key', 'last_keyword_url']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'flows' else []
        if key == 'flow_index':
            st.session_state[key] = 0
        if key == 'last_keyword_url':
            st.session_state[key] = (None, None)

# Helper Functions
def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive - works for both Sheets and uploaded CSV"""
    try:
        # Try Google Sheets export first
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            # Try direct download for uploaded files
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            response = requests.get(url, timeout=30)
        
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text), dtype=str)
        return df
    except Exception as e:
        st.error(f"❌ Error loading CSV: {str(e)}")
        st.info("💡 Make sure file is shared as 'Anyone with the link can view'")
        return None

def load_json_from_gdrive(file_id):
    """Load JSON from Google Drive"""
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ Error loading JSON: {str(e)}")
        return None

def clean_url(url):
    """Remove tracking parameters"""
    if not url or pd.isna(url):
        return url
    try:
        parsed = urlparse(str(url))
        query_params = parse_qs(parsed.query)
        clean_params = {k: v for k, v in query_params.items() 
                       if k not in ['utm_source', 'utm_medium', 'utm_campaign', 
                                   'gclid', 'fbclid', 'msclkid']}
        from urllib.parse import urlencode, urlunparse
        clean_query = urlencode(clean_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                          parsed.params, clean_query, ''))
    except:
        return url

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        return float(value) if pd.notna(value) else default
    except:
        return default

def safe_int(value, default=0):
    """Safely convert to int"""
    try:
        return int(float(value)) if pd.notna(value) else default
    except:
        return default

def calculate_metrics(df):
    """Calculate CTR and CVR with error handling"""
    df['impressions'] = df['impressions'].apply(safe_float)
    df['clicks'] = df['clicks'].apply(safe_float)
    df['conversions'] = df['conversions'].apply(safe_float)
    
    df['ctr'] = df.apply(lambda x: (x['clicks'] / x['impressions'] * 100) 
                         if x['impressions'] > 0 else 0, axis=1)
    df['cvr'] = df.apply(lambda x: (x['conversions'] / x['clicks'] * 100) 
                         if x['clicks'] > 0 else 0, axis=1)
    
    return df

def calculate_campaign_averages(df):
    """Calculate weighted averages"""
    total_impressions = df['impressions'].sum()
    total_clicks = df['clicks'].sum()
    total_conversions = df['conversions'].sum()
    
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
    
    return avg_ctr, avg_cvr

def get_quadrant(ctr, cvr, avg_ctr, avg_cvr):
    """Determine performance quadrant"""
    if ctr >= avg_ctr and cvr >= avg_cvr:
        return 'High Performing', '#22c55e'
    elif ctr >= avg_ctr and cvr < avg_cvr:
        return 'Low CVR', '#eab308'
    elif ctr < avg_ctr and cvr >= avg_cvr:
        return 'Niche', '#3b82f6'
    else:
        return 'Underperforming', '#ef4444'

def call_similarity_api(prompt, api_key):
    """Call Anthropic API with retry logic"""
    if not api_key:
        return None
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code == 429:  # Rate limit
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            text = data['content'][0]['text']
            clean_text = text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_text)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    
    return None

def fetch_page_content(url):
    """Fetch and clean page content"""
    if not url or pd.isna(url) or str(url).lower() == 'null':
        return ""
    
    try:
        clean_page_url = clean_url(url)
        response = requests.get(clean_page_url, timeout=10, 
                              headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                            'iframe', 'noscript']):
            element.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return text[:3000]
    except:
        return ""

def calculate_similarities(flow_data, api_key):
    """Calculate all three similarity scores"""
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
    
    results['kwd_to_ad'] = call_similarity_api(kwd_to_ad_prompt, api_key)
    time.sleep(1)  # Rate limiting
    
    # Only proceed if URL is valid
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
            
            results['ad_to_page'] = call_similarity_api(ad_to_page_prompt, api_key)
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
            
            results['kwd_to_page'] = call_similarity_api(kwd_to_page_prompt, api_key)
    
    return results

def render_similarity_card(title, data, key):
    """Render similarity score card"""
    if not data:
        st.warning(f"{title}: Data unavailable")
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
        <h4 style="margin:0; color: #d1d5db; font-size: 14px;">{title}</h4>
        <h2 style="margin: 10px 0; color: {color};">{score:.2%}</h2>
        <p style="margin:0; color: #9ca3af; font-size: 12px; text-transform: uppercase;">{band}</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Details", expanded=False):
        st.write(f"**Reason:** {data.get('reason', 'N/A')}")
        
        if 'keyword_match' in data:
            col1, col2, col3 = st.columns(3)
            col1.metric("Keyword Match", f"{data.get('keyword_match', 0):.2%}", help="Weight: 15%")
            col2.metric("Topic Match", f"{data.get('topic_match', 0):.2%}", help="Weight: 35%")
            col3.metric("Intent Match", f"{data.get('intent_match', 0):.2%}", help="Weight: 50%")
            st.info(f"**Intent:** {data.get('intent', 'N/A')}")
        elif 'brand_match' in data:
            col1, col2, col3 = st.columns(3)
            col1.metric("Topic Match", f"{data.get('topic_match', 0):.2%}", help="Weight: 30%")
            col2.metric("Brand Match", f"{data.get('brand_match', 0):.2%}", help="Weight: 20%")
            col3.metric("Promise Match", f"{data.get('promise_match', 0):.2%}", help="Weight: 50%")
        elif 'answer_quality' in data:
            col1, col2 = st.columns(2)
            col1.metric("Topic Match", f"{data.get('topic_match', 0):.2%}", help="Weight: 40%")
            col2.metric("Answer Quality", f"{data.get('answer_quality', 0):.2%}", help="Weight: 60%")
            st.info(f"**Intent:** {data.get('intent', 'N/A')}")

def render_serp_preview(flow_data, serp_templates, device_view, zoom_level):
    """Render SERP with replaced values"""
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_description = flow_data.get('ad_description', 'N/A')
    ad_display_url = flow_data.get('ad_display_url', 'N/A')
    
    # Try to use template if available
    if serp_templates and len(serp_templates) > 0:
        try:
            serp_html = serp_templates[0].get('code', '')
            
            # Replace with regex for robustness
            serp_html = re.sub(
                r'Sponsored results for: "[^"]*"',
                f'Sponsored results for: "{keyword}"',
                serp_html
            )
            serp_html = re.sub(
                r'<div class="url">[^<]*</div>',
                f'<div class="url">{ad_display_url}</div>',
                serp_html,
                count=1
            )
            serp_html = re.sub(
                r'<div class="title">[^<]*</div>',
                f'<div class="title">{ad_title}</div>',
                serp_html,
                count=1
            )
            serp_html = re.sub(
                r'<div class="desc">[^<]*</div>',
                f'<div class="desc">{ad_description}</div>',
                serp_html,
                count=1
            )
            
            st.components.v1.html(serp_html, height=600, scrolling=True)
            return
        except:
            pass
    
    # Fallback simple preview
    device_width = {'mobile': 375, 'tablet': 768, 'laptop': 1440}[device_view]
    
    st.markdown(f"""
    <div style="background: white; padding: 20px; border-radius: 8px; width: {device_width * zoom_level / 100}px; overflow: auto;">
        <div style="color: #666; font-size: 12px; margin-bottom: 16px;">
            Sponsored results for: "{keyword}"
        </div>
        <div style="color: #666; font-size: 12px; margin: 16px 0 8px; padding-bottom: 8px; border-bottom: 1px solid #ddd;">
            Sponsored
        </div>
        <div style="color: #006621; font-size: 12px; margin-bottom: 8px;">
            {ad_display_url}
        </div>
        <div style="margin-bottom: 8px;">
            <a href="#" style="color: #1a0dab; font-size: 18px; font-weight: 500; text-decoration: none;">
                {ad_title}
            </a>
        </div>
        <div style="color: #545454; font-size: 14px;">
            {ad_description}
        </div>
    </div>
    """, unsafe_allow_html=True)

# Main App
st.title("📊 CPA Flow Mockup Tool")
st.markdown("*Visualize and analyze campaign performance flows*")

# Sidebar
with st.sidebar:
    st.header("🔐 API Configuration")
    
    # Load API key
    try:
        api_key_from_secrets = st.secrets.get("ANTHROPIC_API_KEY")
        if api_key_from_secrets:
            st.session_state.api_key = api_key_from_secrets
            st.success("✓ API key from secrets")
    except:
        pass
    
    if not st.session_state.api_key:
        api_key_input = st.text_input("Anthropic API Key", type="password")
        if api_key_input:
            st.session_state.api_key = api_key_input
    
    st.divider()
    st.header("📁 Data Loading")
    
    if st.button("🔄 Load Data from Google Drive", type="primary"):
        with st.spinner("Loading files..."):
            st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
            if st.session_state.data_a is not None:
                st.success(f"✓ File A: {len(st.session_state.data_a)} rows")
            
            st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
            if st.session_state.data_b is not None:
                st.success(f"✓ File B: {len(st.session_state.data_b)} templates")
    
    st.divider()
    st.header("⚙️ Settings")
    device_view = st.radio("Device View", ['mobile', 'tablet', 'laptop'], horizontal=True)
    zoom_level = st.slider("Zoom Level", 50, 200, 100, 10, format="%d%%")

# Main Content
if st.session_state.data_a is not None:
    df = st.session_state.data_a
    
    # Validate columns
    required_cols = ['Advertiser_Name', 'Campaign_Name', 'keyword_term', 
                    'publisher_url', 'impressions', 'clicks', 'conversions',
                    'ad_title', 'ad_description', 'ad_display_url', 'reporting_destination_url']
    missing = [c for c in required_cols if c not in df.columns]
    
    if missing:
        st.error(f"❌ Missing columns: {', '.join(missing)}")
        st.info(f"Available: {', '.join(df.columns)}")
        st.stop()
    
    # Campaign Selection
    col1, col2 = st.columns(2)
    
    with col1:
        advertisers = sorted(df['Advertiser_Name'].dropna().unique())
        selected_advertiser = st.selectbox("Advertiser", [''] + advertisers)
    
    with col2:
        if selected_advertiser:
            campaigns = sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique())
            selected_campaign = st.selectbox("Campaign", [''] + campaigns)
        else:
            selected_campaign = st.selectbox("Campaign", [''], disabled=True)
    
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
        
        # Main Layout
        left_col, right_col = st.columns([6, 4])
        
        with left_col:
            st.subheader("🔑 Keyword Selection")
            
            keyword_agg = campaign_df.groupby('keyword_term').agg({
                'impressions': 'sum', 'clicks': 'sum', 'conversions': 'sum'
            }).reset_index()
            
            keyword_agg['ctr'] = keyword_agg.apply(
                lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
            keyword_agg['cvr'] = keyword_agg.apply(
                lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
            
            # Bubble Chart
            bubble_data = keyword_agg.nlargest(5, 'clicks')
            
            fig = go.Figure()
            for _, row in bubble_data.iterrows():
                quadrant, color = get_quadrant(row['ctr'], row['cvr'], avg_ctr, avg_cvr)
                fig.add_trace(go.Scatter(
                    x=[row['ctr']], y=[row['cvr']],
                    mode='markers',
                    marker=dict(size=max(10, min(50, row['clicks']/10)), 
                               color=color, line=dict(width=2, color='white')),
                    name=row['keyword_term'][:30],
                    text=f"{row['keyword_term']}<br>CTR: {row['ctr']:.2f}%<br>CVR: {row['cvr']:.2f}%",
                    hovertemplate='%{text}<extra></extra>'
                ))
            
            fig.add_hline(y=avg_cvr, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=avg_ctr, line_dash="dash", line_color="gray", opacity=0.5)
            
            fig.update_layout(
                xaxis_title="CTR (%)", yaxis_title="CVR (%)", height=400,
                showlegend=False, plot_bgcolor='#1f2937', paper_bgcolor='#1f2937',
                font=dict(color='white'),
                xaxis=dict(gridcolor='#374151'), yaxis=dict(gridcolor='#374151')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Filters
            f1, f2, f3 = st.columns(3)
            keyword_filter = f1.selectbox("Filter", ['all', 'best', 'worst'])
            keyword_limit = f2.selectbox("Show", [5, 10, 25, 50])
            keyword_sort = f3.selectbox("Sort by", ['clicks', 'ctr', 'cvr'])
            keyword_search = st.text_input("🔍 Search keywords", "")
            
            filtered_keywords = keyword_agg.copy()
            
            if keyword_filter == 'best':
                filtered_keywords = filtered_keywords[
                    (filtered_keywords['ctr'] >= avg_ctr) & 
                    (filtered_keywords['cvr'] >= avg_cvr)]
            elif keyword_filter == 'worst':
                filtered_keywords = filtered_keywords[
                    (filtered_keywords['ctr'] < avg_ctr) & 
                    (filtered_keywords['cvr'] < avg_cvr)]
            
            if keyword_search:
                filtered_keywords = filtered_keywords[
                    filtered_keywords['keyword_term'].str.contains(keyword_search, case=False, na=False)]
            
            filtered_keywords = filtered_keywords.sort_values(keyword_sort, ascending=False).head(keyword_limit)
            
            # Table
            display_df = filtered_keywords[['keyword_term', 'clicks', 'ctr', 'cvr']].copy()
            display_df.columns = ['Keyword', 'Clicks', 'CTR (%)', 'CVR (%)']
            display_df['CTR (%)'] = display_df['CTR (%)'].apply(lambda x: f"{x:.2f}")
            display_df['CVR (%)'] = display_df['CVR (%)'].apply(lambda x: f"{x:.2f}")
            
            selected_kwd = st.dataframe(display_df, use_container_width=True, 
                                       hide_index=True, on_select="rerun", selection_mode="single-row")
            
            if selected_kwd and len(selected_kwd['selection']['rows']) > 0:
                idx = selected_kwd['selection']['rows'][0]
                new_keyword = filtered_keywords.iloc[idx]['keyword_term']
                if new_keyword != st.session_state.selected_keyword:
                    st.session_state.selected_keyword = new_keyword
                    st.session_state.flow_index = 0
                    st.session_state.similarities = {}
        
        with right_col:
            st.subheader("🔗 URL Selection")
            
            url_agg = campaign_df.groupby('publisher_url').agg({
                'impressions': 'sum', 'clicks': 'sum', 'conversions': 'sum'
            }).reset_index()
            
            url_agg['ctr'] = url_agg.apply(
                lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
            url_agg['cvr'] = url_agg.apply(
                lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
            
            u1, u2, u3 = st.columns(3)
            url_filter = u1.selectbox("Filter ", ['all', 'best', 'worst'], key='uf')
            url_limit = u2.selectbox("Show ", [5, 10, 25, 50], key='ul')
            url_sort = u3.selectbox("Sort by ", ['clicks', 'ctr', 'cvr'], key='us')
            
            filtered_urls = url_agg.copy()
            
            if url_filter == 'best':
                filtered_urls = filtered_urls[
                    (filtered_urls['ctr'] >= avg_ctr) & 
                    (filtered_urls['cvr'] >= avg_cvr)]
            elif url_filter == 'worst':
                filtered_urls = filtered_urls[
                    (filtered_urls['ctr'] < avg_ctr) & 
                    (filtered_urls['cvr'] < avg_cvr)]
            
            filtered_urls = filtered_urls.sort_values(url_sort, ascending=False).head(url_limit)
            filtered_urls['display_url'] = filtered_urls['publisher_url'].apply(
                lambda x: x[:50] + '...' if len(str(x)) > 50 else x)
            
            display_url_df = filtered_urls[['display_url', 'clicks', 'ctr', 'cvr']].copy()
            display_url_df.columns = ['Publisher URL', 'Clicks', 'CTR (%)', 'CVR (%)']
            display_url_df['CTR (%)'] = display_url_df['CTR (%)'].apply(lambda x: f"{x:.2f}")
            display_url_df['CVR (%)'] = display_url_df['CVR (%)'].apply(lambda x: f"{x:.2f}")
            
            selected_url_idx = st.dataframe(display_url_df, use_container_width=True,
                                           hide_index=True, on_select="rerun", selection_mode="single-row")
            
            if selected_url_idx and len(selected_url_idx['selection']['rows']) > 0:
                idx = selected_url_idx['selection']['rows'][0]
                new_url = filtered_urls.iloc[idx]['publisher_url']
                if new_url != st.session_state.selected_url:
                    st.session_state.selected_url = new_url
                    st.session_state.flow_index = 0
                    st.session_state.similarities = {}
        
        # Flow Analysis
        if st.session_state.selected_keyword and st.session_state.selected_url:
            # Check if keyword/URL changed
            current_pair = (st.session_state.selected_keyword, st.session_state.selected_url)
            if current_pair != st.session_state.last_keyword_url:
                st.session_state.flow_index = 0
                st.session_state.similarities = {}
                st.session_state.last_keyword_url = current_pair
            
            st.divider()
            st.header("📈 Flow Analysis")
            
            flows = campaign_df[
                (campaign_df['keyword_term'] == st.session_state.selected_keyword) &
                (campaign_df['publisher_url'] == st.session_state.selected_url)
            ].sort_values('clicks', ascending=False).head(5)
            
            # Prioritize non-null URLs
            non_null = flows[
                flows['reporting_destination_url'].notna() & 
                (flows['reporting_destination_url'].str.lower() != 'null') &
                (flows['reporting_destination_url'] != '')
            ]
            
            st.session_state.flows = (non_null if len(non_null) > 0 else flows).to_dict('records')
            
            if len(st.session_state.flows) > 0:
                # Navigation
                col_info, col_nav = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"""
                    **Keyword:** `{st.session_state.selected_keyword}`  
                    **URL:** `{st.session_state.selected_url[:60]}...`
                    """)
                
                with col_nav:
                    if len(st.session_state.flows) > 1:
                        c1, c2, c3 = st.columns([1, 2, 1])
                        if c1.button("◀", key="prev"):
                            st.session_state.flow_index = max(0, st.session_state.flow_index - 1)
                            st.session_state.similarities = {}
                            st.rerun()
                        c2.markdown(f"<center>Flow {st.session_state.flow_index + 1}/{len(st.session_state.flows)}</center>", 
                                   unsafe_allow_html=True)
                        if c3.button("▶", key="next"):
                            st.session_state.flow_index = min(len(st.session_state.flows) - 1, 
                                                             st.session_state.flow_index + 1)
                            st.session_state.similarities = {}
                            st.rerun()
                
                current_flow = st.session_state.flows[st.session_state.flow_index]
                
                # Auto-calculate similarities
                if (not st.session_state.similarities or 
                    st.session_state.similarities.get('flow_id') != current_flow.get('creative_id')):
                    if st.session_state.api_key:
                        with st.spinner("Calculating similarity scores..."):
                            st.session_state.similarities = calculate_similarities(
                                current_flow, st.session_state.api_key)
                            st.session_state.similarities['flow_id'] = current_flow.get('creative_id')
                    else:
                        st.warning("⚠️ Add API key to calculate similarities")
                
                # Show Scores
                if st.session_state.similarities and st.session_state.similarities.get('kwd_to_ad'):
                    st.subheader("🎯 Similarity Scores")
                    s1, s2, s3 = st.columns(3)
                    with s1:
                        render_similarity_card("Keyword → Ad", 
                                             st.session_state.similarities.get('kwd_to_ad'), 'ka')
                    with s2:
                        render_similarity_card("Keyword → Page", 
                                             st.session_state.similarities.get('kwd_to_page'), 'kp')
                    with s3:
                        render_similarity_card("Ad → Page", 
                                             st.session_state.similarities.get('ad_to_page'), 'ap')
                    st.divider()
                
                # Visual Flow
                st.subheader("🖥️ Visual Flow")
                
                # SERP
                st.markdown("### SERP Preview")
                prev_col, det_col = st.columns([6, 4])
                
                with prev_col:
                    render_serp_preview(current_flow, st.session_state.data_b, device_view, zoom_level)
                
                with det_col:
                    st.markdown("**SERP Details**")
                    st.text(f"Template: {current_flow.get('serp_template_name', 'N/A')}")
                    st.text(f"Title: {current_flow.get('ad_title', 'N/A')[:40]}...")
                    st.text(f"Display URL: {current_flow.get('ad_display_url', 'N/A')}")
                
                st.divider()
                
                # Landing Page
                st.markdown("### Landing Page Preview")
                lp_col, lpd_col = st.columns([6, 4])
                
                with lp_col:
                    dest_url = current_flow.get('reporting_destination_url', '')
                    if dest_url and pd.notna(dest_url) and str(dest_url).lower() != 'null' and str(dest_url).strip():
                        device_width = {'mobile': 375, 'tablet': 768, 'laptop': 1440}[device_view]
                        st.components.v1.iframe(dest_url, width=device_width * zoom_level // 100, 
                                               height=600, scrolling=True)
                    else:
                        st.warning("⚠️ Landing page URL is null")
                
                with lpd_col:
                    st.markdown("**Performance**")
                    st.metric("Impressions", f"{safe_int(current_flow.get('impressions', 0)):,}")
                    st.metric("Clicks", f"{safe_int(current_flow.get('clicks', 0)):,}")
                    st.metric("Conversions", f"{safe_int(current_flow.get('conversions', 0)):,}")
                    st.metric("CTR", f"{safe_float(current_flow.get('ctr', 0)):.2f}%")
                    st.metric("CVR", f"{safe_float(current_flow.get('cvr', 0)):.2f}%")
            else:
                st.warning("No flows found for this combination.")
else:
    st.info("👆 Click 'Load Data from Google Drive' in sidebar")
    
    st.markdown("""
    ### 📋 Setup Checklist:
    
    #### 1️⃣ Prepare Google Drive Files
    - Upload **File A** (CSV) and **File B** (JSON) to Google Drive
    - Share both as **"Anyone with the link can view"**
    - Get file IDs from URLs
    
    #### 2️⃣ Update Code Configuration
    Replace these lines (top of code):
    ```python
    FILE_A_ID = "your-file-a-id-here"
    FILE_B_ID = "your-file-b-id-here"
    ```
    
    #### 3️⃣ Add API Key to Streamlit Secrets
    In Streamlit Cloud → App Settings → Secrets:
    ```toml
    ANTHROPIC_API_KEY = "sk-ant-api03-..."
    ```
    
    #### 4️⃣ Deploy!
    - Push to GitHub
    - Deploy on Streamlit Cloud
    - Click "Load Data" button
    
    ---
    
    **File A Format:** CSV with columns including `keyword_term`, `ad_title`, `ad_description`, etc.
    
    **File B Format:** JSON array: `[{"url": "...", "code": "<html>...</html>"}]`
    """)