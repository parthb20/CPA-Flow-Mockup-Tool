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

# Try to import playwright (for 403 bypass)
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    
    # Auto-install browsers on first run (Streamlit Cloud)
    try:
        import subprocess
        import os
        if not os.path.exists(os.path.expanduser('~/.cache/ms-playwright')):
            subprocess.run(['playwright', 'install', 'chromium', '--with-deps'], 
                          capture_output=True, timeout=120)
    except Exception as e:
        pass  # Install might fail, test browser launch instead
    
    # Test if browser actually works
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            PLAYWRIGHT_AVAILABLE = True
    except Exception as e:
        PLAYWRIGHT_AVAILABLE = False
        # Don't show warning on startup - will show when needed
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False

# OCR for screenshot text extraction (optional)
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None

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
    </style>
""", unsafe_allow_html=True)

# Config
FILE_A_ID = "17_JKUhXfBYlWZZEKUStRgFQhL3Ty-YZu"  # Main data file
# SERP URL base - template key gets appended
SERP_BASE_URL = "https://related.performmedia.com/search/?srprc=3&oscar=1&a=100&q=nada+vehicle+value+by+vin&mkt=perform&purl=forbes.com/home&tpid="

try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
    SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()
except Exception as e:
    API_KEY = ""
    SCREENSHOT_API_KEY = ""

# Session state
# FORCE CLEAR SIMILARITY SCORES - REMOVED FEATURE
if 'similarities' in st.session_state:
    del st.session_state.similarities

for key in ['data_a', 'loading_done', 'default_flow', 'current_flow', 'view_mode', 'flow_layout', 'last_campaign_key']:
    if key not in st.session_state:
        if key == 'view_mode':
            st.session_state[key] = 'basic'
        elif key == 'flow_layout':
            st.session_state[key] = 'horizontal'
        else:
            st.session_state[key] = None

# Ensure similarities is NEVER set
if 'similarities' in st.session_state:
    del st.session_state.similarities

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
                
                # Read CSV with maximum field size to prevent truncation
                import csv
                csv.field_size_limit(100000000)  # 100MB per field - very large to prevent any truncation
                
                # Read as CSV with comprehensive options
                df = pd.read_csv(
                    BytesIO(decompressed), 
                    dtype=str, 
                    on_bad_lines='skip',
                    encoding='utf-8',
                    engine='python'  # Python engine doesn't truncate
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

def extract_text_from_html(html_content):
    """Extract clean text from HTML for similarity analysis"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript', 'aside']):
            element.decompose()
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        # Limit to 3000 chars for API
        return text[:3000]
    except:
        return ""

def fetch_page_content(url):
    """Fetch page content for similarity analysis - tries multiple methods"""
    if not url or pd.isna(url) or str(url).lower() == 'null':
        return ""
    
    # Try 1: Regular request
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            return extract_text_from_html(response.text)
    except:
        pass
    
    # Try 2: Playwright if available
    if PLAYWRIGHT_AVAILABLE:
        try:
            html = capture_with_playwright(url, device='mobile')
            if html:
                return extract_text_from_html(html)
        except:
            pass
    
    # Try 3: Screenshot OCR if available (for 403 blocks)
    if OCR_AVAILABLE and SCREENSHOT_API_KEY:
        try:
            from urllib.parse import quote
            screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(url)}&full_page=true&viewport_width=390&viewport_height=844&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
            extracted_text = extract_text_from_screenshot(screenshot_url)
            if extracted_text:
                return extracted_text[:3000]  # Limit for API
        except:
            pass
    
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
    """Find the best performing flow - prioritize conversions, then clicks, then impressions"""
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
        
        # Determine sorting metric: conversions > clicks > impressions
        total_conversions = df['conversions'].sum()
        total_clicks = df['clicks'].sum()
        
        if total_conversions > 0:
            sort_metric = 'conversions'
        elif total_clicks > 0:
            sort_metric = 'clicks'
        else:
            sort_metric = 'impressions'
        
        # Build combination key: keyword + domain + SERP (NOT URL yet)
        group_cols = ['keyword_term', 'publisher_domain']
        
        if 'serp_template_name' in df.columns:
            group_cols.append('serp_template_name')
        elif 'serp_template_id' in df.columns:
            group_cols.append('serp_template_id')
        
        # Step 1: Aggregate by keyword + domain + SERP (in ONE step)
        agg_df = df.groupby(group_cols, dropna=False)[sort_metric].sum().reset_index()
        
        # Find THE BEST keyword+domain+SERP combination
        best_combo = agg_df.nlargest(1, sort_metric).iloc[0]
        
        # Filter original df to this keyword+domain+SERP combination
        filtered = df.copy()
        for col in group_cols:
            filtered = filtered[filtered[col] == best_combo[col]]
        
        # Step 2: From best keyword+domain+SERP combo, pick most recent view WITH the metric
        if len(filtered) > 0:
            # Prefer views that have the metric > 0
            if sort_metric == 'conversions':
                views_with_metric = filtered[filtered['conversions'] > 0]
            elif sort_metric == 'clicks':
                views_with_metric = filtered[filtered['clicks'] > 0]
            else:
                views_with_metric = filtered[filtered['impressions'] > 0]
            
            # If we have views with metric, use those; otherwise use all
            if len(views_with_metric) > 0:
                filtered = views_with_metric
            
            # Get most recent view
            if 'ts' in filtered.columns:
                best_flow = filtered.nlargest(1, 'ts').iloc[0]
            else:
                best_flow = filtered.nlargest(1, sort_metric).iloc[0]
            
            return best_flow.to_dict()
        else:
            return None
    
    except Exception as e:
        st.error(f"Error finding default flow: {str(e)}")
        return None

