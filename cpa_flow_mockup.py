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
from concurrent import futures

# Page config - MUST be first Streamlit command
st.set_page_config(page_title="CPA Flow Analysis v2", page_icon="📊", layout="wide")

# Try to import gdown (better for large files)
try:
    import gdown
    GDOWN_AVAILABLE = True
except:
    GDOWN_AVAILABLE = False

# Try to import playwright (for 403 bypass)
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
    
    # Auto-install browsers on first run (Streamlit Cloud)
    try:
        import subprocess
        import os
        if not os.path.exists(os.path.expanduser('~/.cache/ms-playwright')):
            subprocess.run(['playwright', 'install', 'chromium', '--with-deps'], 
                          capture_output=True, timeout=120)
    except Exception as e:
        st.warning(f"Playwright browser install: {str(e)[:50]}")
        pass  # If install fails, Playwright will gracefully fail later
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False
    st.warning(f"Playwright not available: {str(e)[:50]}")

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
    h1:not(.main-title), h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {
        color: #0f172a !important;
        font-weight: 500 !important;
        font-size: 16px !important;
    }
    
    /* Don't override the main title - it has its own inline styles */
    h1:not(.main-title) { font-weight: 700 !important; font-size: 32px !important; }
    
                /* Ensure main title is properly sized - override everything - VERY BIG */
                .main-title {
                    font-size: 72px !important;
                    font-weight: 900 !important;
                    color: #0f172a !important;
                    margin: 0 !important;
                    padding: 0 !important;
                    line-height: 1.3 !important;
                    letter-spacing: 0.01em !important;
                    word-spacing: normal !important;
                    white-space: normal !important;
                }
    
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
    
    /* Stage-card CSS removed - no longer using white boxes */
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
FILE_B_ID = "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9"  # SERP templates JSON file
# SERP URL base - template key gets appended
SERP_BASE_URL = "https://related.performmedia.com/search/?srprc=3&oscar=1&a=100&q=nada+vehicle+value+by+vin&mkt=perform&purl=forbes.com/home&tpid="

try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
    SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()  # thum.io API key (auth token) or empty for referer-based
    THUMIO_REFERER_DOMAIN = st.secrets.get("THUMIO_REFERER_DOMAIN", "").strip()  # thum.io referer domain (e.g., cpa-flow-mockup.streamlit.app)
except Exception as e:
    API_KEY = ""
    SCREENSHOT_API_KEY = ""
    THUMIO_REFERER_DOMAIN = ""

# Helper: Check if thum.io is configured (either via auth token or referer domain)
# thum.io is always available (FREE tier works without auth)
# Set SCREENSHOT_API_KEY or THUMIO_REFERER_DOMAIN in secrets for paid tier with higher limits
THUMIO_CONFIGURED = True  # Always True - free tier works without setup!

# Helper function to generate thum.io screenshot URL
def get_screenshot_url(url, device='mobile', full_page=False):
    """
    Generate thum.io screenshot URL
    
    thum.io FREE tier: 1000 impressions/month, no signup required!
    Simple format: https://image.thum.io/get/{url}
    
    Supports three methods (in order of preference):
    1. FREE tier (default): No auth needed, works immediately
    2. Referer-based key: Set THUMIO_REFERER_DOMAIN in secrets
    3. Auth token: Set SCREENSHOT_API_KEY in secrets
    """
    from urllib.parse import quote
    
    # Ensure URL is properly formatted (must start with http:// or https://)
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # Device viewport sizes for better screenshots (used with auth token)
    viewports = {
        'mobile': {'width': 390, 'height': 844},
        'tablet': {'width': 820, 'height': 1180},
        'laptop': {'width': 1440, 'height': 900}
    }
    
    vp = viewports.get(device, viewports['mobile'])
    
    # For referer-based keys, use simple format
    if THUMIO_REFERER_DOMAIN:
        screenshot_url = f"https://image.thum.io/get/{url}"
        return screenshot_url
    
    # For auth token keys, add options with auth
    if SCREENSHOT_API_KEY:
        options = [f"width/{vp['width']}"]
        if full_page:
            options.append("fullpage")
        else:
            options.append(f"height/{vp['height']}")
        options.append(f"auth/{SCREENSHOT_API_KEY}")
        screenshot_url = f"https://image.thum.io/get/{'/'.join(options)}/{url}"
        return screenshot_url
    
    # FREE TIER (default): Simple format - works without auth
    # Format: https://image.thum.io/get/{url}
    # Example: https://image.thum.io/get/https://www.google.com/
    # URL encode the target URL properly
    encoded_url = quote(url, safe='')
    screenshot_url = f"https://image.thum.io/get/{encoded_url}"
    return screenshot_url

# Session state
for key in ['data_a', 'data_b', 'loading_done', 'default_flow', 'current_flow', 'view_mode', 'flow_layout', 'similarities', 'last_campaign_key']:
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


def load_json_from_gdrive(file_id):
    """Load JSON file from Google Drive - returns dict of SERP templates {template_key: html_string}"""
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Return dict as-is: { "T8F75KL": "<html>...", ... }
        if isinstance(data, dict):
            return data
        
        # If it's a list, convert to dict (fallback for old format)
        if isinstance(data, list) and len(data) > 0:
            # Try to extract template key from first item if it has one
            return data
        
        return None
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
    if OCR_AVAILABLE and THUMIO_CONFIGURED:
        try:
            from urllib.parse import quote
            screenshot_url = get_screenshot_url(url, device='mobile', full_page=True)
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

