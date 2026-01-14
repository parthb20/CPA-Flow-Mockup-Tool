# -*- coding: utf-8 -*-
"""
CPA Flow Analysis Tool v2
Horizontal flow visualization with auto-selected best performing flows
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, quote, urljoin
import re
from io import StringIO, BytesIO
import time
import base64
import html
import zipfile
import gzip
import tempfile
import os

# Page config - MUST be first Streamlit command
st.set_page_config(page_title="CPA Flow Analysis v2", page_icon="📊", layout="wide")

# Try to import gdown (better for large files)
try:
    import gdown
    GDOWN_AVAILABLE = True
except:
    GDOWN_AVAILABLE = False

# Custom CSS
st.markdown("""
    <style>
    /* Background */
    .main { background-color: #f8fafc !important; }
    .stApp { background-color: #f8fafc !important; }
    
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
    
    /* Buttons */
    .stButton > button {
        background-color: white !important;
        color: #0f172a !important;
        border: 2px solid #cbd5e1 !important;
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
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background: white !important;
        color: #0f172a !important;
        border: 2px solid #e2e8f0 !important;
    }
    
    /* Dropdowns */
    [data-baseweb="select"] { background-color: white !important; }
    [data-baseweb="select"] > div { 
        background-color: white !important; 
        border-color: #cbd5e1 !important; 
    }
    [data-baseweb="select"] span { 
        color: #0f172a !important; 
        font-weight: 500 !important; 
        font-size: 16px !important; 
    }
    [role="listbox"] { 
        background-color: white !important; 
    }
    [role="option"] { 
        background-color: white !important; 
        color: #0f172a !important; 
    }
    [role="option"]:hover { 
        background-color: #f1f5f9 !important; 
    }
    [role="option"][aria-selected="true"] { 
        background-color: #e0f2fe !important; 
        color: #0369a1 !important; 
    }
    
    /* Metrics */
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
    
    /* Flow Card */
    .flow-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .stage-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        height: 100%;
        transition: all 0.3s ease;
    }
    
    .stage-card:hover {
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.15);
        border-color: #3b82f6;
    }
    
    .stage-title {
        font-size: 18px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .flow-stage {
        text-align: center;
        padding: 16px;
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border: 2px solid #3b82f6;
        border-radius: 8px;
        margin: 0 10px;
    }
    
    .flow-arrow {
        font-size: 32px;
        color: #3b82f6;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 5px;
    }
    
    .similarity-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 2px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .score-box {
        display: inline-block;
        padding: 16px 24px;
        border-radius: 10px;
        border: 3px solid;
        font-size: 42px;
        font-weight: 700;
        margin: 15px 0;
    }
    
    .score-excellent { border-color: #22c55e; background: linear-gradient(135deg, #22c55e15, #22c55e08); color: #22c55e; }
    .score-good { border-color: #3b82f6; background: linear-gradient(135deg, #3b82f615, #3b82f608); color: #3b82f6; }
    .score-moderate { border-color: #eab308; background: linear-gradient(135deg, #eab30815, #eab30808); color: #eab308; }
    .score-weak { border-color: #f97316; background: linear-gradient(135deg, #f9731615, #f9731608); color: #f97316; }
    .score-poor { border-color: #ef4444; background: linear-gradient(135deg, #ef444415, #ef444408); color: #ef4444; }
    
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
    
    /* Dataframe styling */
    [data-testid="stDataFrame"] {
        background-color: white !important;
    }
    [data-testid="stDataFrame"] table {
        background-color: white !important;
    }
    [data-testid="stDataFrame"] th {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
        font-weight: 700 !important;
    }
    [data-testid="stDataFrame"] td {
        background-color: white !important;
        color: #0f172a !important;
    }
    </style>
""", unsafe_allow_html=True)

# Config

# Get ID from: https://drive.google.com/file/d/FILE_ID_HERE/view
# File should be compressed (.gz) and < 100MB for best performance
FILE_A_ID = "17_JKUhXfBYlWZZEKUStRgFQhL3Ty-YZu"  # ← UPDATE THIS with your Google Drive file ID
try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
except Exception as e:
    API_KEY = ""

# Session state
for key in ['data_a', 'loading_done', 'default_flow', 'current_flow', 'view_mode', 'flow_layout', 'similarities', 'last_campaign_key']:
    if key not in st.session_state:
        if key == 'view_mode':
            st.session_state[key] = 'basic'
        elif key == 'flow_layout':
            st.session_state[key] = 'horizontal'
        else:
            st.session_state[key] = None

def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive - handles CSV, ZIP, GZIP, and large file virus scan"""
    
    # Method 1: Try gdown if available (best for large files)
    if GDOWN_AVAILABLE:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                url = f"https://drive.google.com/uc?id={file_id}"
                output = tmp_file.name
                
                gdown.download(url, output, quiet=True, fuzzy=True)
                
                # Read the downloaded file
                with open(output, 'rb') as f:
                    content = f.read()
                
                # Clean up
                try:
                    os.unlink(output)
                except:
                    pass
                
                # Process the content (detect type and decompress if needed)
                return process_file_content(content)
                
        except Exception as e:
            pass  # Silently try alternative
    
    # Method 2: Manual download (fallback)
    try:
        session = requests.Session()
        
        # Initial request
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = session.get(url, timeout=30, stream=False)
        
        content = response.content
        
        # Check for virus scan warning or download confirmation (handle silently)
        if b'virus scan warning' in content.lower() or b'download anyway' in content.lower() or content.startswith(b'<!DOCTYPE'):
            text = content.decode('utf-8', errors='ignore')
            
            # Try to find confirmation token
            confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', text)
            if confirm_match:
                confirm = confirm_match.group(1)
                url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm}"
                response = session.get(url, timeout=60, stream=False)
                content = response.content
            else:
                download_match = re.search(r'href="(/uc\?[^"]*export=download[^"]*)"', text)
                if download_match:
                    download_path = download_match.group(1).replace('&amp;', '&')
                    url = f"https://drive.google.com{download_path}"
                    response = session.get(url, timeout=60, stream=False)
                    content = response.content
                else:
                    return None
        
        if response.status_code != 200:
            return None
        
        # Process the content
        return process_file_content(content)
            
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.info("💡 Make sure the file is shared with 'Anyone with the link'")
        return None

def process_file_content(content):
    """Process file content - detect type and decompress if needed"""
    try:
        # Check if Google Drive returned HTML error page
        if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html') or b'<title>Google Drive' in content[:1000]:
            st.error("❌ Could not download file - check sharing settings")
            return None
        
        # Check file type by magic bytes
        # GZIP: 1f 8b
        if len(content) >= 2 and content[:2] == b'\x1f\x8b':
            try:
                # Decompress GZIP
                with gzip.open(BytesIO(content), 'rb') as gz_file:
                    decompressed = gz_file.read()
                
                # Read as CSV with error handling for malformed lines
                df = pd.read_csv(
                    BytesIO(decompressed), 
                    dtype=str, 
                    on_bad_lines='skip',  # Skip malformed rows
                    encoding='utf-8',
                    engine='python',  # Python engine is more forgiving
                    quoting=1  # Handle quoted fields properly
                )
                return df
            except Exception as e:
                st.error(f"❌ Error decompressing GZIP: {str(e)}")
                return None
        
        # ZIP: 50 4b (PK)
        elif len(content) >= 2 and content[:2] == b'PK':
            try:
                with zipfile.ZipFile(BytesIO(content)) as zip_file:
                    # Find CSV file
                    csv_file = None
                    for filename in zip_file.namelist():
                        if filename.lower().endswith('.csv'):
                            csv_file = filename
                            break
                    
                    if csv_file:
                        csv_content = zip_file.read(csv_file)
                        df = pd.read_csv(
                            BytesIO(csv_content), 
                            dtype=str, 
                            on_bad_lines='skip',
                            encoding='utf-8',
                            engine='python'
                        )
                        return df
                    else:
                        st.error("❌ No CSV file found in ZIP")
                        return None
            except Exception as e:
                st.error(f"❌ Error extracting ZIP: {str(e)}")
                return None
        else:
            # Try as CSV
            try:
                df = pd.read_csv(
                    StringIO(content.decode('utf-8')), 
                    dtype=str, 
                    on_bad_lines='skip',
                    encoding='utf-8',
                    engine='python'
                )
                return df
            except Exception as e:
                st.error(f"❌ CSV parse error: {str(e)}")
                return None
                
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
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

def call_similarity_api(prompt):
    """Call FastRouter API for similarity scoring"""
    if not API_KEY:
        return {
            "error": True,
            "status_code": "no_api_key",
            "body": "FASTROUTER_API_KEY not found in Streamlit secrets"
        }
    
    try:
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
    except Exception as e:
        return {
            "error": True,
            "status_code": "api_error",
            "body": str(e)
        }

def fetch_page_content(url):
    """Fetch page content for similarity analysis"""
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
    """Calculate all three similarity scores"""
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

def get_score_class(score):
    """Get CSS class based on score"""
    if score >= 0.8:
        return "score-excellent", "Excellent", "#22c55e"
    elif score >= 0.6:
        return "score-good", "Good", "#3b82f6"
    elif score >= 0.4:
        return "score-moderate", "Moderate", "#eab308"
    elif score >= 0.2:
        return "score-weak", "Weak", "#f97316"
    else:
        return "score-poor", "Poor", "#ef4444"

def find_default_flow(df):
    """Find the best performing flow based on conversions and recency"""
    try:
        # Convert numeric columns
        df['conversions'] = df['conversions'].apply(safe_float)
        df['impressions'] = df['impressions'].apply(safe_float)
        df['clicks'] = df['clicks'].apply(safe_float)
        
        # Ensure ts is datetime
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
        
        # Get domain from publisher_url or Serp_URL if publisher_domain doesn't exist
        if 'publisher_domain' not in df.columns:
            if 'publisher_url' in df.columns:
                df['publisher_domain'] = df['publisher_url'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
            elif 'Serp_URL' in df.columns:
                df['publisher_domain'] = df['Serp_URL'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
        
        # Step 1: Find keyword_domain combination with most conversions
        if 'publisher_domain' in df.columns:
            kwd_domain_conv = df.groupby(['keyword_term', 'publisher_domain'])['conversions'].sum().reset_index()
            best_kwd_domain = kwd_domain_conv.nlargest(1, 'conversions').iloc[0]
            
            # Filter to this combination
            filtered = df[
                (df['keyword_term'] == best_kwd_domain['keyword_term']) &
                (df['publisher_domain'] == best_kwd_domain['publisher_domain'])
            ]
        else:
            # Fallback: just use keyword
            kwd_conv = df.groupby('keyword_term')['conversions'].sum().reset_index()
            best_kw = kwd_conv.nlargest(1, 'conversions').iloc[0]['keyword_term']
            filtered = df[df['keyword_term'] == best_kw]
        
        # Step 2: Find SERP template with most conversions
        if 'serp_template_name' in filtered.columns:
            serp_conv = filtered.groupby('serp_template_name')['conversions'].sum().reset_index()
            best_serp = serp_conv.nlargest(1, 'conversions').iloc[0]['serp_template_name']
            filtered = filtered[filtered['serp_template_name'] == best_serp]
        elif 'serp_template_id' in filtered.columns:
            serp_conv = filtered.groupby('serp_template_id')['conversions'].sum().reset_index()
            best_serp = serp_conv.nlargest(1, 'conversions').iloc[0]['serp_template_id']
            filtered = filtered[filtered['serp_template_id'] == best_serp]
        
        # Step 3: Find publisher_url with most conversions
        if 'publisher_url' in filtered.columns:
            url_conv = filtered.groupby('publisher_url')['conversions'].sum().reset_index()
            best_url = url_conv.nlargest(1, 'conversions').iloc[0]['publisher_url']
            filtered = filtered[filtered['publisher_url'] == best_url]
        
        # Step 4: Get most recent view_id (MAX(ts))
        if 'ts' in filtered.columns:
            best_flow = filtered.nlargest(1, 'ts').iloc[0]
        else:
            best_flow = filtered.iloc[0]
        
        return best_flow.to_dict()
    
    except Exception as e:
        st.error(f"Error finding default flow: {str(e)}")
        return None

def render_mini_device_preview(content, is_url=False, device='mobile'):
    """Render device preview with realistic chrome for mobile/tablet/laptop
    
    Args:
        content: URL or HTML content
        is_url: If True, tries iframe src first
        device: 'mobile', 'tablet', or 'laptop'
    """
    # Real device dimensions
    if device == 'mobile':
        device_w = 390
        container_height = 844
        scale = 0.35
        frame_style = "border-radius: 40px; border: 10px solid #000000;"
        
        # Mobile chrome
        device_chrome = """
        <div style="background: #000; color: white; padding: 6px 20px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 500;">
            <div>9:41</div>
            <div style="display: flex; gap: 4px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style="background: #f7f7f7; border-bottom: 1px solid #d1d1d1; padding: 8px 12px; display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; background: white; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid #e0e0e0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #666; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">URL</span>
                <span style="font-size: 16px;">🔄</span>
            </div>
        </div>
        """
        
        bottom_nav = """
        <div style="position: fixed; bottom: 0; left: 0; right: 0; background: #f7f7f7; border-top: 1px solid #d1d1d1; padding: 8px; display: flex; justify-content: space-around; align-items: center;">
            <div style="text-align: center; font-size: 20px;">◀️</div>
            <div style="text-align: center; font-size: 20px;">▶️</div>
            <div style="text-align: center; font-size: 20px;">↻</div>
            <div style="text-align: center; font-size: 20px;">⊞</div>
        </div>
        """
        chrome_height = "90px"
        
    elif device == 'tablet':
        device_w = 820
        container_height = 1180
        scale = 0.25
        frame_style = "border-radius: 16px; border: 12px solid #1f2937;"
        
        # Tablet chrome
        device_chrome = """
        <div style="background: #000; color: white; padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500;">
            <div style="display: flex; gap: 12px;">
                <span>9:41 AM</span>
                <span>Wed Jan 13</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style="background: #f0f0f0; border-bottom: 1px solid #d0d0d0; padding: 12px 16px; display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 20px;">◀️</span>
            <span style="font-size: 20px;">▶️</span>
            <span style="font-size: 20px;">↻</span>
            <div style="flex: 1; background: white; border-radius: 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;">
                <span style="font-size: 18px;">🔒</span>
                <span style="color: #666; font-size: 15px; flex: 1;">URL</span>
            </div>
            <span style="font-size: 20px;">⊞</span>
            <span style="font-size: 20px;">⋮</span>
        </div>
        """
        bottom_nav = ""
        chrome_height = "60px"
        
    else:  # laptop
        device_w = 1440
        container_height = 900
        scale = 0.2
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        
        # Laptop chrome
        device_chrome = """
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
                <span style="color: #333; font-size: 14px; flex: 1;">https://URL</span>
                <span style="font-size: 16px;">⭐</span>
            </div>
            <span style="font-size: 18px; margin-left: 8px;">⊞</span>
            <span style="font-size: 18px;">⋮</span>
        </div>
        """
        bottom_nav = ""
        chrome_height = "52px"
    
    display_w = int(device_w * scale)
    display_h = int(container_height * scale)
    
    if is_url:
        iframe_content = f'<iframe src="{content}" style="width: 100%; height: 100%; border: none;"></iframe>'
    else:
        iframe_content = content
    
    full_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width={device_w}, initial-scale=1.0">
        <style>
            body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
            .chrome {{ width: 100%; background: white; position: fixed; top: 0; left: 0; right: 0; z-index: 100; }}
            .content {{ position: absolute; top: {chrome_height}; bottom: {'50px' if device == 'mobile' else '0'}; left: 0; right: 0; overflow-y: auto; }}
            .bottom-nav {{ position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; }}
        </style>
    </head>
    <body>
        <div class="chrome">{device_chrome}</div>
        <div class="content">{iframe_content}</div>
        {f'<div class="bottom-nav">{bottom_nav}</div>' if device == 'mobile' else ''}
    </body>
    </html>
    """
    
    escaped = full_content.replace("'", "&apos;").replace('"', '&quot;')
    
    html = f"""
    <div style="display: flex; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 8px;">
        <div style="width: {display_w}px; height: {display_h}px; {frame_style} overflow: hidden; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
            <iframe srcdoc='{escaped}' style="width: {device_w}px; height: {container_height}px; border: none; transform: scale({scale}); transform-origin: 0 0; display: block; background: white;"></iframe>
        </div>
    </div>
    """
    
    return html, display_h + 30, is_url

def unescape_adcode(adcode):
    """
    Unescape the adcode string properly (from Flask app logic)
    Handles both \\u003c (double-escaped) and \u003c (single-escaped)
    """
    # Check if this is double-escaped (contains literal \u sequences)
    if '\\u' in adcode or '\\/' in adcode or '\\"' in adcode:
        try:
            # This is double-escaped - parse it again as JSON
            # Wrap it in quotes and parse as JSON string
            adcode = json.loads('"' + adcode + '"')
        except:
            # If that fails, try manual unicode escape decoding
            try:
                adcode = adcode.encode('utf-8').decode('unicode_escape')
            except:
                pass
    
    # Then unescape HTML entities if any
    adcode = html.unescape(adcode)
    
    return adcode

def parse_creative_html(response_str):
    """Parse response JSON and extract HTML with proper unescaping"""
    try:
        if not response_str or pd.isna(response_str):
            return None, None
        
        # Check if JSON is double-stringified
        if str(response_str).startswith('{\\'):
            try:
                response_str = json.loads('"' + response_str + '"')
            except:
                pass
        
        # Parse JSON
        response_data = json.loads(response_str)
        
        # Get adcode (escaped HTML with unicode escapes)
        raw_adcode = response_data.get('adcode', '')
        
        if not raw_adcode:
            return None, None
        
        # Unescape using Flask app logic
        adcode = unescape_adcode(raw_adcode)
        
        # Get metadata
        metadata = {
            'adomain': response_data.get('adomain', 'N/A'),
            'ecrid': response_data.get('ecrid', 'N/A')
        }
        
        # Try to extract dimensions from adcode
        size_match = re.search(r'(\d{2,4})\s*[x×]\s*(\d{2,4})', raw_adcode)
        if size_match:
            metadata['dimensions'] = f"{size_match.group(1)}×{size_match.group(2)}"
        
        # Wrap in HTML structure WITHOUT responsive constraints (original dimensions)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ 
                    margin: 0; 
                    padding: 0; 
                    background: white; 
                    font-family: Arial, sans-serif;
                }}
                /* Keep original dimensions - don't force responsive */
            </style>
        </head>
        <body>
            {adcode}
        </body>
        </html>
        """
        
        return html, raw_adcode
        
    except Exception as e:
        st.error(f"Error parsing creative: {str(e)}")
        return None, None


# Simple title at top (Streamlit handles styling)
st.title("📊 CPA Flow Analysis v2")

# Auto-load from Google Drive (silent loading)
if not st.session_state.loading_done:
    with st.spinner("Loading data..."):
        try:
            st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
            st.session_state.loading_done = True
        except Exception as e:
            st.error(f"❌ Error loading data")
            st.session_state.loading_done = True

# View mode toggle
view_col1, view_col2, view_col3 = st.columns([1, 1, 4])
with view_col1:
    if st.button("📊 Basic View", type="primary" if st.session_state.view_mode == 'basic' else "secondary"):
        st.session_state.view_mode = 'basic'
        st.rerun()
with view_col2:
    if st.button("⚙️ Advanced View", type="primary" if st.session_state.view_mode == 'advanced' else "secondary"):
        st.session_state.view_mode = 'advanced'
        st.rerun()

st.divider()

if st.session_state.data_a is not None and len(st.session_state.data_a) > 0:
    df = st.session_state.data_a
    
    # Select Advertiser and Campaign
    col1, col2 = st.columns(2)
    with col1:
        advertisers = ['-- Select Advertiser --'] + sorted(df['Advertiser_Name'].dropna().unique().tolist())
        selected_advertiser = st.selectbox("Advertiser", advertisers)
    
    if selected_advertiser and selected_advertiser != '-- Select Advertiser --':
        with col2:
            campaigns = ['-- Select Campaign --'] + sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique().tolist())
            selected_campaign = st.selectbox("Campaign", campaigns, key='campaign_selector')
        
        # Reset flow when campaign changes
        campaign_key = f"{selected_advertiser}_{selected_campaign}"
        if 'last_campaign_key' not in st.session_state:
            st.session_state.last_campaign_key = None
        
        if st.session_state.last_campaign_key != campaign_key:
            st.session_state.default_flow = None
            st.session_state.current_flow = None
            st.session_state.similarities = None
            st.session_state.last_campaign_key = campaign_key
        
        if selected_campaign and selected_campaign != '-- Select Campaign --':
            campaign_df = df[(df['Advertiser_Name'] == selected_advertiser) & (df['Campaign_Name'] == selected_campaign)].copy()
            
            # Calculate metrics
            campaign_df['impressions'] = campaign_df['impressions'].apply(safe_float)
            campaign_df['clicks'] = campaign_df['clicks'].apply(safe_float)
            campaign_df['conversions'] = campaign_df['conversions'].apply(safe_float)
            campaign_df['ctr'] = campaign_df.apply(lambda x: (x['clicks'] / x['impressions'] * 100) if x['impressions'] > 0 else 0, axis=1)
            campaign_df['cvr'] = campaign_df.apply(lambda x: (x['conversions'] / x['clicks'] * 100) if x['clicks'] > 0 else 0, axis=1)
            
            # Add publisher_domain if not present
            if 'publisher_domain' not in campaign_df.columns and 'publisher_url' in campaign_df.columns:
                campaign_df['publisher_domain'] = campaign_df['publisher_url'].apply(
                    lambda x: urlparse(str(x)).netloc if pd.notna(x) else ''
                )
            
            total_impressions = campaign_df['impressions'].sum()
            total_clicks = campaign_df['clicks'].sum()
            total_conversions = campaign_df['conversions'].sum()
            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            avg_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            
            st.divider()
            
            # Calculate weighted averages for coloring
            weighted_avg_ctr = avg_ctr  # Already calculated as weighted avg
            weighted_avg_cvr = avg_cvr  # Already calculated as weighted avg
            
            # Show aggregated table
            st.markdown("### 📊 Flow Combinations Overview")
            
            if 'publisher_domain' in campaign_df.columns and 'keyword_term' in campaign_df.columns:
                # Aggregate by domain + keyword
                agg_df = campaign_df.groupby(['publisher_domain', 'keyword_term']).agg({
                    'impressions': 'sum',
                    'clicks': 'sum',
                    'conversions': 'sum'
                }).reset_index()
                
                agg_df['CTR'] = agg_df.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                agg_df['CVR'] = agg_df.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                # Sort by conversions and show top 20
                agg_df = agg_df.sort_values('conversions', ascending=False).head(20)
                
                # Get landing URLs for each combo
                landing_urls = []
                for _, row in agg_df.iterrows():
                    matching = campaign_df[
                        (campaign_df['publisher_domain'] == row['publisher_domain']) &
                        (campaign_df['keyword_term'] == row['keyword_term'])
                    ]
                    if len(matching) > 0:
                        landing_urls.append(matching.iloc[0]['reporting_destination_url'])
                    else:
                        landing_urls.append('N/A')
                
                agg_df['Landing URL'] = landing_urls
                
                # Create display dataframe
                display_df = agg_df.copy()
                
                # Format columns
                display_df['Impressions'] = display_df['impressions'].apply(lambda x: f"{int(x):,}")
                display_df['Clicks'] = display_df['clicks'].apply(lambda x: f"{int(x):,}")
                display_df['Conversions'] = display_df['conversions'].apply(lambda x: f"{int(x):,}")
                display_df['CTR %'] = display_df['CTR'].apply(lambda x: f"{x:.2f}%")
                display_df['CVR %'] = display_df['CVR'].apply(lambda x: f"{x:.2f}%")
                
                # Select and order columns
                display_df = display_df[['publisher_domain', 'keyword_term', 'Impressions', 'Clicks', 'Conversions', 'CTR %', 'CVR %', 'Landing URL']]
                display_df.columns = ['Publisher Domain', 'Keyword', 'Impressions', 'Clicks', 'Conversions', 'CTR %', 'CVR %', 'Landing URL']
                
                # Style with column_config
                st.dataframe(
                    display_df,
                    column_config={
                        "CTR %": st.column_config.TextColumn(
                            "CTR %",
                            help="Click-through rate"
                        ),
                        "CVR %": st.column_config.TextColumn(
                            "CVR %",
                            help="Conversion rate"
                        ),
                        "Landing URL": st.column_config.LinkColumn(
                            "Landing URL",
                            help="Advertiser landing page"
                        )
                    },
                    hide_index=True,
                    height=600
                )
            else:
                st.warning("Could not generate table - missing required columns")
            
            st.divider()
            
            # Explain what a flow is
            st.info("""
            **🔄 What is a Flow?**
            
            A flow represents the complete user journey from seeing your ad to reaching your landing page:
            
            **Publisher** → **Creative** → **SERP** → **Landing Page**
            
            • Each combination of these elements creates a unique flow
            • We automatically select the best performing flow to display
            • You can customize any element to see how it affects the journey
            """)
            
            st.divider()
            
            # Find default flow if not set
            if st.session_state.default_flow is None:
                with st.spinner("Finding best performing flow..."):
                    st.session_state.default_flow = find_default_flow(campaign_df)
                    st.session_state.current_flow = st.session_state.default_flow.copy() if st.session_state.default_flow else None
            
            if st.session_state.current_flow:
                current_flow = st.session_state.current_flow
                
                # Flow layout toggle
                layout_col1, layout_col2, layout_col3, layout_col4 = st.columns([1, 1, 3, 1])
                with layout_col1:
                    if st.button("↔️ Horizontal", type="primary" if st.session_state.flow_layout == 'horizontal' else "secondary", key='horiz_btn'):
                        st.session_state.flow_layout = 'horizontal'
                        st.rerun()
                with layout_col2:
                    if st.button("↕️ Vertical", type="primary" if st.session_state.flow_layout == 'vertical' else "secondary", key='vert_btn'):
                        st.session_state.flow_layout = 'vertical'
                        st.rerun()
                
                # Advanced mode: Show keyword and domain filters
                if st.session_state.view_mode == 'advanced':
                    with layout_col3:
                        st.markdown("")  # spacing
                    with layout_col4:
                        st.markdown("")  # spacing
                    
                    st.divider()
                    
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                        selected_keyword_filter = st.selectbox("🔑 Filter by Keyword:", ['All'] + keywords, key='kw_filter_adv')
                    
                    with filter_col2:
                        if 'publisher_domain' in campaign_df.columns:
                            domains = sorted(campaign_df['publisher_domain'].dropna().unique().tolist())
                            selected_domain_filter = st.selectbox("🌐 Filter by Domain:", ['All'] + domains, key='dom_filter_adv')
                
                st.divider()
                
                if st.session_state.view_mode == 'basic':
                    st.success("✨ **Auto-Selected**: Best performing flow displayed. Expand '⚙️ Edit Details' on any card to customize.")
                else:
                    st.success("✨ **Best Flow**: Highest conversions + most recent data. Use filters above to rebuild flow.")
                
                # Build filter data
                keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                
                # Filter based on selections
                current_kw = current_flow.get('keyword_term', keywords[0] if keywords else '')
                kw_filtered = campaign_df[campaign_df['keyword_term'] == current_kw]
                
                domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in kw_filtered.columns else []
                current_dom = current_flow.get('publisher_domain', domains[0] if domains else '')
                dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == current_dom] if domains else kw_filtered
                
                urls = sorted(dom_filtered['publisher_url'].dropna().unique().tolist()) if 'publisher_url' in dom_filtered.columns else []
                current_url = current_flow.get('publisher_url', urls[0] if urls else '')
                url_filtered = dom_filtered[dom_filtered['publisher_url'] == current_url] if urls else dom_filtered
                
                serps = []
                if 'serp_template_name' in url_filtered.columns:
                    serps = sorted(url_filtered['serp_template_name'].dropna().unique().tolist())
                current_serp = current_flow.get('serp_template_name', serps[0] if serps else '')
                final_filtered = url_filtered[url_filtered['serp_template_name'] == current_serp] if serps else url_filtered
                
                if len(final_filtered) > 0:
                    current_flow.update(final_filtered.iloc[0].to_dict())
                
                # Update session state
                st.session_state.current_flow = current_flow
                
                # Show stats for current selection (only in advanced view)
                if st.session_state.view_mode == 'advanced' and len(final_filtered) > 0:
                    stats_df = final_filtered.agg({
                        'impressions': 'sum',
                        'clicks': 'sum',
                        'conversions': 'sum'
                    })
                    
                    st.markdown("#### 📈 Selected Flow Performance")
                    s1, s2, s3, s4, s5 = st.columns(5)
                    s1.metric("Impressions", f"{safe_int(stats_df['impressions']):,}")
                    s2.metric("Clicks", f"{safe_int(stats_df['clicks']):,}")
                    s3.metric("Conversions", f"{safe_int(stats_df['conversions']):,}")
                    s4.metric("CTR", f"{(stats_df['clicks']/stats_df['impressions']*100 if stats_df['impressions'] > 0 else 0):.2f}%")
                    s5.metric("CVR", f"{(stats_df['conversions']/stats_df['clicks']*100 if stats_df['clicks'] > 0 else 0):.2f}%")
                    
                    st.divider()
                
                # Flow Display based on layout
                st.markdown("### 🔄 Flow Journey")
                
                if st.session_state.flow_layout == 'horizontal':
                    # Add some spacing and styling for horizontal layout
                    st.markdown("""
                    <div style='background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); 
                                padding: 20px; border-radius: 12px; margin: 10px 0; 
                                border: 2px solid #e2e8f0;'>
                    </div>
                    """, unsafe_allow_html=True)
                    stage_cols = st.columns([1, 0.15, 1, 0.15, 1, 0.15, 1])
                else:
                    # Vertical layout - one card per row
                    stage_cols = None
                
                # Stage 1: Publisher URL
                stage_1_container = stage_cols[0] if stage_cols else st.container()
                with stage_1_container:
                    st.markdown('<div class="stage-card">', unsafe_allow_html=True)
                    st.markdown('<div class="stage-title">📰 Publisher URL</div>', unsafe_allow_html=True)
                    
                    # Device selector
                    device1 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev_pub', index=0, label_visibility="collapsed")
                    
                    # Only show edit details in advanced mode
                    if st.session_state.view_mode == 'advanced':
                        with st.expander("⚙️ Edit Details", expanded=True):
                            # Domain selector
                            if domains:
                                selected_domain = st.selectbox(
                                    "🌐 Publisher Domain:",
                                    domains,
                                    index=domains.index(current_dom) if current_dom in domains else 0,
                                    key='dom_select_stage'
                                )
                            else:
                                st.caption("No domains available")
                                selected_domain = current_dom
                            
                                if selected_domain != current_dom:
                                    current_flow['publisher_domain'] = selected_domain
                                    dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == selected_domain]
                                    urls = sorted(dom_filtered['publisher_url'].dropna().unique().tolist())
                                    if urls:
                                        current_flow['publisher_url'] = urls[0]
                                    url_filtered = dom_filtered[dom_filtered['publisher_url'] == urls[0]] if urls else dom_filtered
                                    if len(url_filtered) > 0:
                                        current_flow.update(url_filtered.iloc[0].to_dict())
                                    st.session_state.similarities = None  # Reset scores
                                    st.rerun()
                            
                            # URL selector
                            if urls:
                                selected_pub_url = st.selectbox(
                                    "📰 Specific URL:",
                                    urls,
                                    index=urls.index(current_url) if current_url in urls else 0,
                                    key='url_select'
                                )
                                
                                if selected_pub_url != current_url:
                                    current_flow['publisher_url'] = selected_pub_url
                                    url_filtered = dom_filtered[dom_filtered['publisher_url'] == selected_pub_url]
                                    if 'serp_template_name' in url_filtered.columns:
                                        serps = sorted(url_filtered['serp_template_name'].dropna().unique().tolist())
                                    final_filtered = url_filtered
                                    if len(final_filtered) > 0:
                                        current_flow.update(final_filtered.iloc[0].to_dict())
                                    st.session_state.similarities = None  # Reset scores
                                    st.rerun()
                            
                            # Show count
                            st.caption(f"📊 {len(urls)} URLs available")
                    else:
                        # Basic mode - show info only
                        st.caption(f"**Domain:** {current_dom}")
                        st.caption(f"**URL:** {current_url[:50]}...")
                    
                    pub_url = current_flow.get('publisher_url', '')
                    if pub_url and pd.notna(pub_url) and str(pub_url).strip():
                        # Try iframe src first, fallback to fetched HTML if blocked
                        try:
                            preview_html, height, used_src = render_mini_device_preview(pub_url, is_url=True, device=device1)
                            st.components.v1.html(preview_html, height=height, scrolling=False)
                        except:
                            # Fallback: Fetch HTML
                            try:
                                response = requests.get(pub_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                                if response.status_code == 200:
                                    page_html = response.text
                                    page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(pub_url, m.group(1))}"', page_html)
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device1)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                else:
                                    st.error("Could not load")
                            except:
                                st.error("Load failed")
                    else:
                        st.warning("No publisher URL")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if stage_cols:
                    with stage_cols[1]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%;'>
                            <div style='font-size: 36px; color: #3b82f6; font-weight: 700;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='text-align: center; font-size: 40px; color: #3b82f6; margin: 20px 0; font-weight: 700;'>
                        ↓
                    </div>
                    """, unsafe_allow_html=True)
                
                # Stage 2: Creative
                stage_2_container = stage_cols[2] if stage_cols else st.container()
                with stage_2_container:
                    st.markdown('<div class="stage-card">', unsafe_allow_html=True)
                    st.markdown('<div class="stage-title">🎨 Creative</div>', unsafe_allow_html=True)
                    
                    # Device selector
                    device2 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev_creative', index=0, label_visibility="collapsed")
                    
                    # Show details
                    creative_id = current_flow.get('creative_id', 'N/A')
                    creative_name = current_flow.get('creative_template_name', 'N/A')
                    creative_size = current_flow.get('creative_size', 'N/A')
                    
                    if st.session_state.view_mode == 'advanced':
                        with st.expander("⚙️ View Details", expanded=False):
                            st.caption(f"**ID:** {creative_id}")
                            st.caption(f"**Name:** {creative_name}")
                            st.caption(f"**Size:** {creative_size}")
                            st.caption("*Auto-selected based on flow*")
                    else:
                        st.caption(f"**Size:** {creative_size}")
                    
                    # Get response column (creative data)
                    if 'response' in current_flow and current_flow.get('response'):
                        try:
                            creative_html, raw_adcode = parse_creative_html(current_flow['response'])
                            if creative_html and raw_adcode:
                                # Render in original dimensions
                                st.components.v1.html(creative_html, height=400, scrolling=True)
                                
                                # Show raw code option
                                with st.expander("👁️ View Raw Ad Code"):
                                    st.code(raw_adcode[:500], language='html')
                            else:
                                st.warning("Could not parse creative JSON")
                        except Exception as e:
                            st.error(f"Creative error: {str(e)}")
                    else:
                        st.warning("No creative data in 'response' column")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if stage_cols:
                    with stage_cols[3]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%;'>
                            <div style='font-size: 36px; color: #3b82f6; font-weight: 700;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='text-align: center; font-size: 40px; color: #3b82f6; margin: 20px 0; font-weight: 700;'>
                        ↓
                    </div>
                    """, unsafe_allow_html=True)
                
                # Stage 3: SERP
                stage_3_container = stage_cols[4] if stage_cols else st.container()
                with stage_3_container:
                    st.markdown('<div class="stage-card">', unsafe_allow_html=True)
                    st.markdown('<div class="stage-title">📄 SERP</div>', unsafe_allow_html=True)
                    
                    # Device selector
                    device3 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev_serp', index=0, label_visibility="collapsed")
                    
                    if st.session_state.view_mode == 'advanced':
                        with st.expander("⚙️ Edit Details", expanded=False):
                            # SERP template dropdown
                            if serps:
                                selected_serp = st.selectbox(
                                    "📄 SERP Template:",
                                    serps,
                                    index=serps.index(current_serp) if current_serp in serps else 0,
                                    key='serp_select'
                                )
                                
                                if selected_serp != current_serp:
                                    current_flow['serp_template_name'] = selected_serp
                                    final_filtered = url_filtered[url_filtered['serp_template_name'] == selected_serp]
                                    if len(final_filtered) > 0:
                                        current_flow.update(final_filtered.iloc[0].to_dict())
                                    st.session_state.similarities = None  # Reset scores
                                    st.rerun()
                            
                                # Show ad details
                                st.caption(f"**Title:** {current_flow.get('ad_title', 'N/A')[:30]}...")
                                st.caption(f"**Display URL:** {current_flow.get('ad_display_url', 'N/A')[:30]}...")
                                st.caption(f"📊 {len(serps)} templates available")
                    else:
                        # Basic mode - show template name only
                        serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
                        st.caption(f"**Template:** {serp_name}")
                    
                    # Use Serp_URL for iframe rendering
                    serp_url = current_flow.get('Serp_URL', '')
                    if serp_url and pd.notna(serp_url) and str(serp_url).strip():
                        # Try iframe src first, fallback to fetched HTML if blocked
                        try:
                            preview_html, height, used_src = render_mini_device_preview(serp_url, is_url=True, device=device3)
                            st.components.v1.html(preview_html, height=height, scrolling=False)
                        except:
                            # Fallback: Fetch HTML
                            try:
                                response = requests.get(serp_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                                if response.status_code == 200:
                                    page_html = response.text
                                    page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(serp_url, m.group(1))}"', page_html)
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device3)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                else:
                                    st.error("Could not load SERP")
                            except:
                                st.error("SERP load failed")
                    else:
                        st.warning("No SERP URL")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if stage_cols:
                    with stage_cols[5]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%;'>
                            <div style='font-size: 36px; color: #3b82f6; font-weight: 700;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='text-align: center; font-size: 40px; color: #3b82f6; margin: 20px 0; font-weight: 700;'>
                        ↓
                    </div>
                    """, unsafe_allow_html=True)
                
                # Stage 4: Landing Page
                stage_4_container = stage_cols[6] if stage_cols else st.container()
                with stage_4_container:
                    st.markdown('<div class="stage-card">', unsafe_allow_html=True)
                    st.markdown('<div class="stage-title">🎯 Landing Page</div>', unsafe_allow_html=True)
                    
                    # Device selector
                    device4 = st.radio("Device:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='dev_landing', index=0, label_visibility="collapsed")
                    
                    # Get landing page URL
                    adv_url = current_flow.get('reporting_destination_url', '')
                    
                    if st.session_state.view_mode == 'advanced':
                        with st.expander("⚙️ Edit Details", expanded=False):
                            # Keyword selector
                            selected_keyword = st.selectbox(
                                "🔑 Search Keyword:",
                                keywords,
                                index=keywords.index(current_kw) if current_kw in keywords else 0,
                                key='kw_select'
                            )
                            
                            if selected_keyword != current_kw:
                                # Rebuild filters from keyword
                                current_flow['keyword_term'] = selected_keyword
                                kw_filtered = campaign_df[campaign_df['keyword_term'] == selected_keyword]
                                if 'publisher_domain' in kw_filtered.columns:
                                    domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist())
                                    if domains:
                                        current_flow['publisher_domain'] = domains[0]
                                        dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == domains[0]]
                                        urls = sorted(dom_filtered['publisher_url'].dropna().unique().tolist())
                                        if urls:
                                            current_flow['publisher_url'] = urls[0]
                                            url_filtered = dom_filtered[dom_filtered['publisher_url'] == urls[0]]
                                            if len(url_filtered) > 0:
                                                current_flow.update(url_filtered.iloc[0].to_dict())
                                st.session_state.similarities = None  # Reset scores
                                st.rerun()
                            
                            # Show landing page URL info
                            st.caption(f"**Landing:** {adv_url[:35]}...")
                            st.caption(f"📊 {len(keywords)} keywords available")
                    else:
                        # Basic mode - show keyword only
                        st.caption(f"**Keyword:** {current_kw}")
                    
                    if adv_url and pd.notna(adv_url) and str(adv_url).strip():
                        # Try iframe src first, fallback to fetched HTML if blocked
                        try:
                            preview_html, height, used_src = render_mini_device_preview(adv_url, is_url=True, device=device4)
                            st.components.v1.html(preview_html, height=height, scrolling=False)
                        except:
                            # Fallback: Fetch HTML
                            try:
                                response = requests.get(adv_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                                if response.status_code == 200:
                                    page_html = response.text
                                    # Fix relative URLs
                                    page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(adv_url, m.group(1))}"', page_html)
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device4)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                else:
                                    st.error("Could not load page")
                            except:
                                st.error("Load failed")
                    else:
                        st.warning("No landing page URL")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.divider()
                
                # Calculate similarity scores
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if API_KEY:
                        with st.spinner("🧠 Calculating similarity scores..."):
                            st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                # Similarity Scores Below
                st.markdown("### 📊 Similarity Scores")
                
                score_cols = st.columns(3)
                
                with score_cols[0]:
                    st.markdown("#### 🔗 Keyword → Ad")
                    if 'similarities' in st.session_state and st.session_state.similarities:
                        data = st.session_state.similarities.get('kwd_to_ad', {})
                        if 'error' not in data:
                            score = data.get('final_score', 0)
                            reason = data.get('reason', 'N/A')
                            css_class, label, color = get_score_class(score)
                            
                            st.markdown(f'<div class="score-box {css_class}">{score:.1%}</div>', unsafe_allow_html=True)
                            st.markdown(f"**{label} Match**")
                            st.caption(reason)
                            
                            with st.expander("📊 Details"):
                                for key, value in data.items():
                                    if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                                        st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
                        else:
                            st.error("API Error")
                    else:
                        st.info("Add API key to calculate")
                
                with score_cols[1]:
                    st.markdown("#### 🔗 Ad → Page")
                    if 'similarities' in st.session_state and st.session_state.similarities:
                        data = st.session_state.similarities.get('ad_to_page', {})
                        if data and 'error' not in data:
                            score = data.get('final_score', 0)
                            reason = data.get('reason', 'N/A')
                            css_class, label, color = get_score_class(score)
                            
                            st.markdown(f'<div class="score-box {css_class}">{score:.1%}</div>', unsafe_allow_html=True)
                            st.markdown(f"**{label} Match**")
                            st.caption(reason)
                            
                            with st.expander("📊 Details"):
                                for key, value in data.items():
                                    if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                                        st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
                        else:
                            st.info("Will calculate after landing page loads")
                    else:
                        st.info("Add API key to calculate")
                
                with score_cols[2]:
                    st.markdown("#### 🔗 Keyword → Page")
                    if 'similarities' in st.session_state and st.session_state.similarities:
                        data = st.session_state.similarities.get('kwd_to_page', {})
                        if data and 'error' not in data:
                            score = data.get('final_score', 0)
                            reason = data.get('reason', 'N/A')
                            css_class, label, color = get_score_class(score)
                            
                            st.markdown(f'<div class="score-box {css_class}">{score:.1%}</div>', unsafe_allow_html=True)
                            st.markdown(f"**{label} Match**")
                            st.caption(reason)
                            
                            with st.expander("📊 Details"):
                                for key, value in data.items():
                                    if key not in ['final_score', 'band', 'reason'] and isinstance(value, (int, float)):
                                        st.metric(key.replace('_', ' ').title(), f"{value:.1%}")
                        else:
                            st.info("Will calculate after landing page loads")
                    else:
                        st.info("Add API key to calculate")
            
            else:
                st.warning("No data available for this campaign")
else:
    st.error("❌ Could not load data")
    
    st.warning("""
    ### 🔧 Quick Fix for Large Files:
    
    Google Drive's virus scan warning blocks automated downloads for large files.
    
    **Option 1: Make a Copy (Recommended)**
    1. Open your file in Google Drive
    2. File → Make a copy
    3. Share the **copy** with "Anyone with the link"
    4. Use the **copy's** file ID
    
    **Option 2: Use Direct Link Format**
    Try this URL format in your browser to test download:
    ```
    https://drive.google.com/uc?export=download&id={FILE_A_ID}
    ```
    If it downloads successfully in browser, the file is accessible.
    
    **Option 3: Reduce File Size**
    - Compress with higher compression
    - Filter to essential rows only
    - Split into smaller files
    """)
    
    st.info(f"""
    **Current File ID:** `{FILE_A_ID}`
    
    **Troubleshooting:**
    1. File must be shared with "Anyone with the link can view"
    2. File should be < 100MB for reliable downloads
    3. Make sure it's .csv, .zip, or .gz format
    """)