def render_mini_device_preview(content, is_url=False, device='mobile', use_srcdoc=False):
    """Render device preview with realistic chrome for mobile/tablet/laptop
    
    Args:
        content: URL or HTML content
        is_url: If True, tries iframe src first
        device: 'mobile', 'tablet', or 'laptop'
        use_srcdoc: If True, use srcdoc for HTML (bypasses X-Frame-Options)
    """
    # Real device dimensions
    if device == 'mobile':
        device_w = 390
        container_height = 844
        scale = 0.25  # Smaller previews like before
        frame_style = "border-radius: 40px; border: 10px solid #000000;"
        
        # Mobile chrome - use single quotes to avoid escaping issues
        device_chrome = """
        <div style='background: #000; color: white; padding: 6px 20px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 500;'>
            <div>9:41</div>
            <div style='display: flex; gap: 4px; align-items: center;'>
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style='background: #f7f7f7; border-bottom: 1px solid #d1d1d1; padding: 8px 12px; display: flex; align-items: center; gap: 8px;'>
            <div style='flex: 1; background: white; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid #e0e0e0;'>
                <span style='font-size: 16px;'>🔒</span>
                <span style='color: #666; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'>URL</span>
                <span style='font-size: 16px;'>🔄</span>
            </div>
        </div>
        """
        
        bottom_nav = """
        <div style='position: fixed; bottom: 0; left: 0; right: 0; background: #f7f7f7; border-top: 1px solid #d1d1d1; padding: 8px; display: flex; justify-content: space-around; align-items: center;'>
            <div style='text-align: center; font-size: 20px;'>◀️</div>
            <div style='text-align: center; font-size: 20px;'>▶️</div>
            <div style='text-align: center; font-size: 20px;'>↻</div>
            <div style='text-align: center; font-size: 20px;'>⊞</div>
        </div>
        """
        chrome_height = "90px"
        
    elif device == 'tablet':
        device_w = 820
        container_height = 1180
        scale = 0.25
        frame_style = "border-radius: 16px; border: 12px solid #1f2937;"
        
        # Tablet chrome - use single quotes
        device_chrome = """
        <div style='background: #000; color: white; padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500;'>
            <div style='display: flex; gap: 12px;'>
                <span>9:41 AM</span>
                <span>Wed Jan 13</span>
            </div>
            <div style='display: flex; gap: 8px; align-items: center;'>
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style='background: #f0f0f0; border-bottom: 1px solid #d0d0d0; padding: 12px 16px; display: flex; align-items: center; gap: 12px;'>
            <span style='font-size: 20px;'>◀️</span>
            <span style='font-size: 20px;'>▶️</span>
            <span style='font-size: 20px;'>↻</span>
            <div style='flex: 1; background: white; border-radius: 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;'>
                <span style='font-size: 18px;'>🔒</span>
                <span style='color: #666; font-size: 15px; flex: 1;'>URL</span>
            </div>
            <span style='font-size: 20px;'>⊞</span>
            <span style='font-size: 20px;'>⋮</span>
        </div>
        """
        bottom_nav = ""
        chrome_height = "60px"
        
    else:  # laptop
        device_w = 1440
        container_height = 900
        scale = 0.2
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        
        # Laptop chrome - use single quotes
        device_chrome = """
        <div style='background: #e8e8e8; padding: 12px 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #d0d0d0;'>
            <div style='display: flex; gap: 8px;'>
                <div style='width: 12px; height: 12px; border-radius: 50%; background: #ff5f57;'></div>
                <div style='width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;'></div>
                <div style='width: 12px; height: 12px; border-radius: 50%; background: #28c840;'></div>
            </div>
            <span style='font-size: 18px; margin-left: 8px;'>◀️</span>
            <span style='font-size: 18px;'>▶️</span>
            <span style='font-size: 18px; margin-right: 8px;'>↻</span>
            <div style='flex: 1; background: white; border-radius: 6px; padding: 8px 16px; display: flex; align-items: center; gap: 12px; border: 1px solid #d0d0d0;'>
                <span style='font-size: 16px;'>🔒</span>
                <span style='color: #333; font-size: 14px; flex: 1;'>https://URL</span>
                <span style='font-size: 16px;'>⭐</span>
            </div>
            <span style='font-size: 18px; margin-left: 8px;'>⊞</span>
            <span style='font-size: 18px;'>⋮</span>
        </div>
        """
        bottom_nav = ""
        chrome_height = "52px"
    
    # Calculate display dimensions based on scale
    display_w = int(device_w * scale)
    display_h = int(container_height * scale)
    
    # ALWAYS fetch HTML and render as srcdoc (NO IFRAME SRC) - user requested HTML only
    original_url = None
    if is_url:
        # For URLs, fetch HTML first, then render as srcdoc
        original_url = content  # Save original URL
        try:
            response = requests.get(content, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                content = response.text
                # Fix relative URLs using the original URL as base
                if original_url:
                    from urllib.parse import urljoin
                    content = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                   lambda m: f'src="{urljoin(original_url, m.group(1))}"', content)
                    content = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                   lambda m: f'href="{urljoin(original_url, m.group(1))}"', content)
            else:
                # If fetch fails, return error placeholder
                content = f'<div style="padding: 20px; text-align: center;"><p>Failed to load: HTTP {response.status_code}</p><p><a href="{original_url}" target="_blank">Open in new tab</a></p></div>'
        except Exception as e:
            # If fetch fails, show error
            content = f'<div style="padding: 20px; text-align: center;"><p>Failed to load URL</p><p><a href="{original_url}" target="_blank">Open in new tab</a></p></div>'
    
    # Validate content - if empty or None, show placeholder with styling
    if not content or (isinstance(content, str) and len(content.strip()) == 0):
        content = '<html><body style="padding: 20px; text-align: center; color: #666; font-family: Arial, sans-serif;"><h3>No content available</h3><p>The content could not be loaded.</p></body></html>'
    
    # Always embed HTML directly (no iframe src)
    iframe_content = content
    
    full_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width={device_w}, initial-scale=1.0">
        <meta charset="utf-8">
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{ 
                margin: 0; 
                padding: 0; 
                width: {device_w}px; 
                max-width: {device_w}px;
                overflow-x: hidden; 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            }}
            .chrome {{ width: 100%; background: white; position: fixed; top: 0; left: 0; right: 0; z-index: 100; }}
            .content {{ 
                position: absolute; 
                top: {chrome_height}; 
                bottom: {'50px' if device == 'mobile' else '0'}; 
                left: 0; 
                right: 0; 
                overflow-y: auto; 
                overflow-x: hidden; 
                width: 100%; 
                max-width: {device_w}px; 
            }}
            .bottom-nav {{ position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; }}
            /* Prevent vertical text - allow proper word breaking */
            p, div, span, h1, h2, h3, h4, h5, h6, a, li {{ 
                white-space: normal !important; 
                word-wrap: break-word !important; 
                word-break: break-word !important;  /* Changed from 'normal' - allows breaking */
                overflow-wrap: break-word !important;
                max-width: 100% !important;
            }}
            /* Ensure text flows horizontally - CRITICAL */
            html, body, * {{ 
                writing-mode: horizontal-tb !important;
                text-orientation: mixed !important;
                direction: ltr !important;
            }}
            /* Constrain all direct children of content */
            .content > * {{
                max-width: 100% !important;
                min-width: unset !important;
                overflow-x: hidden !important;
            }}
            /* Force horizontal text on all text elements */
            p, div, span, h1, h2, h3, h4, h5, h6, a, li, label, button {{
                writing-mode: horizontal-tb !important;
                text-orientation: mixed !important;
            }}
        </style>
    </head>
    <body>
        <div class="chrome">{device_chrome}</div>
        <div class="content">{iframe_content}</div>
        {f'<div class="bottom-nav">{bottom_nav}</div>' if device == 'mobile' else ''}
    </body>
    </html>
    """
    
    # Use base64 encoding to avoid ALL escaping issues
    # Base64 encoding bypasses all HTML escaping problems - browser decodes it automatically
    b64_html = base64.b64encode(full_content.encode('utf-8')).decode('ascii')
    
    # Use transform scale for all devices
    iframe_style = f"width: {device_w}px; height: {container_height}px; border: none; transform: scale({scale}); transform-origin: center top; display: block; background: white;"
    
    html_output = f"""
    <div style="display: flex; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 8px;">
        <div style="width: {display_w}px; height: {display_h}px; {frame_style} overflow: hidden; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
            <iframe src="data:text/html;base64,{b64_html}" style="{iframe_style}"></iframe>
        </div>
    </div>
    """
    
    return html_output, display_h + 30, is_url

def extract_text_from_screenshot(screenshot_url):
    """Extract text from screenshot using OCR"""
    if not OCR_AVAILABLE:
        return None
    
    try:
        # Download screenshot
        response = requests.get(screenshot_url, timeout=30)
        if response.status_code == 200:
            # Open image
            img = Image.open(BytesIO(response.content))
            # Extract text using OCR
            text = pytesseract.image_to_string(img)
            return text.strip() if text else None
    except Exception as e:
        # Silent fail - don't show warning for OCR failures
        return None
    return None

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

def capture_with_playwright(url, device='mobile', timeout=30000):
    """Capture page using Playwright with clean URL (bypasses many 403 errors)
    
    Args:
        url: URL to capture
        device: 'mobile', 'tablet', or 'laptop'
        timeout: Navigation timeout in ms (default 30000, use 60000 for SERP)
    
    Returns:
        HTML content or None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        # Clean URL - remove ONLY tracking params (after ?) and hash fragments (after #)
        clean_url = url.split('?')[0] if '?' in url else url
        clean_url = clean_url.split('#')[0] if '#' in clean_url else clean_url
        
        # Device viewports
        viewports = {
            'mobile': {'width': 390, 'height': 844},
            'tablet': {'width': 820, 'height': 1180},
            'laptop': {'width': 1440, 'height': 900}
        }
        
        # Rotate user agents for better success
        import random
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        user_agent = random.choice(user_agents)
        
        with sync_playwright() as p:
            # Launch browser with comprehensive anti-bot flags
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--window-size=1920,1080',
                    '--disable-infobars',
                    '--disable-extensions'
                ]
            )
            
            # Enhanced context with realistic fingerprint
            context = browser.new_context(
                viewport=viewports[device],
                user_agent=user_agent,
                color_scheme="light",
                locale='en-US',
                timezone_id='America/New_York',
                device_scale_factor=1,
                has_touch=(device == 'mobile'),
                java_script_enabled=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1'
                }
            )
            
            page = context.new_page()
            
            # Comprehensive anti-detection scripts (wrap in try-catch)
            try:
                page.add_init_script("""
                    // Hide webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override the permissions API
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // Mock plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            {
                                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "internal-pdf-viewer",
                                length: 1,
                                name: "Chrome PDF Plugin"
                            }
                        ]
                    });
                    
                    // Mock languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Add chrome object for Chromium
                    if (!window.chrome) {
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                    }
                    
                    // Mock permissions
                    const originalPermissions = navigator.permissions;
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: async (params) => ({
                                state: 'prompt',
                                onchange: null
                            })
                        })
                    });
                """)
            except Exception as e:
                pass  # Script injection failed, continue anyway
            
            # Set timeout (use provided timeout parameter)
            page.set_default_navigation_timeout(timeout)
            
            # Handle dialogs automatically
            page.on("dialog", lambda dialog: dialog.dismiss())
            
            # Navigate to clean URL
            try:
                response = page.goto(clean_url, wait_until='domcontentloaded', timeout=30000)
                
                if not response or response.status >= 400:
                    # Fallback to 'commit' if domcontentloaded times out or status error
                    try:
                        page.goto(clean_url, wait_until='commit', timeout=15000)
                    except Exception as e:
                        # If commit also fails, try 'load' as last resort
                        page.goto(clean_url, wait_until='load', timeout=10000)
                
                # Add random human-like delay
                time.sleep(random.uniform(1.5, 3.0))
                
                # Wait for network to be idle
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except:
                    pass  # Continue anyway
                
                # Scroll to trigger lazy loading
                try:
                    page.evaluate("""
                        async () => {
                            await new Promise((resolve) => {
                                let totalHeight = 0;
                                const distance = 100;
                                const timer = setInterval(() => {
                                    const scrollHeight = document.body.scrollHeight;
                                    window.scrollBy(0, distance);
                                    totalHeight += distance;

                                    if(totalHeight >= scrollHeight){
                                        window.scrollTo(0, 0);
                                        clearInterval(timer);
                                        resolve();
                                    }
                                }, 100);
                            });
                        }
                    """)
                except:
                    pass
                
                # Small delay after scroll
                time.sleep(0.5)
                
                # Get HTML
                html_content = page.content()
                
                browser.close()
                return html_content
                
            except Exception as e:
                try:
                    browser.close()
                except:
                    pass
                return None
    except Exception as e:
        # Return None on any error (caller will handle fallback)
        return None

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
        html_content = f"""
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
        
        return html_content, raw_adcode
        
    except Exception as e:
        st.error(f"Error parsing creative: {str(e)}")
        return None, None


# Simple title at top (Streamlit handles styling)
st.title("📊 CPA Flow Analysis v2")

# ============================================
# FORCE CLEAR SIMILARITY SCORES - REMOVED FEATURE
# ============================================
# This feature has been completely removed
# Clear any cached similarity scores MULTIPLE TIMES
if 'similarities' in st.session_state:
    del st.session_state.similarities
# Force set to None and delete again
try:
    st.session_state.similarities = None
    del st.session_state.similarities
except:
    pass
# Final check
if 'similarities' in st.session_state:
    del st.session_state.similarities

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
            # Similarity scores removed - clear any cached state
            if 'similarities' in st.session_state:
                del st.session_state.similarities
            st.session_state.last_campaign_key = campaign_key
        
        if selected_campaign and selected_campaign != '-- Select Campaign --':
            campaign_df = df[(df['Advertiser_Name'] == selected_advertiser) & (df['Campaign_Name'] == selected_campaign)].copy()
            
            # Calculate metrics
            campaign_df['impressions'] = campaign_df['impressions'].apply(safe_float)
            campaign_df['clicks'] = campaign_df['clicks'].apply(safe_float)
            campaign_df['conversions'] = campaign_df['conversions'].apply(safe_float)
            campaign_df['ctr'] = campaign_df.apply(lambda x: (x['clicks'] / x['impressions'] * 100) if x['impressions'] > 0 else 0, axis=1)
            campaign_df['cvr'] = campaign_df.apply(lambda x: (x['conversions'] / x['clicks'] * 100) if x['clicks'] > 0 else 0, axis=1)
            
            # Add publisher_domain from URL if not present
            if 'publisher_url' in campaign_df.columns:
                campaign_df['publisher_domain'] = campaign_df['publisher_url'].apply(
                    lambda x: urlparse(str(x)).netloc if pd.notna(x) and str(x).strip() else ''
                )
            
            total_impressions = campaign_df['impressions'].sum()
            total_clicks = campaign_df['clicks'].sum()
            total_conversions = campaign_df['conversions'].sum()
            avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            avg_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            
            st.divider()
            
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
                agg_df = agg_df.sort_values('conversions', ascending=False).head(20).reset_index(drop=True)
                
                # Simple approach - format the dataframe with visual indicators in the cells
                display_df = pd.DataFrame({
                    'Publisher Domain': agg_df['publisher_domain'],
                    'Keyword': agg_df['keyword_term'],
                    'Impressions': agg_df['impressions'].apply(lambda x: f"{int(x):,}"),
                    'Clicks': agg_df['clicks'].apply(lambda x: f"{int(x):,}"),
                    'Conversions': agg_df['conversions'].apply(lambda x: f"{int(x):,}"),
                    'CTR %': agg_df['CTR'].apply(lambda x: f"{x:.2f}%"),
                    'CVR %': agg_df['CVR'].apply(lambda x: f"{x:.2f}%")
                })
                
                # Apply background colors using column_config (Streamlit's way)
                st.dataframe(
                    display_df,
                    column_config={
                        "CTR %": st.column_config.TextColumn(
                            "CTR %",
                            help=f"Green if ≥ {avg_ctr:.2f}% (avg), Red if below"
                        ),
                        "CVR %": st.column_config.TextColumn(
                            "CVR %", 
                            help=f"Green if ≥ {avg_cvr:.2f}% (avg), Red if below"
                        )
                    },
                    height=600,
                    hide_index=True
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
                
                # Show selected flow details
                st.info(f"""
                **🎯 Selected Flow:**
                • Keyword: {current_flow.get('keyword_term', 'N/A')}
                • Domain: {current_flow.get('publisher_domain', 'N/A')}
                • SERP: {current_flow.get('serp_template_name', 'N/A')}
                • Impressions: {safe_int(current_flow.get('impressions', 0)):,}
                • Clicks: {safe_int(current_flow.get('clicks', 0)):,}
                • Conversions: {safe_int(current_flow.get('conversions', 0)):,}
                """)
                
                if st.session_state.view_mode == 'basic':
                    st.success("✨ Auto-selected based on best performance")
                else:
                    st.success("✨ Use filters above to change flow")
                
                # Build filter data
                keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                
                # Filter based on selections
                current_kw = current_flow.get('keyword_term', keywords[0] if keywords else '')
                kw_filtered = campaign_df[campaign_df['keyword_term'] == current_kw]
                
                domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in kw_filtered.columns else []
                current_dom = current_flow.get('publisher_domain', domains[0] if domains else '')
                dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == current_dom] if domains else kw_filtered
                
                # Get unique URLs without sorting to preserve full URL
                urls = dom_filtered['publisher_url'].dropna().unique().tolist() if 'publisher_url' in dom_filtered.columns else []
                current_url = current_flow.get('publisher_url', urls[0] if urls else '')
                url_filtered = dom_filtered[dom_filtered['publisher_url'] == current_url] if urls else dom_filtered
                
                serps = []
                if 'serp_template_name' in url_filtered.columns:
                    serps = sorted(url_filtered['serp_template_name'].dropna().unique().tolist())
                current_serp = current_flow.get('serp_template_name', serps[0] if serps else '')
                final_filtered = url_filtered[url_filtered['serp_template_name'] == current_serp] if serps else url_filtered
                
                # Preserve original clicks/conversions before updating (for landing page check)
                original_clicks = safe_int(current_flow.get('clicks', 0), default=0)
                original_conversions = safe_int(current_flow.get('conversions', 0), default=0)
                
                if len(final_filtered) > 0:
                    current_flow.update(final_filtered.iloc[0].to_dict())
                    # Restore aggregated clicks/conversions if we have filtered data
                    if len(final_filtered) > 1:
                        agg_clicks = safe_int(final_filtered['clicks'].sum(), default=0)
                        agg_conversions = safe_int(final_filtered['conversions'].sum(), default=0)
                        if agg_clicks > 0:
                            current_flow['clicks'] = agg_clicks
                        if agg_conversions > 0:
                            current_flow['conversions'] = agg_conversions
                    elif original_clicks > 0:
                        # Keep original if single row has 0
                        current_flow['clicks'] = original_clicks
                    if original_conversions > 0:
                        current_flow['conversions'] = original_conversions
                
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
                
                # Single device selector for ALL cards
                device_all = st.radio("Device for all previews:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='device_all', index=0)
                
                if st.session_state.flow_layout == 'horizontal':
                    # Equal width columns for 4 cards + 3 arrows
                    stage_cols = st.columns([1, 0.1, 1, 0.1, 1, 0.1, 1])
                else:
                    # Vertical layout - one card per row
                    stage_cols = None
                
                # Stage 1: Publisher URL
                stage_1_container = stage_cols[0] if stage_cols else st.container()
                with stage_1_container:
                    st.markdown('<div class="stage-card">', unsafe_allow_html=True)
                    st.markdown('<div class="stage-title">📰 Publisher URL</div>', unsafe_allow_html=True)
                    
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
                                    urls = dom_filtered['publisher_url'].dropna().unique().tolist()
                                    if urls:
                                        current_flow['publisher_url'] = urls[0]
                                    url_filtered = dom_filtered[dom_filtered['publisher_url'] == urls[0]] if urls else dom_filtered
                                    if len(url_filtered) > 0:
                                        current_flow.update(url_filtered.iloc[0].to_dict())
                                    # Similarity scores removed
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
                                        serps = url_filtered['serp_template_name'].dropna().unique().tolist()
                                    final_filtered = url_filtered
                                    if len(final_filtered) > 0:
                                        current_flow.update(final_filtered.iloc[0].to_dict())
                                    # Similarity scores removed
                                    st.rerun()
                            
                            # Show count
                            st.caption(f"📊 {len(urls)} URLs available")
                    else:
                        # Basic mode - show info
                        st.caption(f"**Domain:** {current_dom}")
                        if current_url and pd.notna(current_url):
                            url_display = str(current_url)[:60] + "..." if len(str(current_url)) > 60 else str(current_url)
                            st.caption(f"**URL:** {url_display}")
                    
                    # Get the full URL for rendering
                    pub_url = current_flow.get('publisher_url', '')
                    
                    if pub_url and pub_url != 'NOT_FOUND' and pd.notna(pub_url) and str(pub_url).strip():
                        # Check if site blocks iframe embedding by checking headers
                        try:
                            head_response = requests.head(pub_url, timeout=5, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                'Accept': 'text/html,application/xhtml+xml',
                                'Accept-Language': 'en-US,en;q=0.9'
                            })
                            x_frame = head_response.headers.get('X-Frame-Options', '').upper()
                            csp = head_response.headers.get('Content-Security-Policy', '')
                            
                            # Check if iframe will be blocked
                            iframe_blocked = ('DENY' in x_frame or 'SAMEORIGIN' in x_frame or 'frame-ancestors' in csp.lower())
                        except:
                            iframe_blocked = False  # If can't check, try iframe anyway
                        
                        if not iframe_blocked:
                            # Try iframe src (preferred)
                            try:
                                preview_html, height, _ = render_mini_device_preview(pub_url, is_url=True, device=device_all)
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                st.caption("📺 Iframe")
                            except:
                                iframe_blocked = True  # Failed, use HTML
                        
                        if iframe_blocked:
                            # Fetch HTML with complete browser headers
                            try:
                                # More complete headers to mimic real browser
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Accept-Encoding': 'gzip, deflate, br',
                                    'DNT': '1',
                                    'Connection': 'keep-alive',
                                    'Upgrade-Insecure-Requests': '1',
                                    'Sec-Fetch-Dest': 'document',
                                    'Sec-Fetch-Mode': 'navigate',
                                    'Sec-Fetch-Site': 'none',
                                    'Cache-Control': 'max-age=0'
                                }
                                
                                # Try with session to handle cookies
                                session = requests.Session()
                                response = session.get(pub_url, timeout=15, headers=headers, allow_redirects=True)
                                
                                if response.status_code == 403:
                                    # Try Playwright first (free, bypasses many 403s)
                                    if PLAYWRIGHT_AVAILABLE:
                                        with st.spinner("🔄 Trying browser automation..."):
                                            page_html = capture_with_playwright(pub_url, device=device_all)
                                            if page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                            else:
                                                # Playwright failed - try Screenshot API
                                                if SCREENSHOT_API_KEY:
                                                    try:
                                                        from urllib.parse import quote
                                                        screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(pub_url)}&full_page=false&viewport_width=390&viewport_height=844&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
                                                        screenshot_html = f'<img src="{screenshot_url}" style="width: 100%; height: auto;" />'
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                                        st.caption("📸 Screenshot API")
                                                    except Exception as scr_err:
                                                        st.warning("🚫 Site blocks access (403) - All methods failed")
                                                        st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                                else:
                                                    st.warning("🚫 Site blocks access (403) - Playwright failed")
                                                    st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                    elif SCREENSHOT_API_KEY:
                                        # No Playwright, use Screenshot API
                                        try:
                                            from urllib.parse import quote
                                            screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(pub_url)}&full_page=false&viewport_width=390&viewport_height=844&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
                                            screenshot_html = f'<img src="{screenshot_url}" style="width: 100%; height: auto;" />'
                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                            st.components.v1.html(preview_html, height=height, scrolling=False)
                                            st.caption("📸 Screenshot API")
                                        except Exception as scr_err:
                                            st.warning("🚫 Site blocks access (403)")
                                            st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                    else:
                                        # No Playwright and no Screenshot API
                                        st.warning("🚫 Site blocks access (403)")
                                        st.info("💡 Install Playwright or add SCREENSHOT_API_KEY to bypass 403 errors")
                                        st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                elif response.status_code == 200:
                                    # Use response.text which handles encoding automatically
                                    page_html = response.text
                                    
                                    # Force UTF-8 in HTML
                                    if '<head>' in page_html:
                                        page_html = page_html.replace('<head>', '<head><meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=utf-8">', 1)
                                    else:
                                        page_html = '<head><meta charset="utf-8"></head>' + page_html
                                    
                                    # Fix relative URLs
                                    page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(pub_url, m.group(1))}"', page_html)
                                    page_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                      lambda m: f'href="{urljoin(pub_url, m.group(1))}"', page_html)
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                    st.caption("📄 HTML")
                                else:
                                    st.error(f"❌ HTTP {response.status_code}")
                            except Exception as e:
                                st.error(f"❌ {str(e)[:100]}")
                    else:
                        st.warning("⚠️ No valid publisher URL in data")
                    
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
                    response_value = current_flow.get('response', None)
                    
                    if response_value and pd.notna(response_value) and str(response_value).strip():
                        try:
                            creative_html, raw_adcode = parse_creative_html(response_value)
                            if creative_html and raw_adcode:
                                # Render in original dimensions
                                st.components.v1.html(creative_html, height=400, scrolling=True)
                                
                                # Show raw code option
                                with st.expander("👁️ View Raw Ad Code"):
                                    st.code(raw_adcode[:500], language='html')
                            else:
                                st.warning("⚠️ Empty creative JSON")
                        except Exception as e:
                            st.error(f"⚠️ Creative error: {str(e)[:100]}")
                    else:
                        st.warning("⚠️ No creative data")
                    
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
                                    # Similarity scores removed
                                    st.rerun()
                            
                                # Show ad details
                                st.caption(f"**Title:** {current_flow.get('ad_title', 'N/A')[:30]}...")
                                st.caption(f"**Display URL:** {current_flow.get('ad_display_url', 'N/A')[:30]}...")
                                st.caption(f"📊 {len(serps)} templates available")
                    else:
                        # Basic mode - show template name only
                        serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
                        st.caption(f"**Template:** {serp_name}")
                    
                    # Construct SERP URL dynamically from serp_template_key
                    serp_template_key = current_flow.get('serp_template_key', '')
                    
                    # Always show the constructed SERP URL (full URL + clickable link)
                    if serp_template_key:
                        final_serp_url = SERP_BASE_URL + str(serp_template_key)
                        st.text("Final SERP URL:")
                        st.code(final_serp_url, language=None)
                        st.markdown(f"[🔗 Open in new tab]({final_serp_url})")
                    
                    if serp_template_key and pd.notna(serp_template_key) and str(serp_template_key).strip():
                        # Build SERP URL: base + template key
                        serp_url = SERP_BASE_URL + str(serp_template_key)
                    else:
                        serp_url = None
                    
                    if serp_url:
                        # Get ad details for replacement
                        ad_title = current_flow.get('ad_title', '')
                        ad_desc = current_flow.get('ad_description', '')
                        ad_display_url = current_flow.get('ad_display_url', '')
                        keyword = current_flow.get('keyword_term', '')
                        
                        # ALWAYS fetch HTML FIRST, replace values, THEN render (NO IFRAME SRC)
                        try:
                            # Step 1: Fetch SERP HTML
                            response = requests.get(serp_url, timeout=15, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9'
                            })
                            
                            if response.status_code == 200:
                                serp_html = response.text
                                
                                # Step 2: Replace ad content in SERP HTML
                                # FIRST: Use regex to replace keyword in "Sponsored results for:" text (most reliable)
                                if keyword:
                                    # Replace any variation: "Sponsored results for: ..." or "Sponsored results for: '...'"
                                    # Try multiple patterns to catch all variations
                                    patterns = [
                                        (r'Sponsored results for:\s*["\']?[^"\']*["\']?', f'Sponsored results for: "{keyword}"'),
                                        (r'Sponsored results for:\s*[^<]*', f'Sponsored results for: "{keyword}"'),
                                        (r'Sponsored results for[^:]*:\s*["\']?[^"\']*["\']?', f'Sponsored results for: "{keyword}"'),
                                    ]
                                    for pattern, replacement in patterns:
                                        if re.search(pattern, serp_html, re.IGNORECASE):
                                            serp_html = re.sub(pattern, replacement, serp_html, flags=re.IGNORECASE, count=1)
                                            break
                                
                                # THEN: Use BeautifulSoup for structured replacements
                                from bs4 import BeautifulSoup
                                soup = BeautifulSoup(serp_html, 'html.parser')
                                
                                replacement_made = False
                                
                                # Find ad/sponsored container
                                ad_container = None
                                for pattern in [r'sponsored', r'ad-result', r'paid', r'ad-container', r'sponsor', r'ad-result']:
                                    ad_container = soup.find('div', class_=re.compile(pattern, re.IGNORECASE))
                                    if ad_container:
                                        break
                                
                                # If no container found, try finding by text
                                if not ad_container:
                                    for elem in soup.find_all(string=re.compile(r'Sponsored results for:', re.IGNORECASE)):
                                        parent = elem.parent
                                        while parent and parent.name != 'div':
                                            parent = parent.parent
                                        if parent:
                                            ad_container = parent
                                            break
                                
                                # Search scope: ad container if found, otherwise whole document
                                search_scope = ad_container if ad_container else soup
                                
                                # Replace ad title - search more broadly
                                if ad_title:
                                    # Try multiple strategies
                                    title_elem = None
                                    # Strategy 1: Find by class containing "title"
                                    title_elem = search_scope.find(class_=re.compile(r'title', re.IGNORECASE))
                                    # Strategy 2: Find heading tags (h1-h6) in ad container
                                    if not title_elem:
                                        title_elem = search_scope.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                                    # Strategy 3: Find any element with "title" in id or class
                                    if not title_elem:
                                        title_elem = search_scope.find(attrs={'class': re.compile(r'title', re.IGNORECASE)})
                                    if not title_elem and ad_container:
                                        # Fallback: search globally
                                        title_elem = soup.find(class_=re.compile(r'title', re.IGNORECASE))
                                    if title_elem:
                                        title_elem.clear()
                                        title_elem.append(ad_title)
                                        replacement_made = True
                                
                                # Replace ad description
                                if ad_desc:
                                    desc_elem = search_scope.find(class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                    if not desc_elem:
                                        # Try finding paragraph or span in ad container
                                        desc_elem = search_scope.find(['p', 'span'], class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                    if not desc_elem and ad_container:
                                        desc_elem = soup.find(class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                    if desc_elem:
                                        desc_elem.clear()
                                        desc_elem.append(ad_desc)
                                        replacement_made = True
                                
                                # Replace ad display URL
                                if ad_display_url:
                                    url_elem = search_scope.find(class_=re.compile(r'url|display.*url|ad.*url|link', re.IGNORECASE))
                                    if not url_elem:
                                        # Try finding link element
                                        url_elem = search_scope.find('a', class_=re.compile(r'url|display', re.IGNORECASE))
                                    if not url_elem and ad_container:
                                        url_elem = soup.find(class_=re.compile(r'url|display.*url|ad.*url', re.IGNORECASE))
                                    if url_elem:
                                        url_elem.clear()
                                        url_elem.append(ad_display_url)
                                        replacement_made = True
                                
                                # Convert back to HTML
                                serp_html = str(soup)
                                
                                # Fix relative URLs to absolute
                                serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                  lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                                serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                  lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                                
                                # Add mobile-friendly viewport and CSS to prevent vertical text
                                # Get device width based on selected device
                                device_widths = {'mobile': 390, 'tablet': 820, 'laptop': 1440}
                                current_device_w = device_widths.get(device_all, 390)
                                
                                mobile_css = f'''
                                <meta name="viewport" content="width={current_device_w}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
                                <style>
                                    * {{ 
                                        box-sizing: border-box !important; 
                                        max-width: 100% !important;
                                    }}
                                    html, body {{ 
                                        width: {current_device_w}px !important;
                                        max-width: {current_device_w}px !important; 
                                        overflow-x: hidden !important; 
                                        margin: 0 !important; 
                                        padding: 0 !important; 
                                        font-size: 14px !important;
                                    }}
                                    /* Force horizontal text flow - CRITICAL */
                                    html, body, * {{
                                        writing-mode: horizontal-tb !important;
                                        text-orientation: mixed !important;
                                        direction: ltr !important;
                                    }}
                                    /* Allow text to wrap properly - CRITICAL */
                                    p, div, span, a, h1, h2, h3, h4, h5, h6, li, td, th, label, button {{
                                        word-break: break-word !important;
                                        overflow-wrap: break-word !important;
                                        white-space: normal !important;
                                        max-width: 100% !important;
                                        writing-mode: horizontal-tb !important;
                                        text-orientation: mixed !important;
                                    }}
                                    /* Override fixed widths */
                                    img, iframe, video {{
                                        max-width: 100% !important;
                                        height: auto !important;
                                    }}
                                    /* CRITICAL: Remove ALL min-width constraints */
                                    * {{
                                        min-width: unset !important;
                                    }}
                                    /* Prevent horizontal scroll */
                                    [class*="container"], [class*="ad-result"], [class*="serp-result"], [class*="sponsored"], 
                                    [class*="result"], [class*="ad"], div, section, article {{
                                        max-width: 100% !important; 
                                        min-width: unset !important;
                                        width: auto !important;
                                    }}
                                    /* Ensure tables don't break layout */
                                    table {{
                                        width: 100% !important;
                                        max-width: 100% !important;
                                        table-layout: auto !important;
                                    }}
                                </style>
                                '''
                                
                                # Inject into head tag
                                if re.search(r'<head>', serp_html, re.IGNORECASE):
                                    serp_html = re.sub(
                                        r'<head>',
                                        f'<head>{mobile_css}',
                                        serp_html,
                                        flags=re.IGNORECASE,
                                        count=1
                                    )
                                else:
                                    # No head tag, add one
                                    serp_html = f'<head>{mobile_css}</head>{serp_html}'
                                
                                # Step 3: Render modified HTML as iframe using srcdoc
                                # Use selected device (respect user choice)
                                preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                st.caption("📺 SERP with injected ad content")
                                
                            elif response.status_code == 403:
                                # Try Playwright as fallback (with longer timeout for SERP)
                                if PLAYWRIGHT_AVAILABLE:
                                    with st.spinner("🔄 Using browser automation..."):
                                        page_html = capture_with_playwright(serp_url, device=device_all, timeout=60000)
                                        if page_html:
                                            # Apply same replacements using regex FIRST, then BeautifulSoup
                                            # Replace keyword using regex (most reliable)
                                            if keyword:
                                                page_html = re.sub(
                                                    r'Sponsored results for:\s*["\']?[^"\']*["\']?',
                                                    f'Sponsored results for: "{keyword}"',
                                                    page_html,
                                                    flags=re.IGNORECASE,
                                                    count=1
                                                )
                                            
                                            # Then use BeautifulSoup for structured replacements
                                            from bs4 import BeautifulSoup
                                            soup = BeautifulSoup(page_html, 'html.parser')
                                            
                                            # Find ad container
                                            ad_container = None
                                            for pattern in [r'sponsored', r'ad-result', r'paid', r'ad-container', r'sponsor']:
                                                ad_container = soup.find('div', class_=re.compile(pattern, re.IGNORECASE))
                                                if ad_container:
                                                    break
                                            
                                            if not ad_container:
                                                for elem in soup.find_all(string=re.compile(r'Sponsored results for:', re.IGNORECASE)):
                                                    parent = elem.parent
                                                    while parent and parent.name != 'div':
                                                        parent = parent.parent
                                                    if parent:
                                                        ad_container = parent
                                                        break
                                            
                                            search_scope = ad_container if ad_container else soup
                                            
                                            # Replace ad title
                                            if ad_title:
                                                title_elem = search_scope.find(class_=re.compile(r'title', re.IGNORECASE))
                                                if not title_elem:
                                                    title_elem = search_scope.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                                                if not title_elem and ad_container:
                                                    title_elem = soup.find(class_=re.compile(r'title', re.IGNORECASE))
                                                if title_elem:
                                                    title_elem.clear()
                                                    title_elem.append(ad_title)
                                            
                                            # Replace ad description
                                            if ad_desc:
                                                desc_elem = search_scope.find(class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                                if not desc_elem:
                                                    desc_elem = search_scope.find(['p', 'span'], class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                                if not desc_elem and ad_container:
                                                    desc_elem = soup.find(class_=re.compile(r'desc|description|snippet', re.IGNORECASE))
                                                if desc_elem:
                                                    desc_elem.clear()
                                                    desc_elem.append(ad_desc)
                                            
                                            # Replace ad display URL
                                            if ad_display_url:
                                                url_elem = search_scope.find(class_=re.compile(r'url|display.*url|ad.*url|link', re.IGNORECASE))
                                                if not url_elem:
                                                    url_elem = search_scope.find('a', class_=re.compile(r'url|display', re.IGNORECASE))
                                                if not url_elem and ad_container:
                                                    url_elem = soup.find(class_=re.compile(r'url|display.*url|ad.*url', re.IGNORECASE))
                                                if url_elem:
                                                    url_elem.clear()
                                                    url_elem.append(ad_display_url)
                                            
                                            serp_html = str(soup)
                                            serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                              lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                                            serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                              lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                                            
                                            # Add mobile-friendly CSS (enhanced version)
                                            device_widths = {'mobile': 390, 'tablet': 820, 'laptop': 1440}
                                            current_device_w = device_widths.get(device_all, 390)
                                            
                                            mobile_css = f'''
                                            <meta name="viewport" content="width={current_device_w}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
                                            <style>
                                                * {{ 
                                                    box-sizing: border-box !important; 
                                                    max-width: 100% !important;
                                                }}
                                                html, body {{ 
                                                    width: {current_device_w}px !important;
                                                    max-width: {current_device_w}px !important; 
                                                    overflow-x: hidden !important; 
                                                    margin: 0 !important; 
                                                    padding: 0 !important; 
                                                    font-size: 14px !important;
                                                }}
                                                /* Force horizontal text flow - CRITICAL */
                                                html, body, * {{
                                                    writing-mode: horizontal-tb !important;
                                                    text-orientation: mixed !important;
                                                    direction: ltr !important;
                                                }}
                                                p, div, span, a, h1, h2, h3, h4, h5, h6, li, td, th, label, button {{
                                                    word-break: break-word !important;
                                                    overflow-wrap: break-word !important;
                                                    white-space: normal !important;
                                                    max-width: 100% !important;
                                                    writing-mode: horizontal-tb !important;
                                                    text-orientation: mixed !important;
                                                }}
                                                img, iframe, video {{
                                                    max-width: 100% !important;
                                                    height: auto !important;
                                                }}
                                                * {{
                                                    min-width: unset !important;
                                                }}
                                                [class*="container"], [class*="ad-result"], [class*="serp-result"], [class*="sponsored"], 
                                                [class*="result"], [class*="ad"], div, section, article {{
                                                    max-width: 100% !important; 
                                                    min-width: unset !important;
                                                    width: auto !important;
                                                }}
                                                table {{
                                                    width: 100% !important;
                                                    max-width: 100% !important;
                                                    table-layout: auto !important;
                                                }}
                                            </style>
                                            '''
                                            
                                            if re.search(r'<head>', serp_html, re.IGNORECASE):
                                                serp_html = re.sub(
                                                    r'<head>',
                                                    f'<head>{mobile_css}',
                                                    serp_html,
                                                    flags=re.IGNORECASE,
                                                    count=1
                                                )
                                            else:
                                                serp_html = f'<head>{mobile_css}</head>{serp_html}'
                                            
                                            preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                                            st.components.v1.html(preview_html, height=height, scrolling=False)
                                            st.caption("📺 SERP (via Playwright)")
                                        else:
                                            # Playwright failed - try Screenshot API
                                            if SCREENSHOT_API_KEY:
                                                try:
                                                    from urllib.parse import quote
                                                    viewports = {'mobile': (390, 844), 'tablet': (820, 1180), 'laptop': (1440, 900)}
                                                    vw, vh = viewports.get(device_all, (390, 844))
                                                    screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(serp_url)}&full_page=false&viewport_width={vw}&viewport_height={vh}&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
                                                    screenshot_html = f'<img src="{screenshot_url}" style="width: 100%; height: auto;" />'
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                                    st.caption("📸 Screenshot API")
                                                except Exception as scr_err:
                                                    st.warning("⚠️ Could not load SERP - All methods failed")
                                                    st.markdown(f"[🔗 Open SERP in new tab]({serp_url})")
                                            else:
                                                st.warning("⚠️ Playwright failed to load SERP")
                                                st.info("💡 Install Playwright or add SCREENSHOT_API_KEY")
                                                st.markdown(f"[🔗 Open SERP in new tab]({serp_url})")
                                else:
                                    st.error(f"HTTP {response.status_code} - Install Playwright for 403 bypass")
                            else:
                                st.error(f"HTTP {response.status_code}")
                                
                        except Exception as e:
                            st.error(f"Load failed: {str(e)[:100]}")
                    else:
                        st.warning("⚠️ No SERP URL found in mapping")
                    
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
                                        urls = dom_filtered['publisher_url'].dropna().unique().tolist()
                                        if urls:
                                            current_flow['publisher_url'] = urls[0]
                                            url_filtered = dom_filtered[dom_filtered['publisher_url'] == urls[0]]
                                            if len(url_filtered) > 0:
                                                current_flow.update(url_filtered.iloc[0].to_dict())
                                # Similarity scores removed
                                st.rerun()
                            
                            # Show landing page URL
                            st.caption(f"📊 {len(keywords)} keywords available")
                    else:
                        # Basic mode - show keyword only
                        st.caption(f"**Keyword:** {current_kw}")
                    
                    # Get landing URL and check clicks from current_flow
                    # Use same logic as display (safe_int) for consistency - get from original flow, not filtered
                    flow_clicks = current_flow.get('clicks', 0)
                    clicks_value = safe_int(flow_clicks, default=0)
                    
                    # Debug: Show what we have
                    if st.session_state.view_mode == 'advanced':
                        st.caption(f"🔍 Debug: clicks={clicks_value}, URL={'present' if (adv_url and pd.notna(adv_url) and str(adv_url).strip()) else 'missing/empty'}")
                    
                    # Show landing URL info in basic mode
                    if st.session_state.view_mode == 'basic' and adv_url and pd.notna(adv_url):
                        url_display = str(adv_url)[:60] + "..." if len(str(adv_url)) > 60 else str(adv_url)
                        st.caption(f"**Landing URL:** {url_display}")
                    
                    # Check if we have a valid landing URL
                    has_valid_url = adv_url and pd.notna(adv_url) and str(adv_url).strip() and str(adv_url).lower() != 'nan'
                    
                    # Check if clicks > 0 - use the flow's clicks value (same as shown in info box)
                    if clicks_value > 0:
                        if has_valid_url:
                            # Has clicks - show landing page
                            # Check if site blocks iframe embedding
                            try:
                                head_response = requests.head(adv_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                                x_frame = head_response.headers.get('X-Frame-Options', '').upper()
                                csp = head_response.headers.get('Content-Security-Policy', '')
                                
                                iframe_blocked = ('DENY' in x_frame or 'SAMEORIGIN' in x_frame or 'frame-ancestors' in csp.lower())
                            except:
                                iframe_blocked = False
                            
                            if not iframe_blocked:
                                # Try iframe src
                                try:
                                    preview_html, height, _ = render_mini_device_preview(adv_url, is_url=True, device=device_all)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                    st.caption("📺 Iframe")
                                except:
                                    iframe_blocked = True
                            
                            if iframe_blocked:
                                # Auto-fallback to HTML fetch with enhanced headers
                                try:
                                    headers = {
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                        'Accept-Language': 'en-US,en;q=0.9',
                                        'Accept-Encoding': 'gzip, deflate, br',
                                        'DNT': '1',
                                        'Connection': 'keep-alive',
                                        'Upgrade-Insecure-Requests': '1',
                                        'Sec-Fetch-Dest': 'document',
                                        'Sec-Fetch-Mode': 'navigate',
                                        'Sec-Fetch-Site': 'none',
                                        'Cache-Control': 'max-age=0'
                                    }
                                    
                                    session = requests.Session()
                                    response = session.get(adv_url, timeout=15, headers=headers, allow_redirects=True)
                                    
                                    if response.status_code == 403:
                                        # Try Playwright first (free, bypasses many 403s)
                                        if PLAYWRIGHT_AVAILABLE:
                                            with st.spinner("🔄 Trying browser automation..."):
                                                page_html = capture_with_playwright(adv_url, device=device_all)
                                                if page_html:
                                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                                    st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                                else:
                                                    # Playwright failed - try Screenshot API
                                                    if SCREENSHOT_API_KEY:
                                                        try:
                                                            from urllib.parse import quote
                                                            screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(adv_url)}&full_page=false&viewport_width=390&viewport_height=844&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
                                                            screenshot_html = f'<img src="{screenshot_url}" style="width: 100%; height: auto;" />'
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                                            st.components.v1.html(preview_html, height=height, scrolling=False)
                                                            st.caption("📸 Screenshot API")
                                                        except Exception as scr_err:
                                                            st.warning("🚫 Site blocks access (403) - All methods failed")
                                                            st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                                    else:
                                                        st.warning("🚫 Site blocks access (403) - Playwright failed")
                                                        st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                        elif SCREENSHOT_API_KEY:
                                            # No Playwright, use Screenshot API
                                            try:
                                                from urllib.parse import quote
                                                screenshot_url = f"https://api.screenshotone.com/take?access_key={SCREENSHOT_API_KEY}&url={quote(adv_url)}&full_page=false&viewport_width=390&viewport_height=844&device_scale_factor=2&format=jpg&image_quality=80&cache=false"
                                                screenshot_html = f'<img src="{screenshot_url}" style="width: 100%; height: auto;" />'
                                                preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("📸 Screenshot API")
                                            except Exception as scr_err:
                                                st.warning("🚫 Site blocks access (403)")
                                                st.markdown(f"[🔗 Open landing page]({adv_url})")
                                        else:
                                            # No Playwright and no Screenshot API
                                            st.warning("🚫 Site blocks access (403)")
                                            st.info("💡 Install Playwright or add SCREENSHOT_API_KEY to bypass 403 errors")
                                            st.markdown(f"[🔗 Open landing page]({adv_url})")
                                    elif response.status_code == 200:
                                        # Use response.text which handles encoding automatically
                                        page_html = response.text
                                        
                                        # Force UTF-8 in HTML
                                        if '<head>' in page_html:
                                            page_html = page_html.replace('<head>', '<head><meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=utf-8">', 1)
                                        else:
                                            page_html = '<head><meta charset="utf-8"></head>' + page_html
                                        
                                        page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                          lambda m: f'src="{urljoin(adv_url, m.group(1))}"', page_html)
                                        page_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                          lambda m: f'href="{urljoin(adv_url, m.group(1))}"', page_html)
                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                        st.caption("📄 HTML")
                                    else:
                                        st.error(f"❌ HTTP {response.status_code}")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:100]}")
                        else:
                            # Has clicks but no valid URL
                            st.warning("⚠️ **No Landing Page URL in Data**")
                            st.caption("This flow has clicks but the landing URL is missing from the data.")
                    else:
                        # No clicks
                        st.info("ℹ️ **No Ad Clicks**")
                        st.caption("This view has 0 clicks - user didn't reach the landing page.")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.divider()
                
                # ============================================
                # SIMILARITY SCORES COMPLETELY REMOVED - DO NOT DISPLAY
                # ============================================
                # This section is intentionally EMPTY - NO SIMILARITY SCORES
                # All similarity score display code has been removed
                # Force clear any cached state multiple times
                if 'similarities' in st.session_state:
                    del st.session_state.similarities
                try:
                    st.session_state.similarities = None
                    del st.session_state.similarities
                except:
                    pass
                if 'similarities' in st.session_state:
                    del st.session_state.similarities
                
                # ABSOLUTELY NO CODE DISPLAYS SIMILARITY SCORES HERE
                # If similarity scores appear, Streamlit Cloud may be caching old code
                # Solution: Clear Streamlit Cloud cache or redeploy
                
                # Debug: Show file version to confirm correct file is running
                if st.session_state.view_mode == 'advanced':
                    st.caption("✅ Running: cpa_flow_mockup_v2.py (Similarity scores removed)")
            
            else:
                st.warning("No data available for this campaign")
else:
    st.error("❌ Could not load data - Check FILE_A_ID and file sharing settings")