def render_similarity_score(score_type, similarities_data, show_explanation=False, custom_title=None, tooltip_text=None):
    """Render a single similarity score card
    
    Args:
        score_type: 'kwd_to_ad', 'ad_to_page', or 'kwd_to_page'
        similarities_data: Dict with similarity results
        show_explanation: If True, show explanation of what similarity score is
        custom_title: Custom title to display (e.g., "Ad Copy -> Landing page similarity")
        tooltip_text: Tooltip text explaining what this score measures
    """
    if not similarities_data:
        return
    
    data = similarities_data.get(score_type, {})
    
    if not data or 'error' in data:
        if data and data.get('status_code') == 'no_api_key':
            st.info("🔑 Add API key to calculate")
        else:
            st.info("⏳ Will calculate after data loads")
        return
    
    score = data.get('final_score', 0)
    reason = data.get('reason', 'N/A')
    css_class, label, color = get_score_class(score)
    
    # Get bounds if available
    upper_bound = data.get('upper_bound', score)
    lower_bound = data.get('lower_bound', score)
    
    # Explanation removed - it was taking too much space and showing multiple times
    # Explanation should be shown once at the top, not for each score
    
    # Determine title and tooltip
    if custom_title:
        title_text = custom_title
    else:
        if score_type == 'kwd_to_ad':
            title_text = "Keyword → Ad Similarity"
            default_tooltip = "Measures how well the ad creative matches the search keyword. Higher scores indicate better keyword-ad alignment."
        elif score_type == 'ad_to_page':
            title_text = "Ad Copy → Landing Page Similarity"
            default_tooltip = "Measures how well the landing page fulfills the promises made in the ad copy. Higher scores indicate better ad-page consistency."
        elif score_type == 'kwd_to_page':
            title_text = "Keyword → Landing Page Similarity"
            default_tooltip = "Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment."
        else:
            title_text = f"{label} Match"
            default_tooltip = "Similarity score measuring alignment between different parts of your ad flow."
    
    tooltip = tooltip_text or default_tooltip
    
    # Score display with title and tooltip
    st.markdown(f"""
    <div style="margin-bottom: 8px;">
        <span style="font-weight: 600; color: #0f172a; font-size: 14px;">
            {title_text}
            <span title="{tooltip}" style="cursor: help; color: #3b82f6; font-size: 12px; margin-left: 4px;">ℹ️</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Score display with drilldown expander INSIDE the card
    st.markdown(f"""
    <div style="background: white; border: 2px solid {color}; border-radius: 8px; padding: 12px; margin: 8px 0;">
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px;">
            <div style="font-size: 32px; font-weight: 700; color: {color}; flex-shrink: 0;">{score:.0%}</div>
            <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; color: {color}; font-size: 13px; margin-bottom: 4px;">{label} Match</div>
                <div style="font-size: 11px; color: #64748b; line-height: 1.3;">{reason[:70]}{'...' if len(reason) > 70 else ''}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Drilldown expander BELOW the score card
    with st.expander(f"🔍 How was this calculated?", expanded=False):
        st.markdown(f"**Reason:** {reason}")
        # Show calculation breakdown if available
        if 'topic_match' in data:
            st.markdown(f"**Topic Match:** {data.get('topic_match', 0):.0%}")
        if 'brand_match' in data:
            st.markdown(f"**Brand Match:** {data.get('brand_match', 0):.0%}")
        if 'promise_match' in data:
            st.markdown(f"**Promise Match:** {data.get('promise_match', 0):.0%}")
        if 'utility_match' in data:
            st.markdown(f"**Utility Match:** {data.get('utility_match', 0):.0%}")
        if 'intent' in data:
            st.markdown(f"**Intent:** {data.get('intent', 'N/A')}")
        # Show formula if available
        if score_type == 'kwd_to_ad':
            st.caption("Formula: 0.30×Topic + 0.20×Brand + 0.50×Promise")
        elif score_type == 'ad_to_page':
            st.caption("Formula: 0.30×Topic + 0.20×Brand + 0.50×Promise")
        elif score_type == 'kwd_to_page':
            st.caption("Formula: 0.40×Topic + 0.60×Utility")

def render_all_similarity_scores_horizontal(similarities_data):
    """Render all similarity scores in one horizontal line with all devices, upper and lower bounds"""
    if not similarities_data:
        return
    
    # Get all three scores
    kwd_to_ad = similarities_data.get('kwd_to_ad', {})
    ad_to_page = similarities_data.get('ad_to_page', {})
    kwd_to_page = similarities_data.get('kwd_to_page', {})
    
    scores_data = [
        ('kwd_to_ad', kwd_to_ad, '🔗 Keyword → Ad'),
        ('ad_to_page', ad_to_page, '🔗 Ad → Page'),
        ('kwd_to_page', kwd_to_page, '🔗 Keyword → Page')
    ]
    
    # Create columns for all three scores
    cols = st.columns(3)
    
    for idx, (score_type, data, label) in enumerate(scores_data):
        with cols[idx]:
            if not data or 'error' in data:
                if data and data.get('status_code') == 'no_api_key':
                    st.info("🔑 Add API key")
                else:
                    st.info("⏳ Calculating...")
                continue
            
            score = data.get('final_score', 0)
            reason = data.get('reason', 'N/A')
            css_class, score_label, color = get_score_class(score)
            
            # NO upper/lower bounds (as per user request)
            st.markdown(f"""
            <div style="background: white; border: 2px solid {color}; border-radius: 8px; padding: 14px; margin: 4px 0;">
                <div style="font-weight: 600; color: #0f172a; font-size: 13px; margin-bottom: 8px;">{label}</div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap;">
                    <div style="font-size: 36px; font-weight: 700; color: {color}; line-height: 1;">{score:.0%}</div>
                </div>
                <div style="font-weight: 600; color: {color}; font-size: 12px; margin-bottom: 4px;">{score_label} Match</div>
                <div style="font-size: 10px; color: #64748b; line-height: 1.4;">{reason[:75]}{'...' if len(reason) > 75 else ''}</div>
            </div>
            """, unsafe_allow_html=True)

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
    # Real device dimensions - reduced scale for horizontal layout to fit in one line
    if device == 'mobile':
        device_w = 390
        container_height = 844
        scale = 0.5  # Increased for readability - larger previews
        frame_style = "border-radius: 30px; border: 5px solid #000000;"
        
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
        
        bottom_nav = ""  # Removed navigation arrows as requested
        chrome_height = "90px"
        
    elif device == 'tablet':
        device_w = 820
        container_height = 1180
        scale = 0.4  # Increased for readability
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
            <div style="flex: 1; background: white; border-radius: 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;">
                <span style="font-size: 18px;">🔒</span>
                <span style="color: #666; font-size: 15px; flex: 1;">URL</span>
            </div>
        </div>
        """
        bottom_nav = ""
        chrome_height = "60px"
        
    else:  # laptop
        device_w = 1440
        container_height = 900
        scale = 0.3  # Increased for readability
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        
        # Laptop chrome
        device_chrome = """
        <div style="background: #e8e8e8; padding: 12px 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #d0d0d0;">
            <div style="display: flex; gap: 8px;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f57;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #28c840;"></div>
            </div>
            <div style="flex: 1; background: white; border-radius: 6px; padding: 8px 16px; display: flex; align-items: center; gap: 12px; border: 1px solid #d0d0d0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #333; font-size: 14px; flex: 1;">https://URL</span>
            </div>
        </div>
        """
        bottom_nav = ""
        chrome_height = "52px"
    
    display_w = int(device_w * scale)
    display_h = int(container_height * scale)
    
    if is_url and not use_srcdoc:
        iframe_content = f'<iframe src="{content}" style="width: 100%; height: 100%; border: none;"></iframe>'
    else:
        # For HTML content or when use_srcdoc=True, embed directly
        iframe_content = content
    
    # Match the old render_device_preview approach - minimal wrapper, preserve original template styling
    full_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width={device_w}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta charset="utf-8">
        <style>
            body {{ 
                margin: 0; 
                padding: 0; 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                width: {device_w}px;
                max-width: {device_w}px;
                overflow-x: hidden;
            }}
            .device-chrome {{ 
                width: 100%; 
                max-width: {device_w}px;
                background: white; 
            }}
            .content-area {{ 
                width: {device_w}px;
                max-width: {device_w}px;
                height: calc(100vh - {'90px' if device == 'mobile' else '60px' if device == 'tablet' else '52px'}); 
                overflow-y: auto; 
                overflow-x: hidden;
                -webkit-overflow-scrolling: touch; /* Smooth scrolling on mobile */
            }}
            /* Constrain all content to device width - prevent SERP clipping */
            .content-area * {{
                max-width: {device_w}px !important;
                box-sizing: border-box !important;
            }}
            /* Ensure no horizontal overflow */
            html, body {{
                overflow-x: hidden !important;
                width: {device_w}px !important;
                max-width: {device_w}px !important;
            }}
        </style>
    </head>
    <body>
        <div class="device-chrome">{device_chrome}</div>
        <div class="content-area">{iframe_content}</div>
        {bottom_nav if device == 'mobile' else ''}
    </body>
    </html>
    """
    
    escaped = full_content.replace("'", "&apos;").replace('"', '&quot;')
    
    html_output = f"""
    <div style="display: flex; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 8px;">
        <div style="width: {display_w}px; height: {display_h}px; {frame_style} overflow: hidden; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
            <iframe srcdoc='{escaped}' style="width: {device_w}px; height: {container_height}px; border: none; transform: scale({scale}); transform-origin: 0 0; display: block; background: white;"></iframe>
        </div>
    </div>
    """
    
    return html_output, display_h + 30, is_url

def generate_serp_mockup(flow_data, serp_templates):
    """Generate SERP HTML using actual template with CSS fixes
    
    This function processes SERP templates and fixes CSS issues that cause
    vertical text rendering problems.
    
    Args:
        flow_data: Dict containing flow information including 'serp_template_key'
        serp_templates: Dict mapping template keys to HTML strings, e.g., {"T8F75KL": "<html>..."}
    """
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    serp_template_key = flow_data.get('serp_template_key', '')
    
    if serp_templates:
        try:
            # New format: dict with template_key -> HTML string
            if isinstance(serp_templates, dict):
                # Look up template by key
                if serp_template_key and str(serp_template_key) in serp_templates:
                    html = serp_templates[str(serp_template_key)]
                elif len(serp_templates) > 0:
                    # Fallback: use first available template
                    html = list(serp_templates.values())[0]
                else:
                    return ""
            # Old format: list of dicts with 'code' key (backward compatibility)
            elif isinstance(serp_templates, list) and len(serp_templates) > 0:
                html = serp_templates[0].get('code', '')
            else:
                return ""
            
            # Only fix deprecated media queries - don't modify layout CSS
            # These replacements help with older CSS but don't affect responsive design
            html = html.replace('min-device-width', 'min-width')
            html = html.replace('max-device-width', 'max-width')
            html = html.replace('min-device-height', 'min-height')
            html = html.replace('max-device-height', 'max-height')
            
            # Replace keyword in the header text
            html = re.sub(
                r'Sponsored results for:\s*"[^"]*"', 
                f'Sponsored results for: "{keyword}"', 
                html
            )
            
            # Replace URL (inside <div class="url">) - match old working version exactly
            html = re.sub(
                r'(<div class="url">)[^<]*(</div>)', 
                f'\\1{ad_url}\\2', 
                html, 
                count=1
            )
            
            # Replace title (inside <div class="title">) - match old working version exactly
            html = re.sub(
                r'(<div class="title">)[^<]*(</div>)', 
                f'\\1{ad_title}\\2', 
                html, 
                count=1
            )
            
            # Replace description (inside <div class="desc">) - match old working version exactly
            html = re.sub(
                r'(<div class="desc">)[^<]*(</div>)', 
                f'\\1{ad_desc}\\2', 
                html, 
                count=1
            )
            
            return html
        except Exception as e:
            st.error(f"Error generating SERP mockup: {str(e)}")
    
    return ""

def create_screenshot_html(screenshot_url, device='mobile', referer_domain=None):
    """Create HTML for screenshot with proper referer handling
    
    For referer-based thum.io keys, the browser automatically sends the referer header
    when loading images. The referer will be the Streamlit app URL, so ensure
    THUMIO_REFERER_DOMAIN matches your Streamlit app domain (e.g., 'app-name.streamlit.app').
    
    Note: When images are loaded in iframes with srcdoc, the referer may be null.
    This function uses JavaScript to load images, which should preserve the referer.
    """
    vw = 390 if device == 'mobile' else 820 if device == 'tablet' else 1440
    
    # If we have a referer domain, use fetch API to load image with proper referer
    if referer_domain:
        screenshot_html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width={vw}">
<style>* {{margin:0;padding:0}} img {{width:100%;height:auto;display:block;}} .error {{padding: 20px; text-align: center; color: #666;}} .loading {{padding: 20px; text-align: center; color: #999;}}</style>
</head><body>
<div class="loading">Loading screenshot...</div>
<script>
(function() {{
    const img = document.createElement('img');
    img.style.width = '100%';
    img.style.height = 'auto';
    img.style.display = 'block';
    img.onload = function() {{
        document.body.innerHTML = '';
        document.body.appendChild(img);
    }};
    img.onerror = function() {{
        // Try direct load as fallback
        const fallbackImg = new Image();
        fallbackImg.style.width = '100%';
        fallbackImg.style.height = 'auto';
        fallbackImg.style.display = 'block';
        fallbackImg.onload = function() {{
            document.body.innerHTML = '';
            document.body.appendChild(fallbackImg);
        }};
        fallbackImg.onerror = function() {{
            document.body.innerHTML = '<div class="error">Image failed to load</div>';
        }};
        fallbackImg.src = '{screenshot_url}';
    }};
    img.src = '{screenshot_url}';
    img.crossOrigin = 'anonymous';
}})();
</script>
</body></html>'''
    else:
        # Standard img tag for free tier - use proper image loading with error handling and retry
        # Escape URL for JavaScript
        screenshot_url_escaped = screenshot_url.replace("'", "\\'").replace('"', '\\"')
        screenshot_html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width={vw}">
<style>* {{margin:0;padding:0;box-sizing:border-box}} body {{background:#f5f5f5}} img {{width:100%;height:auto;display:block;max-width:100%;}} .error {{padding: 20px; text-align: center; color: #dc2626; background: #fef2f2; border: 2px solid #fca5a5; border-radius: 8px; margin: 10px; font-family: system-ui, -apple-system, sans-serif;}} .loading {{padding: 20px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 8px; margin: 10px;}}</style>
</head><body>
<div class="loading">⏳ Loading screenshot...</div>
<script>
(function() {{
    let retryCount = 0;
    const maxRetries = 3;
    const screenshotUrl = '{screenshot_url_escaped}';
    
    function showError(message) {{
        document.body.innerHTML = '<div class="error">' + message + '</div>';
    }}
    
    function loadImage() {{
        const img = new Image();
        img.style.width = '100%';
        img.style.height = 'auto';
        img.style.display = 'block';
        
        // Set timeout for image loading (10 seconds)
        const timeout = setTimeout(function() {{
            img.onerror = null;
            img.onload = null;
            retryCount++;
            if (retryCount <= maxRetries) {{
                // Retry with cache busting
                const separator = screenshotUrl.includes('?') ? '&' : '?';
                img.src = screenshotUrl + separator + 't=' + Date.now() + '&retry=' + retryCount;
            }} else {{
                showError('⚠️ Screenshot failed to load<br><small>Timeout after multiple retries</small><br><small style="font-size: 10px;">URL: ' + screenshotUrl.substring(0, 60) + '...</small><br><br><small>💡 Check VPN/network connection<br>Some URLs require VPN to access</small>');
            }}
        }}, 10000);
        
        img.onload = function() {{
            clearTimeout(timeout);
            document.body.innerHTML = '';
            document.body.appendChild(img);
        }};
        
        img.onerror = function() {{
            clearTimeout(timeout);
            retryCount++;
            if (retryCount <= maxRetries) {{
                // Retry with cache busting and delay
                setTimeout(function() {{
                    const separator = screenshotUrl.includes('?') ? '&' : '?';
                    img.src = screenshotUrl + separator + 't=' + Date.now() + '&retry=' + retryCount;
                }}, 1000 * retryCount); // Exponential backoff
            }} else {{
                // Try fetch as last resort
                fetch(screenshotUrl, {{ 
                    method: 'GET',
                    cache: 'no-cache',
                    headers: {{ 'Accept': 'image/*' }}
                }})
                    .then(function(response) {{
                        if (!response.ok) {{
                            throw new Error('HTTP ' + response.status);
                        }}
                        return response.blob();
                    }})
                    .then(function(blob) {{
                        const blobUrl = URL.createObjectURL(blob);
                        const fallbackImg = new Image();
                        fallbackImg.style.width = '100%';
                        fallbackImg.style.height = 'auto';
                        fallbackImg.style.display = 'block';
                        fallbackImg.onload = function() {{
                            document.body.innerHTML = '';
                            document.body.appendChild(fallbackImg);
                        }};
                        fallbackImg.onerror = function() {{
                            showError('⚠️ Screenshot failed to load<br><small>Image format error</small><br><br><small>💡 Check VPN/network connection</small>');
                        }};
                        fallbackImg.src = blobUrl;
                    }})
                    .catch(function(error) {{
                        const urlShort = screenshotUrl.substring(0, 60);
                        showError('⚠️ Screenshot failed to load<br><small>Network error: ' + error.message + '</small><br><small style="font-size: 10px;">URL: ' + urlShort + '...</small><br><br><small>💡 This URL may require VPN to access<br>Check your network connection</small>');
                    }});
            }}
        }};
        
        // Set crossOrigin before setting src
        img.crossOrigin = 'anonymous';
        img.src = screenshotUrl;
    }}
    
    // Start loading after a small delay to ensure DOM is ready
    setTimeout(loadImage, 100);
}})();
</script>
</body></html>'''
    
    return screenshot_html

def inject_unique_id(html_content, prefix, url, device, flow_data=None):
    """Inject a unique identifier comment into HTML to force re-rendering
    
    This ensures components re-render when content changes, preventing persistence issues.
    Streamlit components don't support key parameter, so we embed unique ID in HTML.
    """
    import hashlib
    import time
    key_parts = [prefix, str(url), str(device), str(time.time())]
    if flow_data:
        # Include relevant flow data in key
        key_parts.append(str(flow_data.get('publisher_url', '')))
        key_parts.append(str(flow_data.get('serp_template_key', '')))
        key_parts.append(str(flow_data.get('ad_display_url', '')))
    key_string = '_'.join(key_parts)
    # Create a short hash for the unique ID
    unique_id = hashlib.md5(key_string.encode()).hexdigest()[:12]
    # Inject as comment at the start of HTML (handle leading whitespace)
    stripped = html_content.lstrip()
    leading_ws = html_content[:len(html_content) - len(stripped)]
    
    if stripped.startswith('<!DOCTYPE'):
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    elif stripped.startswith('<html'):
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    else:
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    return html_content

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
        st.warning(f"OCR failed: {str(e)[:50]}")
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

def capture_with_playwright(url, device='mobile'):
    """Capture page using Playwright with clean URL (bypasses many 403 errors)"""
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
            
            # Comprehensive anti-detection scripts
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
            
            # Set timeout
            page.set_default_navigation_timeout(30000)
            
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
                browser.close()
                return None
    except Exception as e:
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


# Proper SaaS-style title - REALLY BIG and BOLD (like a logo) - removed v2
st.markdown("""
    <div style="margin-bottom: 15px; padding-bottom: 12px; border-bottom: 3px solid #e2e8f0;">
                        <h1 class="main-title" style="font-size: 72px !important; font-weight: 900 !important; color: #0f172a !important; margin: 0 !important; padding: 0 !important; text-align: left !important; line-height: 1.3 !important; letter-spacing: 0.01em !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.1) !important; pointer-events: none !important; user-select: none !important; word-spacing: normal !important;">
                            📊 CPA Flow Analysis
                        </h1>
    </div>
""", unsafe_allow_html=True)

# Auto-load from Google Drive (parallel loading)
if not st.session_state.loading_done:
    with st.spinner("Loading all data..."):
        try:
            with futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_a = executor.submit(load_csv_from_gdrive, FILE_A_ID)
                future_b = executor.submit(load_json_from_gdrive, FILE_B_ID)
                st.session_state.data_a = future_a.result()
                st.session_state.data_b = future_b.result()
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

# Reduce spacing - minimal margin
st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)

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
        
        # Reset flow when campaign changes - CLEAR ALL OLD DATA IMMEDIATELY
        campaign_key = f"{selected_advertiser}_{selected_campaign}"
        if 'last_campaign_key' not in st.session_state:
            st.session_state.last_campaign_key = None
        
        if st.session_state.last_campaign_key != campaign_key:
            # Clear ALL flow-related state immediately when campaign changes
            st.session_state.default_flow = None
            st.session_state.current_flow = None
            st.session_state.similarities = None
            st.session_state.last_campaign_key = campaign_key
            # Clear any cached previews/components by forcing a complete rerun
            st.empty()  # Clear any lingering containers
            st.rerun()
        
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
            
            # Reduce spacing - minimal margin
            st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
            
            # Show aggregated table with big title
            st.markdown("""
            <div style="margin-bottom: 15px;">
                <h2 style="font-size: 48px; font-weight: 900; color: #0f172a; margin: 0; padding: 0; text-align: left; line-height: 1;">
                    📊 Flow Combinations Overview
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            if 'publisher_domain' in campaign_df.columns and 'keyword_term' in campaign_df.columns:
                # Aggregate by domain + keyword
                agg_df = campaign_df.groupby(['publisher_domain', 'keyword_term']).agg({
                    'impressions': 'sum',
                    'clicks': 'sum',
                    'conversions': 'sum'
                }).reset_index()
                
                agg_df['CTR'] = agg_df.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                agg_df['CVR'] = agg_df.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                # Calculate weighted averages for CTR and CVR
                # CTR weighted by impressions, CVR weighted by clicks
                total_imps = agg_df['impressions'].sum()
                total_clicks = agg_df['clicks'].sum()
                weighted_avg_ctr = (agg_df['clicks'].sum() / total_imps * 100) if total_imps > 0 else 0
                weighted_avg_cvr = (agg_df['conversions'].sum() / total_clicks * 100) if total_clicks > 0 else 0
                
                # Sort by conversions and show top 10 only
                agg_df = agg_df.sort_values('conversions', ascending=False).head(10).reset_index(drop=True)
                
                # Create styled table with white background, black text, borders, and conditional CTR/CVR colors
                table_html = """
                <style>
                .flow-table {
                    width: 100%;
                    border-collapse: collapse;
                    background: white !important;
                    margin: 10px 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    border: 1px solid #e2e8f0;
                }
                .flow-table th {
                    background: #f8fafc !important;
                    color: #000000 !important;
                    font-weight: 700;
                    padding: 12px;
                    text-align: left;
                    border-bottom: 2px solid #cbd5e1;
                    border-right: 1px solid #e2e8f0;
                    font-size: 14px;
                }
                .flow-table th:last-child {
                    border-right: none;
                }
                .flow-table td {
                    padding: 10px 12px;
                    border-bottom: 1px solid #e2e8f0;
                    border-right: 1px solid #e2e8f0;
                    color: #000000 !important;
                    background: white !important;
                    font-size: 13px;
                }
                .flow-table td:last-child {
                    border-right: none;
                }
                .flow-table tr {
                    background: white !important;
                }
                .flow-table tr:hover {
                    background: #f8fafc !important;
                }
                .flow-table tr:hover td {
                    background: #f8fafc !important;
                }
                </style>
                <table class="flow-table">
                <thead>
                    <tr>
                        <th>Publisher Domain</th>
                        <th>Keyword</th>
                        <th>Impressions</th>
                        <th>Clicks</th>
                        <th>Conversions</th>
                        <th>CTR %</th>
                        <th>CVR %</th>
                    </tr>
                </thead>
                <tbody>
                """
                
                for _, row in agg_df.iterrows():
                    ctr_val = row['CTR']
                    cvr_val = row['CVR']
                    
                    # Determine CTR color (light green if >= weighted avg, light red if < weighted avg)
                    if ctr_val >= weighted_avg_ctr:
                        ctr_bg = "#dcfce7"  # light green
                        ctr_color = "#166534"  # dark green text
                    else:
                        ctr_bg = "#fee2e2"  # light red
                        ctr_color = "#991b1b"  # dark red text
                    
                    # Determine CVR color (light green if >= weighted avg, light red if < weighted avg)
                    if cvr_val >= weighted_avg_cvr:
                        cvr_bg = "#dcfce7"  # light green
                        cvr_color = "#166534"  # dark green text
                    else:
                        cvr_bg = "#fee2e2"  # light red
                        cvr_color = "#991b1b"  # dark red text
                    
                    # Escape HTML to prevent rendering issues
                    domain = html.escape(str(row['publisher_domain']))
                    keyword = html.escape(str(row['keyword_term']))
                    
                    table_html += f"""
                    <tr>
                        <td style="background: white !important; color: #000000 !important;">{domain}</td>
                        <td style="background: white !important; color: #000000 !important;">{keyword}</td>
                        <td style="background: white !important; color: #000000 !important;">{int(row['impressions']):,}</td>
                        <td style="background: white !important; color: #000000 !important;">{int(row['clicks']):,}</td>
                        <td style="background: white !important; color: #000000 !important;">{int(row['conversions']):,}</td>
                        <td style="background: {ctr_bg} !important; color: {ctr_color} !important; font-weight: 600;">{ctr_val:.2f}%</td>
                        <td style="background: {cvr_bg} !important; color: {cvr_color} !important; font-weight: 600;">{cvr_val:.2f}%</td>
                    </tr>
                    """
                
                table_html += """
                </tbody>
                </table>
                """
                
                # Calculate dynamic height based on number of rows (min 200px, ~50px per row)
                num_rows = len(agg_df)
                table_height = max(200, 80 + (num_rows * 45))  # Header + rows
                
                # Use components.v1.html to ensure proper rendering - dynamic height
                st.components.v1.html(table_html, height=table_height, scrolling=False)
            else:
                st.warning("Could not generate table - missing required columns")
            
            # Reduce spacing - minimal margin
            st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
            
            # Simplified, easy-to-read flow explanation with consistent styling
            st.markdown("""
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 12px 0;">
                <h3 style="font-size: 18px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">🔄 What is a Flow?</h3>
                <p style="font-size: 15px; color: #334155; margin: 8px 0; line-height: 1.6;">
                    A <strong style="font-weight: 700; color: #0f172a;">flow</strong> is the complete path a user takes from seeing your ad to reaching your landing page.
                </p>
                <p style="font-size: 15px; color: #334155; margin: 8px 0; line-height: 1.6;">
                    <strong style="font-weight: 700; color: #0f172a;">Publisher</strong> → <strong style="font-weight: 700; color: #0f172a;">Creative</strong> → <strong style="font-weight: 700; color: #0f172a;">SERP</strong> → <strong style="font-weight: 700; color: #0f172a;">Landing Page</strong>
                </p>
                <ul style="font-size: 15px; color: #334155; margin: 8px 0; padding-left: 20px; line-height: 1.8;">
                    <li>Each combination creates a <strong style="font-weight: 600;">unique flow</strong></li>
                    <li>We show the <strong style="font-weight: 600;">best performing flow</strong> automatically</li>
                    <li>You can <strong style="font-weight: 600;">customize any part</strong> to see how it changes</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Reduce spacing - minimal margin
            st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
            
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
                filters_changed = False
                if st.session_state.view_mode == 'advanced':
                    with layout_col3:
                        st.markdown("")  # spacing
                    with layout_col4:
                        st.markdown("")  # spacing
                    
                    # Reduce spacing
                    st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                    
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                        current_kw_val = current_flow.get('keyword_term', '')
                        default_kw_idx = 0
                        if current_kw_val in keywords:
                            default_kw_idx = keywords.index(current_kw_val) + 1  # +1 because 'All' is first
                        selected_keyword_filter = st.selectbox("🔑 Filter by Keyword:", ['All'] + keywords, index=default_kw_idx, key='kw_filter_adv')
                    
                    with filter_col2:
                        if 'publisher_domain' in campaign_df.columns:
                            domains = sorted(campaign_df['publisher_domain'].dropna().unique().tolist())
                            current_dom_val = current_flow.get('publisher_domain', '')
                            default_dom_idx = 0
                            if current_dom_val in domains:
                                default_dom_idx = domains.index(current_dom_val) + 1  # +1 because 'All' is first
                            selected_domain_filter = st.selectbox("🌐 Filter by Domain:", ['All'] + domains, index=default_dom_idx, key='dom_filter_adv')
                    
                    # Check if filters were changed from default/current flow
                    if selected_keyword_filter != 'All' and selected_keyword_filter != current_kw_val:
                        filters_changed = True
                    if selected_domain_filter != 'All' and selected_domain_filter != current_dom_val:
                        filters_changed = True
                
                # Reduce spacing - minimal margin instead of divider
                st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                
                # Apply filtering logic based on view mode and filter changes
                if st.session_state.view_mode == 'basic':
                    # Basic view: Use default flow (already set, no changes needed)
                    final_filtered = campaign_df[
                        (campaign_df['keyword_term'] == current_flow.get('keyword_term', '')) &
                        (campaign_df['publisher_domain'] == current_flow.get('publisher_domain', ''))
                    ]
                    if 'serp_template_name' in campaign_df.columns:
                        final_filtered = final_filtered[final_filtered['serp_template_name'] == current_flow.get('serp_template_name', '')]
                    if len(final_filtered) > 0:
                        if 'timestamp' in final_filtered.columns:
                            best_view = final_filtered.loc[final_filtered['timestamp'].idxmax()]
                        else:
                            best_view = final_filtered.iloc[0]
                        current_flow.update(best_view.to_dict())
                
                elif st.session_state.view_mode == 'advanced' and filters_changed:
                    # Advanced view WITH filter changes: Apply new logic (filter -> auto-select SERP -> max timestamp)
                    keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                    
                    # Filter based on user selections
                    if selected_keyword_filter != 'All':
                        current_kw = selected_keyword_filter
                    else:
                        current_kw = current_flow.get('keyword_term', keywords[0] if keywords else '')
                    kw_filtered = campaign_df[campaign_df['keyword_term'] == current_kw]
                    
                    if selected_domain_filter != 'All':
                        current_dom = selected_domain_filter
                    else:
                        domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in kw_filtered.columns else []
                        current_dom = current_flow.get('publisher_domain', domains[0] if domains else '')
                    dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == current_dom] if current_dom else kw_filtered
                    
                    # Get unique URLs without sorting to preserve full URL
                    urls = dom_filtered['publisher_url'].dropna().unique().tolist() if 'publisher_url' in dom_filtered.columns else []
                    current_url = current_flow.get('publisher_url', urls[0] if urls else '')
                    url_filtered = dom_filtered[dom_filtered['publisher_url'] == current_url] if urls else dom_filtered
                    
                    # Auto-select SERP: most convs (then clicks, then imps)
                    serps = []
                    if 'serp_template_name' in url_filtered.columns:
                        serps = sorted(url_filtered['serp_template_name'].dropna().unique().tolist())
                    
                    if serps:
                        # Group by SERP and calculate metrics
                        serp_agg = url_filtered.groupby('serp_template_name').agg({
                            'conversions': 'sum',
                            'clicks': 'sum',
                            'impressions': 'sum'
                        }).reset_index()
                        
                        # Select SERP with most conversions, then clicks, then imps
                        if serp_agg['conversions'].sum() > 0:
                            best_serp = serp_agg.loc[serp_agg['conversions'].idxmax(), 'serp_template_name']
                        elif serp_agg['clicks'].sum() > 0:
                            best_serp = serp_agg.loc[serp_agg['clicks'].idxmax(), 'serp_template_name']
                        else:
                            best_serp = serp_agg.loc[serp_agg['impressions'].idxmax(), 'serp_template_name']
                        
                        current_serp = best_serp
                        current_flow['serp_template_name'] = best_serp
                    else:
                        current_serp = current_flow.get('serp_template_name', '')
                    
                    final_filtered = url_filtered[url_filtered['serp_template_name'] == current_serp] if serps and current_serp else url_filtered
                    
                    if len(final_filtered) > 0:
                        # Select view_id with max timestamp
                        if 'timestamp' in final_filtered.columns:
                            best_view = final_filtered.loc[final_filtered['timestamp'].idxmax()]
                        else:
                            best_view = final_filtered.iloc[0]
                        current_flow.update(best_view.to_dict())
                        # Update keyword and domain in current_flow
                        current_flow['keyword_term'] = current_kw
                        current_flow['publisher_domain'] = current_dom
                        if urls:
                            current_flow['publisher_url'] = current_url
                
                else:
                    # Advanced view WITHOUT filter changes: Use default flow (already set, no changes needed)
                    final_filtered = campaign_df[
                        (campaign_df['keyword_term'] == current_flow.get('keyword_term', '')) &
                        (campaign_df['publisher_domain'] == current_flow.get('publisher_domain', ''))
                    ]
                    if 'serp_template_name' in campaign_df.columns:
                        final_filtered = final_filtered[final_filtered['serp_template_name'] == current_flow.get('serp_template_name', '')]
                    if len(final_filtered) > 0:
                        if 'timestamp' in final_filtered.columns:
                            best_view = final_filtered.loc[final_filtered['timestamp'].idxmax()]
                        else:
                            best_view = final_filtered.iloc[0]
                        current_flow.update(best_view.to_dict())
                
                # Update session state
                st.session_state.current_flow = current_flow
                
                # Show selected flow details - single clean display with performance metrics
                # Get single view_id data (not aggregated)
                if len(final_filtered) > 0:
                    # Select view_id with max timestamp
                    if 'timestamp' in final_filtered.columns:
                        single_view = final_filtered.loc[final_filtered['timestamp'].idxmax()]
                    else:
                        single_view = final_filtered.iloc[0]
                    
                    flow_imps = safe_int(single_view.get('impressions', 0))
                    flow_clicks = safe_int(single_view.get('clicks', 0))
                    flow_convs = safe_int(single_view.get('conversions', 0))
                    flow_ctr = (flow_clicks / flow_imps * 100) if flow_imps > 0 else 0
                    flow_cvr = (flow_convs / flow_clicks * 100) if flow_clicks > 0 else 0
                    
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-left: 4px solid #3b82f6; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                        <h3 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">🎯 Selected Flow</h3>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; font-size: 14px;">
                            <div><strong>Keyword:</strong> {keyword}</div>
                            <div><strong>Domain:</strong> {domain}</div>
                            <div><strong>SERP:</strong> {serp}</div>
                            <div><strong>Landing URL:</strong> {landing_url}</div>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #cbd5e1;">
                            <div><strong style="color: #64748b; font-size: 12px;">Impressions</strong><div style="font-size: 18px; font-weight: 700; color: #0f172a;">{impressions:,}</div></div>
                            <div><strong style="color: #64748b; font-size: 12px;">Clicks</strong><div style="font-size: 18px; font-weight: 700; color: #0f172a;">{clicks:,}</div></div>
                            <div><strong style="color: #64748b; font-size: 12px;">Conversions</strong><div style="font-size: 18px; font-weight: 700; color: #0f172a;">{conversions:,}</div></div>
                            <div><strong style="color: #64748b; font-size: 12px;">CTR</strong><div style="font-size: 18px; font-weight: 700; color: #0f172a;">{ctr:.2f}%</div></div>
                            <div><strong style="color: #64748b; font-size: 12px;">CVR</strong><div style="font-size: 18px; font-weight: 700; color: #0f172a;">{cvr:.2f}%</div></div>
                        </div>
                    </div>
                    """.format(
                        keyword=html.escape(str(single_view.get('keyword_term', 'N/A'))),
                        domain=html.escape(str(single_view.get('publisher_domain', 'N/A'))),
                        serp=html.escape(str(single_view.get('serp_template_name', 'N/A'))),
                        landing_url=html.escape(str(single_view.get('reporting_destination_url', 'N/A'))[:60] + ('...' if len(str(single_view.get('reporting_destination_url', ''))) > 60 else '')),
                        impressions=flow_imps,
                        clicks=flow_clicks,
                        conversions=flow_convs,
                        ctr=flow_ctr,
                        cvr=flow_cvr
                    ), unsafe_allow_html=True)
                    
                    if st.session_state.view_mode == 'basic':
                        st.success("✨ Auto-selected based on best performance")
                    else:
                        st.success("✨ Use filters above to change flow")
                else:
                    st.info("🎯 Selected Flow: No data available")
                
                # Reduce spacing before Flow Journey
                st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                
                # Selected Flow Performance is now shown in the Selected Flow box above - removed duplicate
                
                # Flow Display based on layout
                # Reduce spacing before Flow Journey
                st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
                st.markdown("### 🔄 Flow Journey")
                
                # Single device selector for ALL cards with tooltip
                st.markdown("""
                <div style="margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #64748b;">💡 Select a device to preview how the ad flow appears on different screen sizes</span>
                </div>
                """, unsafe_allow_html=True)
                device_all = st.radio("Device for all previews:", ['mobile', 'tablet', 'laptop'], horizontal=True, key='device_all', index=0)
                
                # Tooltip moved above device selector - now shown as title tooltip
                # Initialize containers for both layouts
                stage_cols = None
                vertical_preview_col = None
                vertical_info_col = None
                stage_1_info_container = None
                stage_2_info_container = None
                stage_3_info_container = None
                stage_4_info_container = None
                
                if st.session_state.flow_layout == 'horizontal':
                    # Add CSS to force single line and prevent wrapping
                    st.markdown("""
                    <style>
                    [data-testid="column"] {
                        flex-shrink: 0 !important;
                        min-width: 0 !important;
                    }
                    .stColumn > div {
                        overflow: hidden !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # Description layer - show domain, URL, keyword (creative), SERP URL, SERP temp key, landing URL
                    desc_cols = st.columns([1, 0.05, 0.7, 0.05, 1, 0.05, 1], gap='small')
                    with desc_cols[0]:
                        domain = current_flow.get('publisher_domain', 'N/A')
                        url = current_flow.get('publisher_url', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 4px 0;">
                            <strong>Domain:</strong> {html.escape(str(domain))}<br>
                            <strong>URL:</strong> {html.escape(str(url)[:40])}{'...' if len(str(url)) > 40 else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[2]:
                        keyword = current_flow.get('keyword_term', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 4px 0;">
                            <strong>Keyword:</strong> {html.escape(str(keyword))}
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[4]:
                        serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
                        serp_key = current_flow.get('serp_template_key', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 4px 0;">
                            <strong>SERP URL:</strong> {html.escape(str(serp_url)[:30])}{'...' if len(str(serp_url)) > 30 else ''}<br>
                            <strong>SERP Key:</strong> {html.escape(str(serp_key))}
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[6]:
                        landing_url = current_flow.get('reporting_destination_url', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 4px 0;">
                            <strong>Landing URL:</strong> {html.escape(str(landing_url)[:40])}{'...' if len(str(landing_url)) > 40 else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Now create columns for the actual cards
                    stage_cols = st.columns([1, 0.05, 0.7, 0.05, 1, 0.05, 1], gap='small')
                else:
                    # Vertical layout - cards extend full width, details inline within card boundaries
                    # No separate columns - everything within each card
                    stage_cols = None
                
                # Stage 1: Publisher URL
                if st.session_state.flow_layout == 'vertical':
                    # Vertical: Full width card with inline details - add spacing for easier reading
                    st.markdown("<br>", unsafe_allow_html=True)  # Add spacing between cards
                    stage_1_container = st.container()
                else:
                    stage_1_container = stage_cols[0]
                
                # Render preview
                # Initialize card columns for vertical layout
                card_col_left = None
                card_col_right = None
                
                # Get current domain and URL for Publisher URL section
                current_dom = current_flow.get('publisher_domain', '')
                current_url = current_flow.get('publisher_url', '')
                
                # Get domains and URLs for filtering (needed for edit details)
                keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                current_kw = current_flow.get('keyword_term', keywords[0] if keywords else '')
                kw_filtered = campaign_df[campaign_df['keyword_term'] == current_kw]
                domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in kw_filtered.columns else []
                
                # Get URLs for current domain
                dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == current_dom] if current_dom and domains else kw_filtered
                urls = dom_filtered['publisher_url'].dropna().unique().tolist() if 'publisher_url' in dom_filtered.columns else []
                
                with stage_1_container:
                    if st.session_state.flow_layout == 'vertical':
                        # Vertical: Full width card with inline details
                        card_col_left, card_col_right = st.columns([0.6, 0.4])
                        with card_col_left:
                            st.markdown('### <strong>📰 Publisher URL</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>📰 Publisher URL</strong>', unsafe_allow_html=True)
                    
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
                                        serps = url_filtered['serp_template_name'].dropna().unique().tolist()
                                    final_filtered = url_filtered
                                    if len(final_filtered) > 0:
                                        current_flow.update(final_filtered.iloc[0].to_dict())
                                    st.session_state.similarities = None  # Reset scores
                                    st.rerun()
                            
                            # Show count
                            st.caption(f"📊 {len(urls)} URLs available")
                    else:
                        # Basic mode - show info
                        st.caption(f"**Domain:** {current_dom}")
                        if current_url and pd.notna(current_url):
                            # Show URL as clickable link only (no duplicate)
                            st.markdown(f"**URL:** [{current_url}]({current_url})", unsafe_allow_html=True)
                    
                    # Get the full URL for rendering
                    pub_url = current_flow.get('publisher_url', '')
                    
                    # In vertical mode, preview goes in left column
                    preview_container = card_col_left if st.session_state.flow_layout == 'vertical' and card_col_left else stage_1_container
                    
                    if pub_url and pub_url != 'NOT_FOUND' and pd.notna(pub_url) and str(pub_url).strip():
                        with preview_container:
                            # Check if site blocks iframe embedding by checking headers
                            try:
                                # Try multiple user agents to bypass blocking
                                user_agents = [
                                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
                                ]
                                head_response = None
                                for ua in user_agents:
                                    try:
                                        head_response = requests.head(pub_url, timeout=5, headers={
                                            'User-Agent': ua,
                                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                            'Accept-Language': 'en-US,en;q=0.9',
                                            'Accept-Encoding': 'gzip, deflate, br',
                                            'DNT': '1',
                                            'Connection': 'keep-alive',
                                            'Upgrade-Insecure-Requests': '1'
                                        })
                                        if head_response.status_code == 200:
                                            break
                                    except:
                                        continue
                                
                                if not head_response:
                                    iframe_blocked = False  # Try anyway
                                else:
                                    x_frame = head_response.headers.get('X-Frame-Options', '').upper()
                                    csp = head_response.headers.get('Content-Security-Policy', '')
                                    
                                    # Check if iframe will be blocked
                                    iframe_blocked = ('DENY' in x_frame or 'SAMEORIGIN' in x_frame or 'frame-ancestors' in csp.lower())
                            except:
                                iframe_blocked = False  # If can't check, try iframe anyway
                            
                            if not iframe_blocked:
                                # Priority 1: Try iframe src
                                try:
                                    preview_html, height, _ = render_mini_device_preview(pub_url, is_url=True, device=device_all)
                                    preview_html = inject_unique_id(preview_html, 'pub_iframe', pub_url, device_all, current_flow)
                                    # Limit height in horizontal mode - readable but compact
                                    display_height = height  # No height limit in horizontal mode - let it be readable
                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                    if st.session_state.flow_layout != 'horizontal':
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
                                    
                                    # Try with session to handle cookies - try multiple user agents
                                    session = requests.Session()
                                    response = None
                                    for ua in user_agents:
                                        headers['User-Agent'] = ua
                                        try:
                                            response = session.get(pub_url, timeout=15, headers=headers, allow_redirects=True)
                                            if response.status_code == 200:
                                                break
                                        except:
                                            continue
                                    
                                    if not response:
                                        response = session.get(pub_url, timeout=15, headers=headers, allow_redirects=True)
                                    
                                    if response.status_code == 403:
                                        # Priority 3: Try Playwright (bypasses many 403s)
                                        if PLAYWRIGHT_AVAILABLE:
                                            try:
                                                with st.spinner("🔄 Trying browser automation..."):
                                                    page_html = capture_with_playwright(pub_url, device=device_all)
                                                    if page_html:
                                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                        preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                                        st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                                    else:
                                                        raise Exception("Playwright returned empty HTML")
                                            except Exception as playwright_error:
                                                # Playwright failed, try screenshot API (priority 4)
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                            if st.session_state.flow_layout != 'horizontal':
                                                                st.caption("📸 Screenshot (thum.io)")
                                                        else:
                                                            st.warning("🚫 Site blocks access (403)")
                                                            st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                                    except:
                                                        st.warning("🚫 Site blocks access (403)")
                                                        st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                                else:
                                                    st.warning("🚫 Site blocks access (403)")
                                                    st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                        elif THUMIO_CONFIGURED:
                                            # No Playwright, try screenshot API (priority 4)
                                            try:
                                                screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                                    st.caption("📸 Screenshot (thum.io)")
                                                else:
                                                    st.warning("🚫 Site blocks access (403)")
                                                    st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                            except:
                                                st.warning("🚫 Site blocks access (403)")
                                                st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                        else:
                                            st.warning("🚫 Site blocks access (403)")
                                            st.info("💡 Install Playwright for better rendering, or screenshots will use thum.io free tier (1000/month)")
                                            st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                    elif response.status_code == 200:
                                        # Priority 2: HTML rendering (after iframe)
                                        try:
                                            page_html = response.text
                                            if '<head>' in page_html:
                                                page_html = page_html.replace('<head>', '<head><meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=utf-8">', 1)
                                            else:
                                                page_html = '<head><meta charset="utf-8"></head>' + page_html
                                            page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                              lambda m: f'src="{urljoin(pub_url, m.group(1))}"', page_html)
                                            page_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                              lambda m: f'href="{urljoin(pub_url, m.group(1))}"', page_html)
                                            preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                            preview_html = inject_unique_id(preview_html, 'pub_html', pub_url, device_all, current_flow)
                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                            st.caption("📄 HTML")
                                        except Exception as html_error:
                                            # HTML rendering failed, try screenshot API as last resort
                                            if THUMIO_CONFIGURED:
                                                try:
                                                    screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                    if screenshot_url:
                                                        screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                        preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                                        st.caption("📸 Screenshot (thum.io)")
                                                    else:
                                                        st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                                except:
                                                    st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                            else:
                                                st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                    else:
                                        # Non-200 status - try Playwright (priority 3) or screenshot (priority 4)
                                        if PLAYWRIGHT_AVAILABLE:
                                            try:
                                                with st.spinner("🔄 Trying browser automation..."):
                                                    page_html = capture_with_playwright(pub_url, device=device_all)
                                                    if page_html:
                                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                        preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                                        st.caption("🤖 Rendered via browser automation")
                                                    else:
                                                        raise Exception("Playwright returned empty HTML")
                                            except Exception as playwright_error:
                                                # Playwright failed, try screenshot API (priority 4)
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                            if st.session_state.flow_layout != 'horizontal':
                                                                st.caption("📸 Screenshot (thum.io)")
                                                        else:
                                                            st.error(f"❌ HTTP {response.status_code}")
                                                    except:
                                                        st.error(f"❌ HTTP {response.status_code}")
                                                else:
                                                    st.error(f"❌ HTTP {response.status_code}")
                                        elif THUMIO_CONFIGURED:
                                            # No Playwright, try screenshot API (priority 4)
                                            try:
                                                screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                                    st.caption("📸 Screenshot (thum.io)")
                                                else:
                                                    st.error(f"❌ HTTP {response.status_code}")
                                            except:
                                                st.error(f"❌ HTTP {response.status_code}")
                                        else:
                                            st.error(f"❌ HTTP {response.status_code}")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:100]}")
                    else:
                        with preview_container:
                            st.warning("⚠️ No valid publisher URL in data")
                    
                    # Publisher URL - Details inline on RIGHT in vertical mode
                    if st.session_state.flow_layout == 'vertical' and card_col_right:
                        with card_col_right:
                            # Similarity definition in tooltip
                            st.markdown("""
                            <div style="margin-bottom: 8px;">
                                <span style="font-weight: 600; color: #0f172a; font-size: 13px;">
                                    📰 Publisher URL Details
                                    <span title="Similarity scores measure how well different parts of your ad flow match: Keyword → Ad (ad matches keyword), Ad → Page (landing page matches ad), Keyword → Page (overall flow consistency)" style="cursor: help; color: #3b82f6; font-size: 12px; margin-left: 4px;">ℹ️</span>
                                </span>
                            </div>
                            """, unsafe_allow_html=True)
                            # Inline details - start URL details inline
                            st.markdown(f"""
                            <div style="display: inline-flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: #64748b;"><strong>Domain:</strong> {current_dom}</span>
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>URL:</strong> <a href="{current_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{current_url[:50]}{"..." if len(current_url) > 50 else ""}</a></span>' if current_url and pd.notna(current_url) else ''}
                            </div>
                            """, unsafe_allow_html=True)
                
                if stage_cols:
                    with stage_cols[1]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%; min-height: 400px; padding: 0; margin: 0;'>
                            <div style='font-size: 80px; color: #3b82f6; font-weight: 900; line-height: 1; text-shadow: 2px 2px 4px rgba(59,130,246,0.3); font-stretch: ultra-condensed; letter-spacing: -0.1em;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                # No vertical arrows in vertical mode - removed as requested
                
                # Stage 2: Creative
                if st.session_state.flow_layout == 'vertical':
                    # Vertical: Full width card with inline details - add spacing
                    st.markdown("<br>", unsafe_allow_html=True)  # Add spacing between cards
                    stage_2_container = st.container()
                    creative_card_left = None
                    creative_card_right = None
                else:
                    if stage_cols:
                        stage_2_container = stage_cols[2]
                    else:
                        stage_2_container = st.container()
                    creative_card_left = None
                    creative_card_right = None
                
                with stage_2_container:
                    if st.session_state.flow_layout == 'vertical':
                        # Create inline columns within card - increase creative size (equal to other cards)
                        creative_card_left, creative_card_right = st.columns([0.5, 0.5])
                        with creative_card_left:
                            st.markdown('### <strong>🎨 Creative</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>🎨 Creative</strong>', unsafe_allow_html=True)
                    
                    # Show details
                    creative_id = current_flow.get('creative_id', 'N/A')
                    creative_name = current_flow.get('creative_template_name', 'N/A')
                    creative_size = current_flow.get('creative_size', 'N/A')
                    
                    # In horizontal mode, minimize details to keep card compact
                    if st.session_state.flow_layout != 'vertical':
                        # Show minimal info in horizontal to keep card narrow
                        if st.session_state.view_mode == 'advanced':
                            with st.expander("⚙️", expanded=False):
                                st.caption(f"**ID:** {creative_id}")
                                st.caption(f"**Name:** {creative_name}")
                                st.caption(f"**Size:** {creative_size}")
                        # Don't show size caption in horizontal - keep it compact
                    
                    # In vertical mode, preview goes in left column
                    creative_preview_container = creative_card_left if st.session_state.flow_layout == 'vertical' and creative_card_left else stage_2_container
                    
                    # Get response column (creative data)
                    response_value = current_flow.get('response', None)
                    
                    with creative_preview_container:
                        if response_value and pd.notna(response_value) and str(response_value).strip():
                            try:
                                creative_html, raw_adcode = parse_creative_html(response_value)
                                if creative_html and raw_adcode:
                                    # Render in readable size - no height limit in horizontal mode
                                    if st.session_state.flow_layout == 'horizontal':
                                        st.components.v1.html(creative_html, height=400, scrolling=True)
                                    else:
                                        st.components.v1.html(creative_html, height=400, scrolling=True)
                                    
                                    # Show raw code option (only in advanced mode or vertical)
                                    if st.session_state.view_mode == 'advanced' or st.session_state.flow_layout == 'vertical':
                                        with st.expander("👁️ View Raw Ad Code"):
                                            st.code(raw_adcode[:500], language='html')
                                else:
                                    st.warning("⚠️ Empty creative JSON")
                            except Exception as e:
                                st.error(f"⚠️ Creative error: {str(e)[:100]}")
                        else:
                            # Keep equal space even when no creative - show readable placeholder
                            if st.session_state.flow_layout == 'horizontal':
                                min_height = 400  # Readable size for horizontal layout
                            else:
                                min_height = 400
                            st.markdown(f"""
                            <div style="min-height: {min_height}px; display: flex; align-items: center; justify-content: center; background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 8px;">
                                <div style="text-align: center; color: #64748b;">
                                    <div style="font-size: 48px; margin-bottom: 8px;">⚠️</div>
                                    <div style="font-weight: 600; font-size: 14px;">No creative data</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Creative Details - Inline on RIGHT in vertical mode
                    if st.session_state.flow_layout == 'vertical' and creative_card_right:
                        with creative_card_right:
                            keyword = current_flow.get('keyword_term', 'N/A')
                            creative_size = current_flow.get('creative_size', 'N/A')
                            creative_name = current_flow.get('creative_template_name', 'N/A')
                            
                            st.markdown("**🎨 Creative Details**")
                            
                            # Keyword filter in creative section (advanced view only)
                            if st.session_state.view_mode == 'advanced':
                                keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                                selected_keyword = st.selectbox(
                                    "🔑 Filter by Keyword:",
                                    keywords,
                                    index=keywords.index(keyword) if keyword in keywords else 0,
                                    key='kw_filter_creative'
                                )
                                if selected_keyword != keyword:
                                    current_flow['keyword_term'] = selected_keyword
                                    st.session_state.similarities = None
                                    st.rerun()
                            
                            # Inline horizontal layout - all on same line
                            st.markdown(f"""
                            <div style="display: inline-flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: #64748b;"><strong>Keyword:</strong> {keyword}</span>
                                <span style="font-size: 12px; color: #64748b;"><strong>Size:</strong> {creative_size}</span>
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>Template:</strong> {creative_name}</span>' if creative_name != 'N/A' else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Keyword → Ad similarity score on right of creative
                            if 'similarities' not in st.session_state or st.session_state.similarities is None:
                                if API_KEY:
                                    st.session_state.similarities = calculate_similarities(current_flow)
                                else:
                                    st.session_state.similarities = {}
                            
                            if 'similarities' in st.session_state and st.session_state.similarities:
                                st.markdown("#### 🔗 Keyword → Ad")
                                render_similarity_score('kwd_to_ad', st.session_state.similarities)
                
                if stage_cols:
                    with stage_cols[3]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%; min-height: 400px; padding: 0; margin: 0;'>
                            <div style='font-size: 80px; color: #3b82f6; font-weight: 900; line-height: 1; text-shadow: 2px 2px 4px rgba(59,130,246,0.3); font-stretch: ultra-condensed; letter-spacing: -0.1em;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                # No vertical arrows in vertical mode - removed as requested
                
                # Stage 3: SERP
                # Construct SERP URL before using it (needed for vertical layout)
                serp_template_key = current_flow.get('serp_template_key', '')
                if serp_template_key and pd.notna(serp_template_key) and str(serp_template_key).strip():
                    serp_url = SERP_BASE_URL + str(serp_template_key)
                else:
                    serp_url = None
                
                if st.session_state.flow_layout == 'vertical':
                    # Vertical: Full width card with inline details - add spacing
                    st.markdown("<br>", unsafe_allow_html=True)  # Add spacing between cards
                    stage_3_container = st.container()
                    serp_card_left = None
                    serp_card_right = None
                else:
                    if stage_cols:
                        stage_3_container = stage_cols[4]
                    else:
                        stage_3_container = st.container()
                    serp_card_left = None
                    serp_card_right = None
                
                with stage_3_container:
                    if st.session_state.flow_layout == 'vertical':
                        # Create inline columns within card
                        serp_card_left, serp_card_right = st.columns([0.6, 0.4])
                        with serp_card_left:
                            st.markdown('### <strong>📄 SERP</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>📄 SERP</strong>', unsafe_allow_html=True)
                    
                    # SERP selection removed from advanced view - auto-selected based on performance
                    # SERP is now auto-selected: most convs (then clicks, then imps)
                    
                    # Basic mode - show template name only
                    serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
                    if st.session_state.flow_layout != 'horizontal':
                        st.caption(f"**Template:** {serp_name}")
                    
                    # Don't show SERP URL in horizontal mode to save space
                    
                    # Get ad details for replacement
                    ad_title = current_flow.get('ad_title', '')
                    ad_desc = current_flow.get('ad_description', '')
                    ad_display_url = current_flow.get('ad_display_url', '')
                    keyword = current_flow.get('keyword_term', '')
                    
                    # Try using SERP templates first (better rendering, fixes CSS issues)
                    serp_html = None
                    if 'data_b' in st.session_state and st.session_state.data_b:
                        # Check if it's a dict (new format) or list (old format)
                        is_dict = isinstance(st.session_state.data_b, dict)
                        is_list = isinstance(st.session_state.data_b, list)
                        if (is_dict and len(st.session_state.data_b) > 0) or (is_list and len(st.session_state.data_b) > 0):
                            serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
                    
                    # In vertical mode, preview goes in left column
                    serp_preview_container = serp_card_left if st.session_state.flow_layout == 'vertical' and serp_card_left else stage_3_container
                    
                    # If template generation worked, use it
                    if serp_html and serp_html.strip():
                        with serp_preview_container:
                            # Render using device preview - preserve original template styling completely
                            preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                            preview_html = inject_unique_id(preview_html, 'serp_template', serp_url or '', device_all, current_flow)
                            display_height = height  # No height limit in horizontal mode - let it be readable
                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                            if st.session_state.flow_layout != 'horizontal':
                                st.caption("📺 SERP (from template)")
                    
                    # Fallback: Fetch from URL if templates not available
                    elif serp_url:
                        with serp_preview_container:
                            try:
                                # Step 1: Fetch SERP HTML
                                response = requests.get(serp_url, timeout=15, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9'
                            })
                            
                                if response.status_code == 200:
                                    serp_html = response.text
                                    
                                    # Only fix deprecated media queries - preserve original layout CSS
                                    serp_html = serp_html.replace('min-device-width', 'min-width')
                                    serp_html = serp_html.replace('max-device-width', 'max-width')
                                    serp_html = serp_html.replace('min-device-height', 'min-height')
                                    serp_html = serp_html.replace('max-device-height', 'max-height')
                                    
                                    # Step 2: Replace ad content in SERP HTML using BeautifulSoup
                                    from bs4 import BeautifulSoup
                                    soup = BeautifulSoup(serp_html, 'html.parser')
                                    
                                    # Debug: Show what we're replacing
                                    replacement_made = False
                                    
                                    # 1. Replace keyword in "Sponsored results for:" text (all occurrences)
                                    for text_node in soup.find_all(string=True):
                                        text_str = str(text_node)
                                        if 'Sponsored results for:' in text_str or 'sponsored results for:' in text_str.lower():
                                            new_text = re.sub(
                                                r'(Sponsored results for:|sponsored results for:)\s*["\']?([^"\'<>]*)["\']?',
                                                f'\\1 "{keyword}"',
                                                text_str,
                                                flags=re.IGNORECASE
                                            )
                                            if new_text != text_str:
                                                text_node.replace_with(new_text)
                                                replacement_made = True
                                    
                                    # 2. Replace ad title - use simple regex like old working version
                                    if ad_title:
                                        # Convert soup back to string, use regex replacement, then re-parse
                                        serp_html_temp = str(soup)
                                        serp_html_temp = re.sub(
                                            r'(<div class="title">)[^<]*(</div>)',
                                            f'\\1{ad_title}\\2',
                                            serp_html_temp,
                                            count=1
                                        )
                                        soup = BeautifulSoup(serp_html_temp, 'html.parser')
                                        replacement_made = True
                                    
                                    # 3. Replace ad description - use simple regex like old working version
                                    if ad_desc:
                                        serp_html_temp = str(soup)
                                        serp_html_temp = re.sub(
                                            r'(<div class="desc">)[^<]*(</div>)',
                                            f'\\1{ad_desc}\\2',
                                            serp_html_temp,
                                            count=1
                                        )
                                        soup = BeautifulSoup(serp_html_temp, 'html.parser')
                                        replacement_made = True
                                    
                                    # 4. Replace ad display URL - use simple regex like old working version
                                    if ad_display_url:
                                        serp_html_temp = str(soup)
                                        serp_html_temp = re.sub(
                                            r'(<div class="url">)[^<]*(</div>)',
                                            f'\\1{ad_display_url}\\2',
                                            serp_html_temp,
                                            count=1
                                        )
                                        soup = BeautifulSoup(serp_html_temp, 'html.parser')
                                        replacement_made = True
                                    
                                    # Debug info
                                    if not replacement_made:
                                        st.warning("⚠️ No matching elements found for replacement. Check SERP HTML structure.")
                                    
                                    # Convert back to HTML
                                    serp_html = str(soup)
                                    
                                    # Fix relative URLs to absolute
                                    serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                                    serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                      lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                                    
                                    # Add CSS to prevent vertical text wrapping
                                    # Don't inject CSS - preserve original template styling
                                    
                                    # Step 3: Render modified HTML as iframe using srcdoc
                                    preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                                    preview_html = inject_unique_id(preview_html, 'serp_injected', serp_url, device_all, current_flow)
                                    display_height = height  # No height limit in horizontal mode - let it be readable
                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                    if st.session_state.flow_layout != 'horizontal':
                                        st.caption("📺 SERP with injected ad content")
                                    
                                elif response.status_code == 403:
                                    # Try Playwright as fallback
                                    if PLAYWRIGHT_AVAILABLE:
                                        with st.spinner("🔄 Using browser automation..."):
                                            page_html = capture_with_playwright(serp_url, device=device_all)
                                            if page_html:
                                                # Apply same replacements
                                                from bs4 import BeautifulSoup
                                                soup = BeautifulSoup(page_html, 'html.parser')
                                                
                                                # Same replacement logic as above
                                                for text_node in soup.find_all(string=True):
                                                    if 'Sponsored results for:' in text_node or 'sponsored results for:' in text_node.lower():
                                                        new_text = re.sub(
                                                            r'(Sponsored results for:|sponsored results for:)\s*["\']?([^"\'<>]*)["\']?',
                                                            f'\\1 "{keyword}"',
                                                            text_node,
                                                            flags=re.IGNORECASE
                                                        )
                                                        text_node.replace_with(new_text)
                                                
                                                title_elements = soup.find_all(class_=re.compile(r'title', re.IGNORECASE))
                                                if title_elements and ad_title:
                                                    first_title = title_elements[0]
                                                    # Only remove text nodes, keep all HTML elements that might have styling
                                                    from bs4 import NavigableString
                                                    for child in list(first_title.children):
                                                        if isinstance(child, NavigableString):
                                                            child.extract()
                                                    first_title.append(ad_title)
                                                
                                                desc_elements = soup.find_all(class_=re.compile(r'desc', re.IGNORECASE))
                                                if desc_elements and ad_desc:
                                                    first_desc = desc_elements[0]
                                                    # Only remove text nodes, keep all HTML elements that might have styling
                                                    from bs4 import NavigableString
                                                    for child in list(first_desc.children):
                                                        if isinstance(child, NavigableString):
                                                            child.extract()
                                                    first_desc.append(ad_desc)
                                                
                                                url_elements = soup.find_all(class_=re.compile(r'url', re.IGNORECASE))
                                                if url_elements and ad_display_url:
                                                    url_elements[0].clear()
                                                    url_elements[0].append(ad_display_url)
                                                
                                                serp_html = str(soup)
                                                
                                                # Apply CSS fixes to prevent vertical text
                                                serp_html = serp_html.replace('min-device-width', 'min-width')
                                                serp_html = serp_html.replace('max-device-width', 'max-width')
                                                serp_html = serp_html.replace('min-device-height', 'min-height')
                                                serp_html = serp_html.replace('max-device-height', 'max-height')
                                                serp_html = re.sub(r'min-height\s*:\s*calc\(100[sv][vh]h?[^)]*\)\s*;?', '', serp_html, flags=re.IGNORECASE)
                                                
                                                serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                                  lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                                                serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                                  lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                                                
                                                # Add CSS to prevent vertical text wrapping
                                                serp_html = re.sub(
                                                    r'<head>',
                                                    '<head><style>body, p, div, span, h1, h2, h3, h4, h5, h6, a, li, td, th { writing-mode: horizontal-tb !important; text-orientation: mixed !important; }</style>',
                                                    serp_html,
                                                    flags=re.IGNORECASE,
                                                    count=1
                                                )
                                                
                                                preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                                                preview_html = inject_unique_id(preview_html, 'serp_playwright', serp_url, device_all, current_flow)
                                                display_height = height  # No height limit in horizontal mode - let it be readable
                                                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                if st.session_state.flow_layout != 'horizontal':
                                                    st.caption("📺 SERP (via Playwright)")
                                            else:
                                                # Playwright failed, try screenshot API if available
                                                if THUMIO_CONFIGURED:
                                                    from urllib.parse import quote
                                                    screenshot_url = get_screenshot_url(serp_url, device=device_all, full_page=False)
                                                    if screenshot_url:
                                                        screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                        preview_html = inject_unique_id(preview_html, 'serp_screenshot', serp_url, device_all, current_flow)
                                                        display_height = height  # No height limit in horizontal mode - let it be readable
                                                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                        st.caption("📸 Screenshot (thum.io)")
                                                else:
                                                    st.warning("⚠️ Could not load SERP. Install Playwright for better rendering, or screenshots will use thum.io free tier")
                                    else:
                                        st.error(f"HTTP {response.status_code} - Install Playwright for 403 bypass")
                                else:
                                    st.error(f"HTTP {response.status_code}")
                                
                            except Exception as e:
                                st.error(f"Load failed: {str(e)[:100]}")
                    else:
                        with serp_preview_container:
                            st.warning("⚠️ No SERP URL found in mapping")
                    
                    # SERP Details - Inline on RIGHT in vertical mode
                    if st.session_state.flow_layout == 'vertical' and serp_card_right:
                        with serp_card_right:
                            serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
                            
                            st.markdown("**📄 SERP Details**")
                            # Inline horizontal layout
                            st.markdown(f"""
                            <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: #64748b;"><strong>Template:</strong> {serp_name}</span>
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>URL:</strong> <a href="{serp_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{serp_url[:50]}{"..." if len(serp_url) > 50 else ""}</a></span>' if serp_url else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Ad → Page similarity score on right of SERP
                            if 'similarities' not in st.session_state or st.session_state.similarities is None:
                                if API_KEY:
                                    st.session_state.similarities = calculate_similarities(current_flow)
                                else:
                                    st.session_state.similarities = {}
                            
                            if 'similarities' in st.session_state and st.session_state.similarities:
                                render_similarity_score('ad_to_page', st.session_state.similarities,
                                                       custom_title="Ad Copy → Landing Page Similarity",
                                                       tooltip_text="Measures how well the landing page fulfills the promises made in the ad copy. Higher scores indicate better ad-page consistency.")
                
                if stage_cols:
                    with stage_cols[5]:
                        st.markdown("""
                        <div style='display: flex; align-items: center; justify-content: center; height: 100%; min-height: 400px; padding: 0; margin: 0;'>
                            <div style='font-size: 80px; color: #3b82f6; font-weight: 900; line-height: 1; text-shadow: 2px 2px 4px rgba(59,130,246,0.3); font-stretch: ultra-condensed; letter-spacing: -0.1em;'>→</div>
                        </div>
                        """, unsafe_allow_html=True)
                # No vertical arrows in vertical mode - removed as requested
                
                # Stage 4: Landing Page
                if st.session_state.flow_layout == 'vertical':
                    # Vertical: Full width card with inline details - add spacing
                    st.markdown("<br>", unsafe_allow_html=True)  # Add spacing between cards
                    stage_4_container = st.container()
                    landing_card_left = None
                    landing_card_right = None
                else:
                    if stage_cols:
                        stage_4_container = stage_cols[6]
                    else:
                        stage_4_container = st.container()
                    landing_card_left = None
                    landing_card_right = None
                
                with stage_4_container:
                    if st.session_state.flow_layout == 'vertical':
                        # Create inline columns within card
                        landing_card_left, landing_card_right = st.columns([0.6, 0.4])
                        with landing_card_left:
                            st.markdown('### <strong>🎯 Landing Page</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>🎯 Landing Page</strong>', unsafe_allow_html=True)
                    
                    # Get landing page URL
                    adv_url = current_flow.get('reporting_destination_url', '')
                    
                    # Keyword filter removed from landing page - now in creative section
                    # Basic mode - no keyword display here
                    pass
                    
                    # Get landing URL and check clicks from current_flow
                    # Use same logic as display (safe_int) for consistency
                    flow_clicks = safe_int(current_flow.get('clicks', 0))
                    
                    # Show landing URL ONLY in horizontal mode (in vertical, it's shown in right panel)
                    if st.session_state.view_mode == 'basic' and adv_url and pd.notna(adv_url) and st.session_state.flow_layout == 'horizontal':
                        st.markdown(f"**Landing URL:** [{adv_url}]({adv_url})", unsafe_allow_html=True)
                    
                    # In vertical mode, preview goes in left column (ONLY preview, no details)
                    landing_preview_container = landing_card_left if st.session_state.flow_layout == 'vertical' and landing_card_left else stage_4_container
                    
                    # Always try to render landing page if URL exists
                    if adv_url and pd.notna(adv_url) and str(adv_url).strip():
                        with landing_preview_container:
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
                                    preview_html = inject_unique_id(preview_html, 'landing_iframe', adv_url, device_all, current_flow)
                                    display_height = height  # No height limit in horizontal mode - let it be readable
                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
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
                                        # Priority 3: Try Playwright (bypasses many 403s)
                                        if PLAYWRIGHT_AVAILABLE:
                                            try:
                                                with st.spinner("🔄 Trying browser automation..."):
                                                    page_html = capture_with_playwright(adv_url, device=device_all)
                                                    if page_html:
                                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                        preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                        st.components.v1.html(preview_html, height=height, scrolling=False)
                                                        st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                                    else:
                                                        raise Exception("Playwright returned empty HTML")
                                            except Exception as playwright_error:
                                                # Playwright failed, try screenshot API (priority 4)
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                            if st.session_state.flow_layout != 'horizontal':
                                                                st.caption("📸 Screenshot (thum.io)")
                                                        else:
                                                            st.warning("🚫 Site blocks access (403)")
                                                            st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                                    except:
                                                        st.warning("🚫 Site blocks access (403)")
                                                        st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                                else:
                                                    st.warning("🚫 Site blocks access (403)")
                                                    st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                        elif THUMIO_CONFIGURED:
                                            # No Playwright, try screenshot API (priority 4)
                                            try:
                                                screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                    display_height = height  # No height limit in horizontal mode - let it be readable
                                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                    if st.session_state.flow_layout != 'horizontal':
                                                        st.caption("📸 Screenshot (thum.io)")
                                                else:
                                                    st.warning("🚫 Site blocks access (403)")
                                                    st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                            except:
                                                st.warning("🚫 Site blocks access (403)")
                                                st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                        else:
                                            st.warning("🚫 Site blocks access (403)")
                                            st.info("💡 Install Playwright for better rendering, or screenshots will use thum.io free tier (1000/month)")
                                            st.markdown(f"[🔗 Open landing page]({adv_url})")
                                    elif response.status_code == 200:
                                        # Priority 2: HTML rendering (after iframe)
                                        try:
                                            page_html = response.text
                                            if '<head>' in page_html:
                                                page_html = page_html.replace('<head>', '<head><meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=utf-8">', 1)
                                            else:
                                                page_html = '<head><meta charset="utf-8"></head>' + page_html
                                            page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                              lambda m: f'src="{urljoin(adv_url, m.group(1))}"', page_html)
                                            page_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                              lambda m: f'href="{urljoin(adv_url, m.group(1))}"', page_html)
                                            preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                            preview_html = inject_unique_id(preview_html, 'landing_html', adv_url, device_all, current_flow)
                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                            st.caption("📄 HTML")
                                        except Exception as html_error:
                                            # HTML rendering failed, try screenshot API as last resort
                                            if THUMIO_CONFIGURED:
                                                try:
                                                    screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                    if screenshot_url:
                                                        screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                        preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                        display_height = height  # No height limit in horizontal mode - let it be readable
                                                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                        st.caption("📸 Screenshot (thum.io)")
                                                    else:
                                                        st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                                except:
                                                    st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                            else:
                                                st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                    else:
                                        # Non-200 status - try Playwright (priority 3) or screenshot (priority 4)
                                        if PLAYWRIGHT_AVAILABLE:
                                            try:
                                                with st.spinner("🔄 Trying browser automation..."):
                                                    page_html = capture_with_playwright(adv_url, device=device_all)
                                                    if page_html:
                                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                        preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                        display_height = height  # No height limit in horizontal mode - let it be readable
                                                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                        if st.session_state.flow_layout != 'horizontal':
                                                            st.caption("🤖 Rendered via browser automation")
                                                    else:
                                                        raise Exception("Playwright returned empty HTML")
                                            except Exception as playwright_error:
                                                # Playwright failed, try screenshot API (priority 4)
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                            display_height = height  # No height limit in horizontal mode - let it be readable
                                                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                            if st.session_state.flow_layout != 'horizontal':
                                                                st.caption("📸 Screenshot (thum.io)")
                                                        else:
                                                            st.error(f"❌ HTTP {response.status_code}")
                                                    except:
                                                        st.error(f"❌ HTTP {response.status_code}")
                                                else:
                                                    st.error(f"❌ HTTP {response.status_code}")
                                        elif THUMIO_CONFIGURED:
                                            # No Playwright, try screenshot API (priority 4)
                                            try:
                                                screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                    display_height = height  # No height limit in horizontal mode - let it be readable
                                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                    if st.session_state.flow_layout != 'horizontal':
                                                        st.caption("📸 Screenshot (thum.io)")
                                                else:
                                                    st.error(f"❌ HTTP {response.status_code}")
                                            except:
                                                st.error(f"❌ HTTP {response.status_code}")
                                        else:
                                            st.error(f"❌ HTTP {response.status_code}")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:100]}")
                    else:
                        with landing_preview_container:
                            st.warning("No landing page URL")
                    
                    # Landing Page Details - Inline on RIGHT in vertical mode
                    if st.session_state.flow_layout == 'vertical' and landing_card_right:
                        with landing_card_right:
                            keyword = current_flow.get('keyword_term', 'N/A')
                            adv_url = current_flow.get('reporting_destination_url', '')
                            
                            st.markdown("**🎯 Landing Page Details**")
                            # Inline horizontal layout - all on same line, landing URL on RIGHT (NO keyword here)
                            st.markdown(f"""
                            <div style="display: inline-flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>Landing URL:</strong> <a href="{adv_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{adv_url[:50]}{"..." if len(adv_url) > 50 else ""}</a></span>' if adv_url and pd.notna(adv_url) else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Keyword → Page similarity score on right of landing page
                            if 'similarities' not in st.session_state or st.session_state.similarities is None:
                                if API_KEY:
                                    st.session_state.similarities = calculate_similarities(current_flow)
                                else:
                                    st.session_state.similarities = {}
                            
                            if 'similarities' in st.session_state and st.session_state.similarities:
                                render_similarity_score('kwd_to_page', st.session_state.similarities,
                                                       custom_title="Ad Copy → Landing Page Similarity",
                                                       tooltip_text="Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment.")
                
                # Fixed Similarity Scores Section for Horizontal Layout (BELOW frame line)
                if st.session_state.flow_layout == 'horizontal':
                    # Reduce spacing - minimal margin
                    st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                    st.markdown("""
                        <h2 style="font-size: 28px; font-weight: 700; color: #0f172a; margin: 20px 0 15px 0;">
                            🧠 Similarity Scores
                        </h2>
                    """, unsafe_allow_html=True)
                    
                    # Calculate similarity scores if not already done
                    if 'similarities' not in st.session_state or st.session_state.similarities is None:
                        if API_KEY:
                            st.session_state.similarities = calculate_similarities(current_flow)
                        else:
                            st.session_state.similarities = {}
                    
                    # Show all three scores in horizontal layout below frames - in ONE line
                    if 'similarities' in st.session_state and st.session_state.similarities:
                        score_cols = st.columns(3, gap='small')
                        
                        with score_cols[0]:
                            render_similarity_score('kwd_to_ad', st.session_state.similarities,
                                                   custom_title="Ad Copy → Ad Similarity",
                                                   tooltip_text="Measures how well the ad creative matches the search keyword. Higher scores indicate better keyword-ad alignment.")
                        
                        with score_cols[1]:
                            render_similarity_score('ad_to_page', st.session_state.similarities,
                                                   custom_title="Ad Copy → Landing Page Similarity",
                                                   tooltip_text="Measures how well the landing page fulfills the promises made in the ad copy. Higher scores indicate better ad-page consistency.")
                        
                        with score_cols[2]:
                            render_similarity_score('kwd_to_page', st.session_state.similarities,
                                                   custom_title="Ad Copy → Landing Page Similarity",
                                                   tooltip_text="Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment.")
                    else:
                        st.info("⏳ Similarity scores will be calculated after data loads")
                    
                    # Container div was removed - no closing tag needed
            
            else:
                st.warning("No data available for this campaign")
else:
    st.error("❌ Could not load data - Check FILE_A_ID and file sharing settings")
