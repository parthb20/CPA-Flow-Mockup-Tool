# -*- coding: utf-8 -*-
"""
Flow Display Module for CPA Flow Analysis Tool
Handles rendering of the Flow Journey (Publisher, Creative, SERP, Landing Page)
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import html
import base64

from src.config import SERP_BASE_URL
from src.renderers import (
    render_mini_device_preview,
    render_similarity_score,
    inject_unique_id
)
from src.screenshot import get_screenshot_url, capture_with_playwright, capture_page_with_fallback
from src.serp import generate_serp_mockup
from src.similarity import calculate_similarities
from src.creative_renderer import render_creative_via_weaver, parse_keyword_array_from_flow
from src.flow_analysis import find_default_flow


# ============================================================================
# COMPREHENSIVE ENCODING HELPERS
# ============================================================================

def decode_with_multiple_encodings(response):
    """Robust encoding detection and decoding - Returns decoded HTML string"""
    detected_encoding = None
    
    # Method 1: Check Content-Type header
    content_type = response.headers.get('Content-Type', '')
    charset_match = re.search(r'charset=([^;\s]+)', content_type, re.IGNORECASE)
    if charset_match:
        detected_encoding = charset_match.group(1).strip('"\'')
    
    # Method 2: Try chardet library (optional but recommended)
    if not detected_encoding:
        try:
            import chardet
            detected = chardet.detect(response.content[:10000])
            if detected['encoding'] and detected['confidence'] > 0.7:
                detected_encoding = detected['encoding']
        except ImportError:
            pass
    
    # Method 3: Use apparent_encoding
    if not detected_encoding and response.apparent_encoding:
        detected_encoding = response.apparent_encoding
    
    # Method 4: Default to UTF-8
    if not detected_encoding:
        detected_encoding = 'utf-8'
    
    # Try decoding with multiple encodings
    page_html = None
    encodings_to_try = [detected_encoding, 'utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'cp1252', 'gb2312', 'shift-jis']
    
    for encoding in encodings_to_try:
        try:
            page_html = response.content.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError, AttributeError):
            continue
    
    # Last resort: force decode with ignore
    if not page_html:
        page_html = response.content.decode('utf-8', errors='ignore')
    
    return page_html


def clean_and_prepare_html(page_html, base_url):
    """Clean HTML and add proper encoding declarations + base tag for CSS/JS loading"""
    # Remove BOM markers
    page_html = page_html.lstrip('\ufeff\ufffe\u200b')
    
    # Add DOCTYPE if missing
    if '<!DOCTYPE' not in page_html.upper()[:200]:
        page_html = '<!DOCTYPE html>\n' + page_html
    
    # Remove ALL existing charset declarations
    page_html = re.sub(r'<meta[^>]*charset[^>]*>', '', page_html, flags=re.IGNORECASE)
    
    # Remove existing base tags
    page_html = re.sub(r'<base[^>]*>', '', page_html, flags=re.IGNORECASE)
    
    # Add UTF-8 charset + BASE TAG as FIRST meta tags
    # The base tag tells the browser where to load CSS/JS/images from
    if '<head>' in page_html.lower():
        page_html = re.sub(
            r'(<head[^>]*>)',
            f'\\1\n<meta charset="UTF-8">\n<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n<base href="{base_url}">',
            page_html,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        page_html = re.sub(
            r'(<html[^>]*>)',
            f'\\1\n<head>\n<meta charset="UTF-8">\n<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n<base href="{base_url}">\n</head>',
            page_html,
            count=1,
            flags=re.IGNORECASE
        )
    
    # Fix relative URLs (belt and suspenders - base tag should handle this, but we do it anyway)
    page_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                      lambda m: f'src="{urljoin(base_url, m.group(1))}"', page_html)
    page_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                      lambda m: f'href="{urljoin(base_url, m.group(1))}"', page_html)
    
    return page_html


def render_html_with_proper_encoding(page_html, device, unique_id_prefix, url, flow, scrolling=False):
    """Render HTML with proper encoding using standard renderer"""
    from src.renderers import render_mini_device_preview, inject_unique_id
    
    # Use standard renderer with use_srcdoc for proper device preview
    preview_html, height, _ = render_mini_device_preview(
        page_html, 
        is_url=False, 
        device=device, 
        use_srcdoc=True
    )
    
    # Inject unique ID for cache busting
    preview_html = inject_unique_id(preview_html, unique_id_prefix, url, device, flow)
    
    return preview_html, height

# ============================================================================


def render_flow_journey(campaign_df, current_flow, api_key, playwright_available, thumio_configured, thumio_referer_domain):
    """
    Render the complete Flow Journey section with all stages:
    Publisher URL, Creative, SERP, Landing Page, and Similarity Scores
    
    Args:
        campaign_df: Filtered campaign dataframe
        current_flow: Current flow dictionary
        api_key: API key for similarity calculations
        playwright_available: Boolean indicating if Playwright is available
        thumio_configured: Boolean indicating if screenshot API is configured (kept for backwards compatibility)
        thumio_referer_domain: Referer domain (kept for backwards compatibility)
    """
    # Layout and Device controls - COMPACT and TOGETHER
    st.markdown("""
    <style>
    /* Make dropdowns extra compact and entire area clickable including arrows */
    div[data-testid="stSelectbox"] > div > div {
        min-height: 36px !important;
        height: 36px !important;
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] > div > div > div {
        padding: 6px 10px !important;
        font-size: 14px !important;
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] svg {
        pointer-events: all !important;
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] {
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        cursor: pointer !important;
    }
    
    /* Completely remove empty spacing elements */
    div[style*="margin-top: 4px; margin-bottom: 4px"],
    div[style*="margin: 0; padding: 0"]:empty,
    div.element-container:empty,
    [data-testid="stVerticalBlock"] > div:empty {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        visibility: hidden !important;
        position: absolute !important;
    }
    
    /* Increase only the FLOW CARDS horizontal container height for URL space */
    section[data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
        min-height: 900px !important;
    }
    
    /* AGGRESSIVE GAP REMOVAL */
    .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    .main > div > div > div > div {
        gap: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Get flow_type from session state
    flow_type = st.session_state.get('flow_type', 'Best')
    all_flows = st.session_state.get('all_flows', [])
    current_flow_index = st.session_state.get('current_flow_index', 0)
    
    # Flow navigation - STRICTLY LEFT ALIGNED, separate from filters - CLICKABLE
    if len(all_flows) > 1:
        # Add CSS for navigation buttons
        st.markdown("""
        <style>
        button[key="nav_prev_btn"], button[key="nav_next_btn"] {
            padding: 0.25rem 0.5rem !important;
            font-size: 1.1rem !important;
            min-height: 2rem !important;
            height: 2rem !important;
            background: white !important;
            border: 2px solid #cbd5e1 !important;
            border-radius: 0.375rem !important;
        }
        button[key="nav_prev_btn"]:hover, button[key="nav_next_btn"]:hover {
            background: #f1f5f9 !important;
            border-color: #94a3b8 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        prev_disabled = current_flow_index == 0
        next_disabled = current_flow_index >= len(all_flows) - 1
        
        # Create clickable navigation with proper Streamlit rerun
        nav_col1, nav_col2, nav_col3 = st.columns([0.5, 2, 0.5])
        
        with nav_col1:
            if not prev_disabled:
                if st.button("⬅️", key='nav_prev_btn', help="Previous flow"):
                    st.session_state.current_flow_index = max(0, current_flow_index - 1)
                    st.session_state.current_flow = all_flows[st.session_state.current_flow_index].copy()
                    st.rerun()
            else:
                st.markdown('<span style="opacity: 0.3; font-size: 1.1rem; cursor: not-allowed;">⬅️</span>', unsafe_allow_html=True)
        
        with nav_col2:
            # Get current flow rank
            current_rank = st.session_state.current_flow.get('flow_rank', current_flow_index + 1) if st.session_state.current_flow else current_flow_index + 1
            st.markdown(f'<div style="text-align: center; padding-top: 0.3rem;"><span style="font-size: 0.85rem; color: #0f172a; font-weight: 700;">Flow {current_flow_index + 1} of {len(all_flows)} <span style="color: #3b82f6;">(Rank {current_rank})</span></span></div>', unsafe_allow_html=True)
        
        with nav_col3:
            if not next_disabled:
                if st.button("➡️", key='nav_next_btn', help="Next flow"):
                    st.session_state.current_flow_index = min(len(all_flows) - 1, current_flow_index + 1)
                    st.session_state.current_flow = all_flows[st.session_state.current_flow_index].copy()
                    st.rerun()
            else:
                st.markdown('<span style="opacity: 0.3; font-size: 1.1rem; cursor: not-allowed;">➡️</span>', unsafe_allow_html=True)
    
    # All controls in one row - Best/Worst FIRST, then Layout, Device, Domain, Keyword
    control_col1, control_col2, control_col3, control_col4, control_col5 = st.columns([1, 1, 1, 1.2, 1.2])
    
    with control_col1:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Flow Type</p>', unsafe_allow_html=True)
        flow_type_choice = st.selectbox("Flow Type", ['Best', 'Worst'], 
                                        index=0 if flow_type == 'Best' else 1,
                                        key='flow_type_dropdown', label_visibility="collapsed")
        if flow_type_choice != flow_type:
            st.session_state.flow_type = flow_type_choice
            st.rerun()
    
    with control_col2:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Layout</p>', unsafe_allow_html=True)
        layout_choice = st.selectbox("Layout", ['Horizontal', 'Vertical'], 
                                     index=0 if st.session_state.flow_layout == 'horizontal' else 1, 
                                     key='layout_dropdown', label_visibility="collapsed")
        if (layout_choice == 'Horizontal' and st.session_state.flow_layout != 'horizontal') or \
           (layout_choice == 'Vertical' and st.session_state.flow_layout != 'vertical'):
            st.session_state.flow_layout = 'horizontal' if layout_choice == 'Horizontal' else 'vertical'
            st.rerun()
    
    with control_col3:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Device</p>', unsafe_allow_html=True)
        device_all = st.selectbox("Device", ['Mobile', 'Tablet', 'Laptop'], 
                                 key='device_all', index=0, label_visibility="collapsed")
        # Extract actual device name
        device_all = device_all.lower()
    
    with control_col4:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Domain</p>', unsafe_allow_html=True)
        domains = ['All Domains'] + sorted(campaign_df['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in campaign_df.columns else ['All Domains']
        selected_domain_inline = st.selectbox("Domain", domains, key='domain_inline_filter', label_visibility="collapsed")
        if selected_domain_inline != 'All Domains':
            campaign_df = campaign_df[campaign_df['publisher_domain'] == selected_domain_inline]
    
    with control_col5:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Keyword</p>', unsafe_allow_html=True)
        keywords = ['All Keywords'] + sorted(campaign_df['keyword_term'].dropna().unique().tolist()) if 'keyword_term' in campaign_df.columns else ['All Keywords']
        selected_keyword_inline = st.selectbox("Keyword", keywords, key='keyword_inline_filter', label_visibility="collapsed")
        if selected_keyword_inline != 'All Keywords':
            campaign_df = campaign_df[campaign_df['keyword_term'] == selected_keyword_inline]
    
    # CRITICAL: If domain or keyword filter was applied, recalculate the best flow from filtered data
    # This ensures the flow updates to show the best performing combination for the selected filters
    if (selected_domain_inline != 'All Domains' or selected_keyword_inline != 'All Keywords'):
        if len(campaign_df) > 0:
            new_flow = find_default_flow(campaign_df)
            if new_flow:
                current_flow = new_flow  # Update current_flow with the recalculated best flow
        else:
            # If no data after filtering, show warning and keep original flow
            st.warning(f"⚠️ No data found for the selected filters. Showing original flow.")
    
    # ZERO GAPS CSS - Remove empty containers
    st.markdown("""
    <style>
    /* Zero spacing */
    .stRadio { 
        margin: 0 !important; 
        padding: 0 !important; 
    }
    
    /* Zero padding for columns */
    [data-testid="column"] {
        padding: 4px !important;
        margin: 0 !important;
    }
    
    /* Zero title spacing */
    [data-testid="column"] h3:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
        margin-bottom: 4px !important;
    }
    
    /* Zero spacing between elements */
    [data-testid="column"] .element-container {
        margin-top: 0 !important;
    }
    
    /* First element no margin */
    [data-testid="column"] > div > .element-container:first-child {
        margin-top: 0 !important;
    }
    
    /* Zero gap in sections */
    section[data-testid="stVerticalBlock"] {
        gap: 0 !important;
    }
    
    /* Remove all streamlit default spacing */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize containers for both layouts
    stage_cols = None
    vertical_preview_col = None
    vertical_info_col = None
    stage_1_info_container = None
    stage_2_info_container = None
    stage_3_info_container = None
    stage_4_info_container = None
    
    if st.session_state.flow_layout == 'horizontal':
        # Add CSS to force single line and prevent wrapping, ensure equal card heights and boundaries
        # Match advanced-horizontal mode alignment - AGGRESSIVE FIXES
        st.markdown("""
        <style>
        /* CRITICAL: Remove ALL top spacing from everything */
        .block-container {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        /* Target Streamlit columns directly - remove ALL padding/margin */
        [data-testid="column"] {
            flex-shrink: 0 !important;
            min-width: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: stretch !important;
            padding: 0 !important;
            margin: 0 !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        [data-testid="column"] > div {
            padding: 0 !important;
            margin: 0 !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        .stColumn > div {
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
            align-items: stretch !important;
            padding: 0 !important;
            margin: 0 !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        /* Remove Streamlit's default element-container spacing */
        [data-testid="column"] .element-container {
            padding: 0 !important;
            margin: 0 !important;
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        /* Remove spacing from first element-container */
        [data-testid="column"] .element-container:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        /* AGGRESSIVE: Remove spacing from ALL element-containers at start */
        [data-testid="column"] > div > .element-container:first-of-type {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        /* Remove spacing from markdown elements at top of columns */
        [data-testid="column"] h3:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        /* Remove spacing from radio button container */
        .stRadio {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        /* Reduce bottom spacing but keep top/side spacing */
        .stHorizontalBlock {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        .stHorizontalBlock > div {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
        }
        /* Remove bottom padding from columns */
        .stColumn {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
        }
        /* Remove extra spacing from markdown and containers */
        .element-container {
            margin-bottom: 0 !important;
        }
        [data-testid="stMarkdownContainer"] {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        
        /* Responsive gaps between stage cards and details */
        [data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            margin-bottom: clamp(0.5rem, 1vw, 1rem) !important;
        }
        
        /* Responsive spacing between cards in vertical layout */
        [data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
            margin-bottom: clamp(0.75rem, 1.5vw, 1.5rem) !important;
        }
        
        /* Consistent spacing between card content and details */
        .stMarkdown + .stMarkdown {
            margin-top: clamp(0.25rem, 0.5vw, 0.5rem) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create columns for the actual cards - all equal size with large gap
        stage_cols = st.columns([1, 1, 1, 1], gap='large')
    else:
        # Vertical layout - cards extend full width, details inline within card boundaries
        stage_cols = None
    
    # Stage 1: Publisher URL
    if st.session_state.flow_layout == 'vertical':
        stage_1_container = st.container()
    else:
        stage_1_container = stage_cols[0]
    
    # Initialize card columns for vertical layout
    card_col_left = None
    card_col_right = None
    
    # Get current domain and URL for Publisher URL section
    current_dom = current_flow.get('publisher_domain', '')
    current_url = current_flow.get('publisher_url', '')
    
    # Get domains and URLs for filtering
    keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
    current_kw = current_flow.get('keyword_term', keywords[0] if keywords else '')
    kw_filtered = campaign_df[campaign_df['keyword_term'] == current_kw]
    domains = sorted(kw_filtered['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in kw_filtered.columns else []
    
    # Get URLs for current domain
    dom_filtered = kw_filtered[kw_filtered['publisher_domain'] == current_dom] if current_dom and domains else kw_filtered
    urls = dom_filtered['publisher_url'].dropna().unique().tolist() if 'publisher_url' in dom_filtered.columns else []
    
    with stage_1_container:
        if st.session_state.flow_layout == 'vertical':
            card_col_left, card_col_right = st.columns([0.6, 0.4])
            with card_col_left:
                st.markdown('<h3 style="font-size: clamp(2rem, 1.75rem + 1.3vw, 2.5rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>📰 Publisher URL</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: clamp(1.5rem, 1.3rem + 1vw, 1.75rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;"><strong>📰 Publisher URL</strong></h3>', unsafe_allow_html=True)
        
        pub_url = current_flow.get('publisher_url', '')
        preview_container = card_col_left if st.session_state.flow_layout == 'vertical' and card_col_left else stage_1_container
        
        if pub_url and pub_url != 'NOT_FOUND' and pd.notna(pub_url) and str(pub_url).strip():
            with preview_container:
                rendered = False
                
                # Method 1: Try Playwright FIRST (most reliable, handles all cases)
                playwright_error = None
                if playwright_available:
                    try:
                        with st.spinner("🔄 Loading with browser..."):
                            page_html = capture_with_playwright(pub_url, device=device_all)
                            if page_html:
                                if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                    preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                    st.caption("📸 Screenshot (API)")
                                else:
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                    preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                                    st.caption("🤖 Browser (Playwright)")
                                rendered = True
                    except Exception as e:
                        playwright_error = str(e)
                
                # Method 2: If Playwright unavailable/failed, try HTML fetch with encoding fixes
                if not rendered:
                    try:
                        # Try to fetch HTML directly with proper encoding
                        response = requests.get(
                            pub_url,
                            timeout=15,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9'
                            },
                            allow_redirects=True
                        )
                        
                        if response.status_code == 200:
                            # Use encoding helper to decode properly
                            page_html = decode_with_multiple_encodings(response)
                            page_html = clean_and_prepare_html(page_html, pub_url)
                            
                            # Render with proper encoding
                            preview_html, display_height = render_html_with_proper_encoding(
                                page_html, device_all, 'pub_html', pub_url, current_flow, scrolling=False
                            )
                            st.components.v1.html(preview_html, height=display_height, scrolling=False)
                            st.caption("📄 HTML")
                            rendered = True
                        else:
                            # If HTML fetch fails, try iframe as last resort
                            raise Exception(f"HTTP {response.status_code}")
                    except:
                        pass
                
                # Method 3: Iframe as last fallback
                if not rendered:
                    try:
                        preview_html, height, _ = render_mini_device_preview(pub_url, is_url=True, device=device_all, display_url=pub_url)
                        preview_html = inject_unique_id(preview_html, 'pub_iframe', pub_url, device_all, current_flow)
                        st.components.v1.html(preview_html, height=height, scrolling=False)
                        st.caption("📺 Iframe (may be blocked by site)")
                        rendered = True
                    except:
                        pass
                
                # Method 3: Last resort - show message with link
                if not rendered:
                    st.warning("⚠️ Could not load page preview")
                    st.markdown(f"[🔗 Click here to open: {pub_url}]({pub_url})")
        else:
            with preview_container:
                st.warning("⚠️ No valid publisher URL in data")
        
        if st.session_state.flow_layout == 'vertical' and card_col_right:
            with card_col_right:
                # No extra spacing - tight layout
                st.markdown("""
                <div style="margin-bottom: 4px;">
                    <span style="font-weight: 900; color: #0f172a; font-size: 20px;">
                        <strong>📰 Publisher URL Details</strong>
                        <span title="Similarity scores measure how well different parts of your ad flow match: Keyword → Ad (ad matches keyword), Ad → Page (landing page matches ad), Keyword → Page (overall flow consistency)" style="cursor: help; color: #3b82f6; font-size: 13px; margin-left: 4px;"><strong>ℹ️</strong></span>
                    </span>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem); font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);">
                    <div style="font-weight: 900; color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem); margin-bottom: clamp(0.125rem, 0.1rem + 0.1vw, 0.125rem);"><strong>Domain:</strong></div>
                    <div style="margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);">{html.escape(str(current_dom))}</div>
                    {f'<div style="margin-top: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem); font-weight: 900; color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem); margin-bottom: clamp(0.125rem, 0.1rem + 0.1vw, 0.125rem);"><strong>URL:</strong></div><div style="margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);"><a href="{current_url}" style="color: #3b82f6; text-decoration: none;">{html.escape(str(current_url))}</a></div>' if current_url and pd.notna(current_url) else ''}
                </div>
                """, unsafe_allow_html=True)
        
        # Close wrapper div for horizontal layout
        if st.session_state.flow_layout == 'horizontal':
            # Show info BELOW card preview in horizontal layout - ALWAYS show
            st.markdown(f"""
            <div style='margin-top: 8px; font-size: 14px;'>
                <div style='font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;'><strong>Domain:</strong></div>
                <div style='margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 13px;'>{html.escape(str(current_dom))}</div>
                {f'<div style="margin-top: 6px; font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;"><strong>URL:</strong></div><div style="margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 13px;"><a href="{current_url}" style="color: #3b82f6; text-decoration: none;">{html.escape(str(current_url))}</a></div>' if current_url and pd.notna(current_url) else ''}
            </div>
            """, unsafe_allow_html=True)
    
    # Arrow divs removed - no longer needed
    
    # Stage 2: Creative
    if st.session_state.flow_layout == 'vertical':
        stage_2_container = st.container()
        creative_card_left = None
        creative_card_right = None
    else:
        stage_2_container = stage_cols[1]
        creative_card_left = None
        creative_card_right = None
    
    with stage_2_container:
        if st.session_state.flow_layout == 'vertical':
            creative_card_left, creative_card_right = st.columns([0.6, 0.4])
            with creative_card_left:
                st.markdown('<h3 style="font-size: clamp(2rem, 1.75rem + 1.3vw, 2.5rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>🎨 Creative</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: clamp(1.5rem, 1.3rem + 1vw, 1.75rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;"><strong>🎨 Creative</strong></h3>', unsafe_allow_html=True)
        
        creative_id = current_flow.get('creative_id', 'N/A')
        creative_name = current_flow.get('creative_template_name', 'N/A')
        creative_size = current_flow.get('Creative_Size_Final', 'N/A')  # From File A
        keyword = current_flow.get('keyword_term', 'N/A')
        
        # Keyword will be shown BELOW card preview
        
        if st.session_state.flow_layout != 'vertical':
            if st.session_state.view_mode == 'advanced':
                with st.expander("⚙️", expanded=False):
                    st.caption(f"**ID:** {creative_id}")
                    st.caption(f"**Name:** {creative_name}")
                    st.caption(f"**Size:** {creative_size}")
        
        creative_preview_container = creative_card_left if st.session_state.flow_layout == 'vertical' and creative_card_left else stage_2_container
        
        with creative_preview_container:
            # Try rendering with File D (pre-rendered) or File C (Weaver API)
            creative_rendered = False
            
            # Check if we have either File D or File C
            has_file_d = st.session_state.get('data_d') is not None
            has_file_c = st.session_state.get('data_c') is not None
            
            if has_file_d or has_file_c:
                try:
                    # Get cipher key from secrets or use default
                    cipher_key = None
                    try:
                        cipher_key = st.secrets.get("WEAVER_CIPHER_KEY", None)
                        if cipher_key:
                            # Clean the key (remove quotes, whitespace)
                            cipher_key = str(cipher_key).strip().strip("'").strip('"')
                    except Exception:
                        cipher_key = None
                    
                    # Parse keyword array from flow
                    keyword_array = parse_keyword_array_from_flow(current_flow)
                    
                    # Render via Weaver API with File D priority
                    # File C is optional - if not present, only File D will be used
                    rendered_html, error_msg = render_creative_via_weaver(
                        creative_id=creative_id,
                        creative_size=creative_size,
                        keyword_array=keyword_array,
                        creative_requests_df=st.session_state.get('data_c', None),
                        cipher_key=cipher_key,
                        prerendered_df=st.session_state.get('data_d', None)
                    )
                    
                    if rendered_html:
                        # Render the creative with responsive height
                        # Calculate height based on creative aspect ratio and responsive width
                        try:
                            width_str, height_str = creative_size.split('x')
                            creative_height = int(height_str)
                            creative_width = int(width_str)
                            # Calculate aspect ratio
                            aspect_ratio = creative_height / creative_width
                            # Use a responsive base width (22vw average ~300px on laptop, ~420px on big screen)
                            # Calculate proportional height
                            base_responsive_height = int(330 * aspect_ratio)  # 330px is avg of min/max
                            # Cap at reasonable limits
                            display_height = min(max(base_responsive_height, 400), 700)
                            needs_scroll = creative_height > display_height or creative_width > 600
                        except:
                            display_height = 500
                            needs_scroll = False
                        
                        st.components.v1.html(rendered_html, height=display_height, scrolling=needs_scroll)
                        creative_rendered = True
                    elif error_msg:
                        # Show detailed error message
                        st.error(f"❌ {error_msg}")
                except Exception as e:
                    st.error(f"⚠️ Creative error: {str(e)[:200]}")
            else:
                # Neither File C nor File D available
                st.error(f"❌ Creative data not found for {creative_id} ({creative_size})")
            
            # Fallback: Try response column from File A if File D failed
            if not creative_rendered:
                response_value = current_flow.get('response', None)
                if response_value and pd.notna(response_value) and str(response_value).strip():
                    try:
                        # Parse and render response from File A
                        if isinstance(response_value, str) and response_value.strip():
                            # Extract width and height from creative_size
                            try:
                                width_str, height_str = creative_size.split('x')
                                width, height = int(width_str), int(height_str)
                            except:
                                width, height = 300, 250
                            
                            # Wrap in HTML container
                            rendered_html = f"""
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <meta charset="UTF-8">
                                <style>
                                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                                    body {{ width: {width}px; height: {height}px; overflow: hidden; }}
                                </style>
                            </head>
                            <body>
                                {response_value}
                            </body>
                            </html>
                            """
                            # Use responsive height based on creative size
                            try:
                                width_str, height_str = creative_size.split('x')
                                creative_height = int(height_str)
                                creative_width = int(width_str)
                                aspect_ratio = creative_height / creative_width
                                display_height = min(max(int(330 * aspect_ratio), 400), 700)
                            except:
                                display_height = 500
                            st.components.v1.html(rendered_html, height=display_height, scrolling=True)
                            creative_rendered = True
                    except Exception as e:
                        pass
            
            # Show placeholder if all rendering failed
            if not creative_rendered:
                # Use consistent height to match other stage boxes
                st.markdown(f"""
                <div style="min-height: 650px; display: flex; align-items: center; justify-content: center; background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 8px;">
                    <div style="text-align: center; color: #64748b;">
                        <div style="font-size: 48px; margin-bottom: 8px;">⚠️</div>
                        <div style="font-weight: 600; font-size: 14px;">No creative data</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Show creative details - ALWAYS (symmetric with heading)
        if st.session_state.flow_layout == 'vertical' and creative_card_right:
            details_container = creative_card_right
        elif st.session_state.flow_layout != 'vertical':
            details_container = creative_preview_container
        else:
            details_container = creative_preview_container  # Fallback
            
        with details_container:
            creative_size = current_flow.get('Creative_Size_Final', 'N/A')
            creative_name = current_flow.get('creative_template_name', 'N/A')
            keyword = current_flow.get('keyword_term', 'N/A')
            
            # Details start at same position as heading (no extra margin for vertical) - RESPONSIVE
            st.markdown(f"""
            <div style='margin-top: 0; margin-bottom: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem);'>
                <strong style='color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem);'>Keyword:</strong> 
                <span style='color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);'>{html.escape(str(keyword))}</span>
            </div>
            <div style='margin-bottom: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem);'>
                <strong style='color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem);'>Creative ID:</strong> 
                <span style='color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);'>{creative_id}</span>
            </div>
            <div style='margin-bottom: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem);'>
                <strong style='color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem);'>Size:</strong> 
                <span style='color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);'>{creative_size}</span>
            </div>
            <div style='margin-bottom: 0;'>
                <strong style='color: #0f172a; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem);'>Template:</strong> 
                <span style='color: #64748b; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);'>{creative_name}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Calculate similarities if not already done
            if 'similarities' not in st.session_state or st.session_state.similarities is None:
                if api_key:
                    st.session_state.similarities = calculate_similarities(current_flow)
                else:
                    st.session_state.similarities = {}
            
            # Add Keyword → Ad similarity for VERTICAL layout
            if st.session_state.flow_layout == 'vertical':
                if 'similarities' in st.session_state and st.session_state.similarities:
                    st.markdown("<div style='margin-top: clamp(0.25rem, 0.3vw, 0.375rem);'></div>", unsafe_allow_html=True)
                    render_similarity_score('kwd_to_ad', st.session_state.similarities,
                                           custom_title="Keyword → Ad Copy Similarity",
                                           tooltip_text="Measures keyword-ad alignment. 70%+ = Good Match (keywords clearly in ad copy), 40-69% = Fair Match (topic relevance present), <40% = Poor Match (weak/no connection)",
                                           max_height=1040)
    
    # Arrow divs removed - no longer needed
    
    # Stage 3: SERP
    serp_template_key = current_flow.get('serp_template_key', '')
    if serp_template_key and pd.notna(serp_template_key) and str(serp_template_key).strip():
        serp_url = SERP_BASE_URL + str(serp_template_key)
    else:
        serp_url = None
    
    if st.session_state.flow_layout == 'vertical':
        stage_3_container = st.container()
        serp_card_left = None
        serp_card_right = None
    else:
        if stage_cols:
            stage_3_container = stage_cols[2]
        else:
            stage_3_container = st.container()
        serp_card_left = None
        serp_card_right = None
    
    with stage_3_container:
        if st.session_state.flow_layout == 'vertical':
            serp_card_left, serp_card_right = st.columns([0.6, 0.4])
            with serp_card_left:
                st.markdown('<h3 style="font-size: clamp(2rem, 1.75rem + 1.3vw, 2.5rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>📄 SERP</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: clamp(1.5rem, 1.3rem + 1vw, 1.75rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;"><strong>📄 SERP</strong></h3>', unsafe_allow_html=True)
        
        serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
        serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
        serp_key = current_flow.get('serp_template_key', 'N/A')
        
        # SERP info removed from above card - will be shown on right side only, not below card
        
        ad_title = current_flow.get('ad_title', '')
        ad_desc = current_flow.get('ad_description', '')
        ad_display_url = current_flow.get('ad_display_url', '')
        keyword = current_flow.get('keyword_term', '')
        
        serp_html = None
        if 'data_b' in st.session_state and st.session_state.data_b:
            is_dict = isinstance(st.session_state.data_b, dict)
            is_list = isinstance(st.session_state.data_b, list)
            if (is_dict and len(st.session_state.data_b) > 0) or (is_list and len(st.session_state.data_b) > 0):
                serp_html = generate_serp_mockup(current_flow, st.session_state.data_b)
        
        serp_preview_container = serp_card_left if st.session_state.flow_layout == 'vertical' and serp_card_left else stage_3_container
        
        if serp_html and serp_html.strip():
            with serp_preview_container:
                preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                preview_html = inject_unique_id(preview_html, 'serp_template', serp_url or '', device_all, current_flow)
                display_height = height
                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                if st.session_state.flow_layout != 'horizontal':
                    st.caption("📺 SERP (from template)")
        
        elif serp_url:
            with serp_preview_container:
                try:
                    response = requests.get(serp_url, timeout=15, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9'
                    })
                    
                    if response.status_code == 200:
                        serp_html = response.text
                        serp_html = serp_html.replace('min-device-width', 'min-width')
                        serp_html = serp_html.replace('max-device-width', 'max-width')
                        serp_html = serp_html.replace('min-device-height', 'min-height')
                        serp_html = serp_html.replace('max-device-height', 'max-height')
                        
                        soup = BeautifulSoup(serp_html, 'html.parser')
                        replacement_made = False
                        
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
                        
                        if ad_title:
                            serp_html_temp = str(soup)
                            serp_html_temp = re.sub(
                                r'(<div class="title">)[^<]*(</div>)',
                                f'\\1{ad_title}\\2',
                                serp_html_temp,
                                count=1
                            )
                            soup = BeautifulSoup(serp_html_temp, 'html.parser')
                            replacement_made = True
                        
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
                        
                        if not replacement_made:
                            st.warning("⚠️ No matching elements found for replacement. Check SERP HTML structure.")
                        
                        serp_html = str(soup)
                        serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                          lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                        serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                          lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                        
                        preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                        preview_html = inject_unique_id(preview_html, 'serp_injected', serp_url, device_all, current_flow)
                        display_height = height
                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                        if st.session_state.flow_layout != 'horizontal':
                            st.caption("📺 SERP with injected ad content")
                    
                    elif response.status_code == 403:
                        if playwright_available:
                            with st.spinner("🔄 Using browser automation..."):
                                page_html = capture_with_playwright(serp_url, device=device_all)
                                if page_html and '<!-- SCREENSHOT_FALLBACK -->' not in page_html:
                                    soup = BeautifulSoup(page_html, 'html.parser')
                                    
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
                                        from bs4 import NavigableString
                                        for child in list(first_title.children):
                                            if isinstance(child, NavigableString):
                                                child.extract()
                                        first_title.append(ad_title)
                                    
                                    desc_elements = soup.find_all(class_=re.compile(r'desc', re.IGNORECASE))
                                    if desc_elements and ad_desc:
                                        first_desc = desc_elements[0]
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
                                    serp_html = serp_html.replace('min-device-width', 'min-width')
                                    serp_html = serp_html.replace('max-device-width', 'max-width')
                                    serp_html = serp_html.replace('min-device-height', 'min-height')
                                    serp_html = serp_html.replace('max-device-height', 'max-height')
                                    serp_html = re.sub(r'min-height\s*:\s*calc\(100[sv][vh]h?[^)]*\)\s*;?', '', serp_html, flags=re.IGNORECASE)
                                    
                                    serp_html = re.sub(r'src=["\'](?!http|//|data:)([^"\']+)["\']', 
                                                      lambda m: f'src="{urljoin(serp_url, m.group(1))}"', serp_html)
                                    serp_html = re.sub(r'href=["\'](?!http|//|#|javascript:)([^"\']+)["\']', 
                                                      lambda m: f'href="{urljoin(serp_url, m.group(1))}"', serp_html)
                                    
                                    serp_html = re.sub(
                                        r'<head>',
                                        '<head><style>body, p, div, span, h1, h2, h3, h4, h5, h6, a, li, td, th { writing-mode: horizontal-tb !important; text-orientation: mixed !important; }</style>',
                                        serp_html,
                                        flags=re.IGNORECASE,
                                        count=1
                                    )
                                    
                                    preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True)
                                    preview_html = inject_unique_id(preview_html, 'serp_playwright', serp_url, device_all, current_flow)
                                    display_height = height
                                    st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                    if st.session_state.flow_layout != 'horizontal':
                                        st.caption("📺 SERP (via Playwright)")
                                else:
                                    st.warning("⚠️ Could not load SERP. Set SCREENSHOT_API_KEY in secrets")
                        else:
                            st.error(f"HTTP {response.status_code}")
                    else:
                        st.error(f"HTTP {response.status_code}")
                    
                except Exception as e:
                    st.error(f"Load failed: {str(e)[:100]}")
        else:
            with serp_preview_container:
                st.warning("⚠️ No SERP URL found in mapping")
        
        if st.session_state.flow_layout == 'vertical' and serp_card_right:
            with serp_card_right:
                # Show SERP details with Template Key FIRST
                serp_template_key = current_flow.get('serp_template_key', 'N/A')
                
                st.markdown("<h4 style='font-size: 20px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0;'><strong>📄 SERP Details</strong></h4>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 6px; font-size: 14px;">
                    <div style="font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;"><strong>Template Key:</strong></div>
                    <div style="margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 13px;">{html.escape(str(serp_template_key))}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Show Ad Copy → Landing Page similarity BELOW SERP details
                st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if api_key:
                        st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                if 'similarities' in st.session_state and st.session_state.similarities:
                    render_similarity_score('ad_to_page', st.session_state.similarities,
                                           custom_title="Ad Copy → Landing Page Similarity",
                                           tooltip_text="Measures ad-to-page consistency. 70%+ = Good Match (page delivers on ad promises), 40-69% = Fair Match (partial fulfillment), <40% = Poor Match (misleading ad copy)")
        
        # Close wrapper div for horizontal layout
        if st.session_state.flow_layout == 'horizontal':
            # Show SERP Template Key BELOW card preview in horizontal layout
            serp_template_key = current_flow.get('serp_template_key', 'N/A')
            st.markdown(f"""
            <div style='margin-top: 8px; font-size: 14px;'>
                <div style="font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;"><strong>Template Key:</strong></div>
                <div style="margin-left: 0; margin-top: 0; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 13px;">{html.escape(str(serp_template_key))}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Arrow divs removed - no longer needed
    
    # Stage 4: Landing Page
    if st.session_state.flow_layout == 'vertical':
        stage_4_container = st.container()
        landing_card_left = None
        landing_card_right = None
    else:
        if stage_cols:
            stage_4_container = stage_cols[3]
        else:
            stage_4_container = st.container()
        landing_card_left = None
        landing_card_right = None
    
    with stage_4_container:
        if st.session_state.flow_layout == 'vertical':
            landing_card_left, landing_card_right = st.columns([0.6, 0.4])
            with landing_card_left:
                st.markdown('<h3 style="font-size: clamp(2rem, 1.75rem + 1.3vw, 2.5rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>🎯 Landing Page</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: clamp(1.5rem, 1.3rem + 1vw, 1.75rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;"><strong>🎯 Landing Page</strong></h3>', unsafe_allow_html=True)
        
        # Use Destination_Url as the landing page URL
        adv_url = current_flow.get('Destination_Url', '') or current_flow.get('reporting_destination_url', '')
        flow_clicks = current_flow.get('clicks', 0)
        
        # Landing URL will be shown BELOW card preview
        
        # Old code removed
        if False:
            st.markdown(f"""
            <div style="margin-bottom: 8px; font-size: 14px;">
                <div style="font-weight: 700; color: #0f172a; font-size: 17px; margin-bottom: 4px;"><strong>Landing URL:</strong></div>
                <div style="margin-left: 8px; word-break: break-word;"><a href="{adv_url}" style="color: #3b82f6; text-decoration: none;">{html.escape(str(adv_url))}</a></div>
            </div>
            """, unsafe_allow_html=True)
        
        landing_preview_container = landing_card_left if st.session_state.flow_layout == 'vertical' and landing_card_left else stage_4_container
        
        if adv_url and pd.notna(adv_url) and str(adv_url).strip():
            with landing_preview_container:
                # Try fetching and rendering HTML FIRST (most reliable)
                rendered_successfully = False
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
                    
                    if response.status_code == 200:
                        # Clean URL by removing placeholder parameters
                        clean_url = str(adv_url)
                        # Remove {clickid}, {click}, and other placeholder parameters
                        clean_url = re.sub(r'[&?]?[\w_]+=\{[^}]+\}', '', clean_url)
                        clean_url = re.sub(r'\{[^}]+\}', '', clean_url)
                        # Remove trailing ? or & if params were removed
                        clean_url = clean_url.rstrip('?&')
                        
                        # Detect redirect/tracking URLs (these won't work in iframe)
                        is_redirect_url = any(keyword in str(adv_url).lower() 
                                            for keyword in ['htrk', 'track', 'redirect', 'aff_c', 'aff_', 'click', 'goto', '/c?', '/aff?'])
                        
                        # If URL was cleaned, use the clean version for rendering
                        render_url = clean_url if clean_url != str(adv_url) else adv_url
                        
                        # Method 1: Try Playwright FIRST (most reliable)
                        if not rendered_successfully and playwright_available:
                            try:
                                with st.spinner("🔄 Trying browser automation..."):
                                    page_html = capture_with_playwright(render_url, device=device_all)
                                    if page_html:
                                        if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                            # Screenshot API was used
                                            preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                            preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                            # Use proportional height from renderer
                                            st.components.v1.html(preview_html, height=height, scrolling=True)
                                            st.caption("📸 Screenshot")
                                            rendered_successfully = True
                                        else:
                                            # Full HTML from Playwright
                                            preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                            preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                            # Use proportional height from renderer
                                            st.components.v1.html(preview_html, height=height, scrolling=True)
                                            st.caption("🤖 Browser")
                                            rendered_successfully = True
                            except:
                                pass
                        
                        # Method 2: If Playwright unavailable/failed, try HTML rendering first (more reliable than iframe)
                        if not rendered_successfully and not is_redirect_url:
                            try:
                                page_html = decode_with_multiple_encodings(response)
                                page_html = clean_and_prepare_html(page_html, render_url)
                                preview_html, display_height = render_html_with_proper_encoding(
                                    page_html, device_all, 'landing_html', adv_url, current_flow, scrolling=True
                                )
                                st.components.v1.html(preview_html, height=display_height, scrolling=True)
                                st.caption("📄 HTML")
                                rendered_successfully = True
                            except:
                                pass
                        
                        # Method 3: Try iframe as fallback (may be blocked by X-Frame-Options)
                        if not rendered_successfully and not is_redirect_url:
                            try:
                                preview_html, height, _ = render_mini_device_preview(render_url, is_url=True, device=device_all, display_url=render_url)
                                preview_html = inject_unique_id(preview_html, 'landing_iframe', render_url, device_all, current_flow)
                                # Use proportional height
                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                st.caption("📺 Iframe (may be blocked by site)")
                                rendered_successfully = True
                            except:
                                pass
                        
                        # For redirect URLs that still haven't rendered, try fetching with cleaned URL
                        if not rendered_successfully and is_redirect_url:
                            try:
                                # Try fetching the cleaned URL directly
                                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                                clean_response = requests.get(render_url, timeout=15, headers=headers, allow_redirects=True)
                                
                                if clean_response.status_code == 200:
                                    # Successfully got HTML, try rendering it
                                    page_html = decode_with_multiple_encodings(clean_response)
                                    page_html = clean_and_prepare_html(page_html, render_url)
                                    preview_html, display_height = render_html_with_proper_encoding(
                                        page_html, device_all, 'landing_html_cleaned', render_url, current_flow, scrolling=True
                                    )
                                    st.components.v1.html(preview_html, height=display_height, scrolling=True)
                                    st.caption("📄 HTML (cleaned URL)")
                                    rendered_successfully = True
                            except:
                                pass
                            
                            # If still not rendered, show message in device preview
                            if not rendered_successfully:
                                message_html = f"""
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <meta charset="UTF-8">
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <style>
                                        body {{
                                            margin: 0;
                                            padding: 20px;
                                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                                            background: #f8fafc;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            min-height: 100vh;
                                        }}
                                        .container {{
                                            text-align: center;
                                            padding: 32px;
                                            background: white;
                                            border-radius: 16px;
                                            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                                            max-width: 340px;
                                        }}
                                        .icon {{
                                            font-size: 64px;
                                            margin-bottom: 16px;
                                        }}
                                        h2 {{
                                            color: #0f172a;
                                            font-size: 20px;
                                            margin: 0 0 12px 0;
                                            font-weight: 700;
                                        }}
                                        p {{
                                            color: #64748b;
                                            font-size: 14px;
                                            line-height: 1.6;
                                            margin: 0 0 20px 0;
                                        }}
                                        .url {{
                                            background: #f1f5f9;
                                            padding: 8px 12px;
                                            border-radius: 6px;
                                            font-size: 11px;
                                            color: #475569;
                                            word-break: break-all;
                                            margin-bottom: 20px;
                                        }}
                                        .button {{
                                            display: inline-block;
                                            background: #3b82f6;
                                            color: white;
                                            padding: 12px 24px;
                                            border-radius: 8px;
                                            text-decoration: none;
                                            font-weight: 600;
                                            font-size: 14px;
                                            transition: background 0.2s;
                                        }}
                                        .button:hover {{
                                            background: #2563eb;
                                        }}
                                    </style>
                                </head>
                                <body>
                                    <div class="container">
                                        <div class="icon">🔄</div>
                                        <h2>Redirect URL</h2>
                                        <p>This tracking URL requires browser automation to display properly.</p>
                                        <div class="url">{html.escape(str(adv_url)[:80])}...</div>
                                        <a href="{adv_url}" target="_blank" class="button">🔗 Open Page</a>
                                    </div>
                                </body>
                                </html>
                                """
                                
                                preview_html, height, _ = render_mini_device_preview(message_html, is_url=False, device=device_all)
                                preview_html = inject_unique_id(preview_html, 'landing_message', adv_url, device_all, current_flow)
                                # Use proportional height
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                st.caption("💡 Redirect URL - Browser automation required")
                                rendered_successfully = True
                    
                    elif response.status_code == 403:
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(adv_url, device=device_all)
                                        if page_html:
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_screenshot_fallback', adv_url, device_all, current_flow)
                                                # Use proportional height
                                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                # Use proportional height
                                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                                st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    # Show error in device preview
                                    error_html = f"""
                                    <!DOCTYPE html>
                                    <html>
                                    <head>
                                        <meta charset="UTF-8">
                                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                        <style>
                                            body {{
                                                margin: 0;
                                                padding: clamp(1rem, 2vw, 1.5rem);
                                                font-family: system-ui, -apple-system, sans-serif;
                                                background: #f8fafc;
                                                display: flex;
                                                align-items: center;
                                                justify-content: center;
                                                min-height: 100vh;
                                            }}
                                            .container {{
                                                text-align: center;
                                                padding: clamp(1.5rem, 3vw, 2rem);
                                                background: white;
                                                border-radius: clamp(0.75rem, 1.5vw, 1rem);
                                                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                                                max-width: 90%;
                                            }}
                                            .icon {{ font-size: clamp(2.5rem, 5vw, 3.5rem); margin-bottom: clamp(0.75rem, 1.5vw, 1rem); }}
                                            h2 {{ color: #dc2626; font-size: clamp(1rem, 2vw, 1.25rem); margin: 0 0 clamp(0.5rem, 1vw, 0.75rem) 0; font-weight: 700; }}
                                            .url {{ background: #f1f5f9; padding: clamp(0.5rem, 1vw, 0.75rem); border-radius: clamp(0.375rem, 0.75vw, 0.5rem); font-size: clamp(0.625rem, 1.2vw, 0.75rem); color: #475569; word-break: break-all; margin-top: clamp(0.75rem, 1.5vw, 1rem); }}
                                        </style>
                                    </head>
                                    <body>
                                        <div class="container">
                                            <div class="icon">🚫</div>
                                            <h2>Could not load page</h2>
                                            <div class="url">{html.escape(str(adv_url))}</div>
                                        </div>
                                    </body>
                                    </html>
                                    """
                                    preview_html, height, _ = render_mini_device_preview(error_html, is_url=False, device=device_all)
                                    preview_html = inject_unique_id(preview_html, 'landing_error', adv_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=False)
                            else:
                                # Show error in device preview
                                error_html = f"""
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <meta charset="UTF-8">
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <style>
                                        body {{
                                            margin: 0;
                                            padding: clamp(1rem, 2vw, 1.5rem);
                                            font-family: system-ui, -apple-system, sans-serif;
                                            background: #f8fafc;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            min-height: 100vh;
                                        }}
                                        .container {{
                                            text-align: center;
                                            padding: clamp(1.5rem, 3vw, 2rem);
                                            background: white;
                                            border-radius: clamp(0.75rem, 1.5vw, 1rem);
                                            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                                            max-width: 90%;
                                        }}
                                        .icon {{ font-size: clamp(2.5rem, 5vw, 3.5rem); margin-bottom: clamp(0.75rem, 1.5vw, 1rem); }}
                                        h2 {{ color: #dc2626; font-size: clamp(1rem, 2vw, 1.25rem); margin: 0 0 clamp(0.5rem, 1vw, 0.75rem) 0; font-weight: 700; }}
                                        .url {{ background: #f1f5f9; padding: clamp(0.5rem, 1vw, 0.75rem); border-radius: clamp(0.375rem, 0.75vw, 0.5rem); font-size: clamp(0.625rem, 1.2vw, 0.75rem); color: #475569; word-break: break-all; margin-top: clamp(0.75rem, 1.5vw, 1rem); }}
                                    </style>
                                </head>
                                <body>
                                    <div class="container">
                                        <div class="icon">🚫</div>
                                        <h2>Could not load page</h2>
                                        <div class="url">{html.escape(str(adv_url))}</div>
                                    </div>
                                </body>
                                </html>
                                """
                                preview_html, height, _ = render_mini_device_preview(error_html, is_url=False, device=device_all)
                                preview_html = inject_unique_id(preview_html, 'landing_error', adv_url, device_all, current_flow)
                                st.components.v1.html(preview_html, height=height, scrolling=False)
                    
                    else:
                        # Other status codes - try Playwright or iframe
                        if not rendered_successfully:
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(adv_url, device=device_all)
                                        if page_html:
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_screenshot_fallback', adv_url, device_all, current_flow)
                                                # Use proportional height from renderer
                                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                                if st.session_state.flow_layout != 'horizontal':
                                                    st.caption("📸 Screenshot (ScreenshotOne API)")
                                                rendered_successfully = True
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                # Use proportional height from renderer
                                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                                if st.session_state.flow_layout != 'horizontal':
                                                    st.caption("🤖 Rendered via browser automation")
                                                rendered_successfully = True
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    st.error(f"❌ HTTP {response.status_code}")
                            else:
                                st.error(f"❌ HTTP {response.status_code}")
                
                except Exception as e:
                    # If HTML fetch completely failed, try iframe as last resort
                    if not rendered_successfully:
                        try:
                            preview_html, height, _ = render_mini_device_preview(adv_url, is_url=True, device=device_all, display_url=adv_url)
                            preview_html = inject_unique_id(preview_html, 'landing_iframe_fallback', adv_url, device_all, current_flow)
                            display_height = 650
                            st.components.v1.html(preview_html, height=display_height, scrolling=True)
                            st.caption("📺 Iframe (HTML fetch failed)")
                            rendered_successfully = True
                        except:
                            st.error(f"❌ Could not load page: {str(e)[:100]}")
        else:
            with landing_preview_container:
                st.warning("No landing page URL")
        
        if st.session_state.flow_layout == 'vertical' and landing_card_right:
            with landing_card_right:
                adv_url = current_flow.get('Destination_Url', '')
                
                st.markdown("<h4 style='font-size: 20px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0;'><strong>🎯 Landing Page Details</strong></h4>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 6px; font-size: 14px;">
                    {f'<div><strong style="color: #0f172a; font-size: 16px;">Landing Page URL:</strong> <a href="{adv_url}" style="color: #3b82f6; text-decoration: none; font-size: 14px;">{html.escape(str(adv_url))}</a></div>' if adv_url and pd.notna(adv_url) else ''}
                </div>
                """, unsafe_allow_html=True)
                
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if api_key:
                        st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                if 'similarities' in st.session_state and st.session_state.similarities:
                    st.markdown("<div style='margin-top: clamp(0.25rem, 0.3vw, 0.375rem);'></div>", unsafe_allow_html=True)
                    render_similarity_score('kwd_to_page', st.session_state.similarities,
                                           custom_title="Keyword → Landing Page Similarity",
                                           tooltip_text="Measures end-to-end flow quality. 70%+ = Good Match (keyword intent matches page content), 40-69% = Fair Match (some relevance), <40% = Poor Match (poor user experience)")
        
        # Close wrapper div for horizontal layout - show Landing Page URL below preview
        if st.session_state.flow_layout == 'horizontal':
            adv_url = current_flow.get('Destination_Url', '') or current_flow.get('reporting_destination_url', '')
            st.markdown(f"""
            <div style='margin-top: 8px; font-size: 14px;'>
                {f'<div><strong style="color: #0f172a; font-size: 16px;">Landing Page URL:</strong> <a href="{adv_url}" style="color: #3b82f6; text-decoration: none; font-size: 14px;">{html.escape(str(adv_url))}</a></div>' if adv_url and pd.notna(adv_url) else ''}
            </div>
            """, unsafe_allow_html=True)
    
    # Similarity Scores Section for Horizontal Layout
    if st.session_state.flow_layout == 'horizontal':
        # Big bold heading for similarity scores - RESPONSIVE
        st.markdown("""
            <div style="font-size: clamp(1.75rem, 1.5rem + 1.25vw, 2rem); font-weight: 900; color: #0f172a; margin: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; padding: 0; line-height: 1.2; display: block;">
                <strong>🧠 Similarity Scores</strong>
            </div>
        """, unsafe_allow_html=True)
        
        # Calculate similarities if not already calculated
        if 'similarities' not in st.session_state or st.session_state.similarities is None:
            if api_key:
                with st.spinner("Calculating similarity scores..."):
                    st.session_state.similarities = calculate_similarities(current_flow)
            else:
                st.session_state.similarities = {}
        
        # Show all 3 similarity scores in one row for horizontal mode
        if 'similarities' in st.session_state and st.session_state.similarities:
            sim_col1, sim_col2, sim_col3 = st.columns(3)
            
            with sim_col1:
                render_similarity_score('kwd_to_ad', st.session_state.similarities,
                                       custom_title="Keyword → Ad Copy Similarity",
                                       tooltip_text="Measures keyword-ad alignment. 70%+ = Good Match (keywords clearly in ad copy), 40-69% = Fair Match (topic relevance present), <40% = Poor Match (weak/no connection)",
                                       max_height=1040)
            
            with sim_col2:
                render_similarity_score('ad_to_page', st.session_state.similarities,
                                       custom_title="Ad Copy → Landing Page Similarity",
                                       tooltip_text="Measures ad-to-page consistency. 70%+ = Good Match (page delivers on ad promises), 40-69% = Fair Match (partial fulfillment), <40% = Poor Match (misleading ad copy)",
                                       max_height=320)
            
            with sim_col3:
                render_similarity_score('kwd_to_page', st.session_state.similarities,
                                       custom_title="Keyword → Landing Page Similarity",
                                       tooltip_text="Measures end-to-end flow quality. 70%+ = Good Match (keyword intent matches page content), 40-69% = Fair Match (some relevance), <40% = Poor Match (poor user experience)",
                                       max_height=320)
        
        # Remove bottom padding after similarity scores (end of page)
        st.markdown("""
        <style>
        /* Remove excess padding at page bottom */
        .main .block-container {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
            min-height: calc(100vh - 6rem) !important;
            max-height: calc(100vh - 3rem) !important;
        }
        .element-container:last-child {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        section[data-testid="stSidebar"] + div {
            padding-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Apply bottom padding fix globally (for all layouts)
    st.markdown("""
    <style>
    /* Global fix: Remove excess bottom padding everywhere */
    .main .block-container {
        padding-bottom: 0 !important;
        padding-top: 2rem !important;
        min-height: calc(100vh - 6rem) !important;
        max-height: 100vh !important;
    }
    .stMarkdown:last-child, .element-container:last-child {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] > div:last-child {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }
    /* Reduce table bottom margin */
    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        margin-bottom: 0.5rem !important;
    }
    /* Force page to fit viewport */
    .main {
        overflow-y: auto !important;
        height: 100vh !important;
    }
    </style>
    """, unsafe_allow_html=True)
