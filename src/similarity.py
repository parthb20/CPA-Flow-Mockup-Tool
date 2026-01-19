# -*- coding: utf-8 -*-
"""
Similarity calculation functions
"""

import streamlit as st
import requests
import pandas as pd
import json
import re
from bs4 import BeautifulSoup
from src.utils import safe_float


def call_similarity_api(prompt):
    """Call FastRouter API for similarity scoring"""
    # Try to get API key from Streamlit secrets
    API_KEY = ""
    try:
        API_KEY = str(st.secrets["FASTROUTER_API_KEY"]).strip()
    except:
        try:
            API_KEY = str(st.secrets["OPENAI_API_KEY"]).strip()
        except:
            API_KEY = ""
    
    if not API_KEY:
        return {
            "error": True,
            "status_code": "no_api_key",
            "body": "FASTROUTER_API_KEY not found in Streamlit secrets. Add it to .streamlit/secrets.toml"
        }
    
    try:
        # Use correct FastRouter URL and Claude model
        response = requests.post(
            "https://go.fastrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-sonnet-4-20250514",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=45  # Increased timeout for Claude
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                score_data = json.loads(json_match.group())
                return {
                    "error": False,
                    "final_score": float(score_data.get('final_score', score_data.get('score', 0))),
                    "reason": score_data.get('reason', 'N/A'),
                    "topic_match": score_data.get('topic_match', 0),
                    "brand_match": score_data.get('brand_match', 0),
                    "promise_match": score_data.get('promise_match', 0),
                    "utility_match": score_data.get('utility_match', 0),
                    "keyword_match": score_data.get('keyword_match', 0),
                    "intent_match": score_data.get('intent_match', 0),
                    "intent": score_data.get('intent', ''),
                    "band": score_data.get('band', '')
                }
            return {"error": True, "status_code": response.status_code, "body": f"No JSON in response: {content[:200]}"}
        else:
            error_msg = f"API returned {response.status_code}: {response.text[:300]}"
            return {"error": True, "status_code": response.status_code, "body": error_msg}
    except Exception as e:
        return {"error": True, "status_code": "exception", "body": f"Exception: {str(e)}"}


def extract_text_from_html(html_content):
    """Extract clean text from HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=' ', strip=True)
    except:
        return ""


def fetch_page_content(url):
    """Fetch and extract text content from URL"""
    try:
        if not url or pd.isna(url) or str(url).lower() == 'null' or not str(url).strip():
            return ""
        
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if response.status_code == 200:
            # Limit page text to reasonable size for API
            page_text = extract_text_from_html(response.text)
            return page_text[:5000]  # Limit to 5000 chars for API
        return ""
    except:
        return ""


def calculate_similarities(flow_data):
    """Calculate all three similarity scores"""
    import time
    
    keyword = flow_data.get('keyword_term', '')
    ad_title = flow_data.get('ad_title', '')
    ad_desc = flow_data.get('ad_description', '')
    ad_text = f"{ad_title} {ad_desc}".strip()
    adv_url = flow_data.get('reporting_destination_url', '')
    
    # Quick validation
    if not keyword or not ad_text:
        return {
            'kwd_to_ad': {"error": True, "status_code": "missing_data", "body": "Missing keyword or ad text"},
            'ad_to_page': {"error": True, "status_code": "missing_data", "body": "Missing ad text"},
            'kwd_to_page': {"error": True, "status_code": "missing_data", "body": "Missing keyword"}
        }
    
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
        
        # If page fetch failed (403/etc), try OCR fallback from screenshot
        if not page_text:
            try:
                from src.ocr_utils import extract_text_from_screenshot_url
                from src.screenshot import get_screenshot_url
                screenshot_url = get_screenshot_url(adv_url, 'laptop')
                if screenshot_url:
                    page_text = extract_text_from_screenshot_url(screenshot_url)
            except:
                pass
        
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
