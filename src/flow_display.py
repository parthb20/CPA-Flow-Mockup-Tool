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
from src.screenshot import get_screenshot_url, capture_with_playwright, clean_url_for_capture
from src.serp import generate_serp_mockup
from src.similarity import calculate_similarities
from src.creative_renderer import render_creative_from_adcode, parse_keyword_array_from_flow
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
    
    # Determine orientation based on DEVICE TYPE, not layout
    # Laptop = always landscape (wide), Mobile/Tablet = portrait (tall)
    if device == 'laptop':
        orientation = 'horizontal'  # Laptop is always wide/landscape
    else:
        orientation = 'vertical'  # Mobile/Tablet are portrait/tall
    
    # Use standard renderer with use_srcdoc for proper device preview
    preview_html, height, _ = render_mini_device_preview(
        page_html, 
        is_url=False, 
        device=device, 
        use_srcdoc=True,
        orientation=orientation
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
        # Add CSS for navigation buttons - NO PADDING ON RIGHT
        st.markdown("""
        <style>
        button[key="nav_prev_btn"] {
            padding: 0.25rem 0.5rem !important;
            font-size: 1.1rem !important;
            min-height: 2rem !important;
            height: 2rem !important;
            background: white !important;
            border: 2px solid #cbd5e1 !important;
            border-radius: 0.375rem !important;
        }
        button[key="nav_next_btn"] {
            padding: 0 !important;
            font-size: 1.1rem !important;
            min-height: 2rem !important;
            height: 2rem !important;
            background: transparent !important;
            border: none !important;
        }
        button[key="nav_prev_btn"]:hover {
            background: #f1f5f9 !important;
            border-color: #94a3b8 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        prev_disabled = current_flow_index == 0
        next_disabled = current_flow_index >= len(all_flows) - 1
        
        # Create clickable navigation with proper Streamlit rerun - COMPACT
        nav_col1, nav_col2, nav_col3 = st.columns([0.3, 1.5, 0.3])
        
        with nav_col1:
            if not prev_disabled:
                if st.button("⬅️", key='nav_prev_btn', help="Previous flow"):
                    st.session_state.current_flow_index = max(0, current_flow_index - 1)
                    st.session_state.current_flow = all_flows[st.session_state.current_flow_index].copy()
                    st.rerun()
            else:
                st.markdown('<span style="opacity: 0.3; font-size: 1.1rem; cursor: not-allowed;">⬅️</span>', unsafe_allow_html=True)
        
        with nav_col2:
            st.markdown(f'<div style="text-align: center; padding-top: 0.3rem;"><span style="font-size: 0.85rem; color: #0f172a; font-weight: 700;">Flow {current_flow_index + 1} of {len(all_flows)}</span></div>', unsafe_allow_html=True)
        
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
        
        # Initialize device selection in session state if not present
        if 'selected_device' not in st.session_state:
            st.session_state.selected_device = 'Mobile'
        
        # Get current index based on session state
        device_options = ['Mobile', 'Tablet', 'Laptop']
        current_index = device_options.index(st.session_state.selected_device) if st.session_state.selected_device in device_options else 0
        
        device_choice = st.selectbox("Device", device_options, 
                                    index=current_index, key='device_dropdown', label_visibility="collapsed")
        
        # Update session state ONLY if changed to trigger rerun
        if device_choice != st.session_state.selected_device:
            st.session_state.selected_device = device_choice
            st.rerun()
        
        # Extract actual device name from current session state
        device_all = st.session_state.selected_device.lower()
    
    with control_col4:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Domain</p>', unsafe_allow_html=True)
        
        # Check if publisher_id column exists
        pub_id_col = None
        for col in campaign_df.columns:
            if col.lower() in ['publisher_id', 'publisherid', 'pub_id']:
                pub_id_col = col
                break
        
        # Create domain display with format: "domain - [id]" if ID exists
        if 'publisher_domain' in campaign_df.columns:
            if pub_id_col:
                # Create "domain - [id]" format
                df_domains = campaign_df[['publisher_domain', pub_id_col]].drop_duplicates().dropna()
                domain_display = df_domains.apply(lambda row: f"{row['publisher_domain']} - [{row[pub_id_col]}]", axis=1).tolist()
                domains = ['All Domains'] + sorted(domain_display)
            else:
                # Just domain names
                domains = ['All Domains'] + sorted(campaign_df['publisher_domain'].dropna().unique().tolist())
        else:
            domains = ['All Domains']
        
        # Initialize domain selection in session state
        if 'selected_domain' not in st.session_state:
            st.session_state.selected_domain = 'All Domains'
        
        # Get current index
        domain_index = domains.index(st.session_state.selected_domain) if st.session_state.selected_domain in domains else 0
        
        selected_domain_inline = st.selectbox("Domain", domains, index=domain_index, key='domain_dropdown', label_visibility="collapsed")
        
        # Update session state if changed
        if selected_domain_inline != st.session_state.selected_domain:
            st.session_state.selected_domain = selected_domain_inline
        
        if selected_domain_inline != 'All Domains':
            # Extract domain name from "domain - [id]" format if ID column exists
            if pub_id_col and ' - [' in selected_domain_inline:
                selected_domain_name = selected_domain_inline.split(' - [')[0]
            else:
                selected_domain_name = selected_domain_inline
            campaign_df = campaign_df[campaign_df['publisher_domain'] == selected_domain_name]
    
    with control_col5:
        st.markdown('<p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); font-weight: 900; color: #0f172a; margin: 0 0 clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0; font-family: system-ui;">Keyword</p>', unsafe_allow_html=True)
        keywords = ['All Keywords'] + sorted(campaign_df['keyword_term'].dropna().unique().tolist()) if 'keyword_term' in campaign_df.columns else ['All Keywords']
        
        # Initialize keyword selection in session state
        if 'selected_keyword' not in st.session_state:
            st.session_state.selected_keyword = 'All Keywords'
        
        # Get current index
        keyword_index = keywords.index(st.session_state.selected_keyword) if st.session_state.selected_keyword in keywords else 0
        
        selected_keyword_inline = st.selectbox("Keyword", keywords, index=keyword_index, key='keyword_dropdown', label_visibility="collapsed")
        
        # Update session state if changed
        if selected_keyword_inline != st.session_state.selected_keyword:
            st.session_state.selected_keyword = selected_keyword_inline
        
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
    
    # Display flow stats below filters and above cards
    if current_flow:
        impressions = current_flow.get('impressions', 0)
        clicks = current_flow.get('clicks', 0)
        conversions = current_flow.get('conversions', 0)
        
        st.markdown(f"""
        <div style="text-align: left; padding: 0.75rem 1rem; margin: 0.5rem 0; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
            <span style="font-size: 0.875rem; color: #64748b; font-weight: 700; margin-right: 2rem;">
                📊 <strong style="font-weight: 900;">Impressions:</strong> <strong style="color: #0f172a; font-size: 1rem; font-weight: 600;">{impressions:,}</strong>
            </span>
            <span style="font-size: 0.875rem; color: #64748b; font-weight: 700; margin-right: 2rem;">
                🖱️ <strong style="font-weight: 900;">Clicks:</strong> <strong style="color: #0f172a; font-size: 1rem; font-weight: 600;">{clicks:,}</strong>
            </span>
            <span style="font-size: 0.875rem; color: #64748b; font-weight: 700;">
                ✅ <strong style="font-weight: 900;">Conversions:</strong> <strong style="color: #0f172a; font-size: 1rem; font-weight: 600;">{conversions:,}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)
    
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
                with st.spinner("📰 Loading Publisher URL..."):
                    rendered = False
                
                    # Method 1: Try HTML FIRST (most reliable, avoids iframe X-Frame-Options issues)
                    try:
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
                            page_html = decode_with_multiple_encodings(response)
                            page_html = clean_and_prepare_html(page_html, pub_url)
                            
                            preview_html, display_height = render_html_with_proper_encoding(
                                page_html, device_all, 'pub_html', pub_url, current_flow, scrolling=False
                            )
                            st.components.v1.html(preview_html, height=display_height, scrolling=True)
                            st.caption("📄 HTML")
                            rendered = True
                    except:
                        pass
                    
                    # Method 2: Try Playwright (if HTML failed and Playwright available)
                    if not rendered and playwright_available:
                        try:
                            page_html = capture_with_playwright(pub_url, device=device_all)
                            if page_html:
                                # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                                orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                                if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all, orientation=orientation)
                                    preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=True)
                                    st.caption("📸 Screenshot (API)")
                                else:
                                    preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all, orientation=orientation)
                                    preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=True)
                                    st.caption("🤖 Playwright")
                                rendered = True
                        except:
                            pass
                    
                    # Method 3: Try Screenshot API (last resort)
                    if not rendered:
                        screenshot_url = get_screenshot_url(pub_url, device=device_all, try_cleaned=True)
                        if screenshot_url:
                            try:
                                screenshot_html = f'<img src="{screenshot_url}" style="width:100%;height:auto;" />'
                                preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                preview_html = inject_unique_id(preview_html, 'pub_screenshot_api', pub_url, device_all, current_flow)
                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                rendered = True
                            except:
                                pass
                    
                    # Method 4: Last resort - show error
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
        creative_size = current_flow.get('creative_size', 'N/A')  # Exact column name from File X
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
            with st.spinner("🎨 Loading Creative..."):
                # Render creative from Response.adcode column in File X
                creative_rendered = False
                
                # DEBUG: Check current_flow
                st.write(f"🔍 DEBUG: current_flow type: {type(current_flow)}, is None: {current_flow is None}")
                if current_flow is not None:
                    st.write(f"🔍 DEBUG: current_flow length: {len(current_flow)}")
                    st.write(f"🔍 DEBUG: creative_id in flow: {current_flow.get('creative_id', 'NOT FOUND')}")
                
                # Check if we have File X data
                has_data = current_flow is not None and len(current_flow) > 0
                
                if has_data:
                    try:
                        # DEBUG: Show available columns
                        debug_cols = [c for c in current_flow.keys() if 'response' in c.lower() or 'code' in c.lower() or 'script' in c.lower()]
                        if debug_cols:
                            st.info(f"🔍 Found columns: {', '.join(debug_cols[:5])}")
                        
                        # Get ad code from Response.adcode column (exact name from File X)
                        adcode_raw = current_flow.get('Response.adcode', None)
                        
                        # DEBUG: Show what we got
                        if adcode_raw:
                            st.success(f"✅ Found Response.adcode: {str(adcode_raw)[:100]}...")
                        else:
                            st.warning(f"⚠️ Response.adcode is empty. Trying fallback...")
                        
                        if not adcode_raw or pd.isna(adcode_raw):
                            # Fallback: search for <script tag in any column
                            for key, value in current_flow.items():
                                if pd.notna(value) and isinstance(value, str) and '<script' in str(value).lower():
                                    adcode_raw = value
                                    st.success(f"✅ Found ad code in column: '{key}'")
                                    break
                        
                        if adcode_raw and pd.notna(adcode_raw):
                            st.info(f"🎯 Calling render_creative_from_adcode with size: {creative_size}")
                            
                            # Render directly from Response.adcode
                            rendered_html, error_msg = render_creative_from_adcode(
                                adcode_raw=adcode_raw,
                                creative_size=creative_size
                            )
                            
                            st.write(f"🔍 render_creative_from_adcode returned:")
                            st.write(f"  - rendered_html is None: {rendered_html is None}")
                            st.write(f"  - error_msg: {error_msg}")
                            
                            if rendered_html:
                                st.success(f"✅ Got rendered HTML ({len(rendered_html)} chars), displaying...")
                                # Display creative directly - NO device frame for creatives
                                # Use height based on creative_size
                                try:
                                    _, height_str = creative_size.split('x')
                                    display_height = int(height_str) + 50  # Add padding
                                except:
                                    display_height = 300
                                
                                st.components.v1.html(rendered_html, height=display_height, scrolling=True)
                                creative_rendered = True
                            elif error_msg:
                                st.error(f"❌ {error_msg}")
                        else:
                            st.error(f"❌ No Response.adcode found for creative {creative_id}")
                    except Exception as e:
                        st.error(f"⚠️ Creative error: {str(e)[:200]}")
                else:
                    st.error(f"❌ Creative data not found for {creative_id} ({creative_size})")
                
                # Fallback: Try old response column if Response.adcode failed
                if not creative_rendered:
                    response_value = current_flow.get('response', None)
                    if response_value and pd.notna(response_value) and str(response_value).strip():
                        try:
                            # Legacy fallback - render old response format
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
        
        # Show creative details - DIFFERENT LAYOUT for horizontal vs vertical
        creative_size = current_flow.get('creative_size', 'N/A')  # Exact column name from File X
        creative_name = current_flow.get('creative_template_name', 'N/A')
        keyword = current_flow.get('keyword_term', 'N/A')
        
        if st.session_state.flow_layout == 'horizontal':
            # HORIZONTAL: Show compact info BELOW preview (like Publisher card)
            st.markdown(f"""
            <div style='margin-top: 8px; font-size: 14px;'>
                <div style='font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;'><strong>Keyword:</strong></div>
                <div style='color: #64748b; font-size: 13px; margin-bottom: 6px;'>{html.escape(str(keyword))}</div>
                <div style='font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;'><strong>Creative ID:</strong></div>
                <div style='color: #64748b; font-size: 13px; margin-bottom: 6px;'>{creative_id}</div>
                <div style='font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;'><strong>Size:</strong></div>
                <div style='color: #64748b; font-size: 13px; margin-bottom: 6px;'>{creative_size}</div>
                <div style='font-weight: 900; color: #0f172a; font-size: 16px; margin-bottom: 2px;'><strong>Template:</strong></div>
                <div style='color: #64748b; font-size: 13px;'>{creative_name}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # VERTICAL: Show in right column
            if creative_card_right:
                details_container = creative_card_right
            else:
                details_container = stage_2_container
                
            with details_container:
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
        
        # Add Keyword → Ad similarity for VERTICAL layout only
        if st.session_state.flow_layout == 'vertical':
            if creative_card_right:
                with creative_card_right:
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
                with st.spinner("🔍 Loading SERP..."):
                    # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                    orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                    preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True, orientation=orientation)
                    preview_html = inject_unique_id(preview_html, 'serp_template', serp_url or '', device_all, current_flow)
                    display_height = height
                    st.components.v1.html(preview_html, height=display_height, scrolling=True)
                    if st.session_state.flow_layout != 'horizontal':
                        st.caption("📺 SERP (from template)")
        
        elif serp_url:
            with serp_preview_container:
                with st.spinner("🔍 Loading SERP..."):
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
                        
                            # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                            orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                            preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True, orientation=orientation)
                            preview_html = inject_unique_id(preview_html, 'serp_injected', serp_url, device_all, current_flow)
                            display_height = height
                            st.components.v1.html(preview_html, height=display_height, scrolling=True)
                            if st.session_state.flow_layout != 'horizontal':
                                st.caption("📺 SERP with injected ad content")
                    
                        elif response.status_code == 403:
                            if playwright_available:
                                with st.spinner("🔄 Using browser automation..."):
                                    page_html = capture_with_playwright(serp_url, device=device_all)
                                    if page_html and '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                        # Screenshot API was used
                                        # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                                        orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all, orientation=orientation)
                                        preview_html = inject_unique_id(preview_html, 'serp_screenshot', serp_url, device_all, current_flow)
                                        st.components.v1.html(preview_html, height=height, scrolling=True)
                                        if st.session_state.flow_layout != 'horizontal':
                                            st.caption("📸 SERP (Screenshot API)")
                                    elif page_html:
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
                                    
                                        # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                                        orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                                        preview_html, height, _ = render_mini_device_preview(serp_html, is_url=False, device=device_all, use_srcdoc=True, orientation=orientation)
                                        preview_html = inject_unique_id(preview_html, 'serp_playwright', serp_url, device_all, current_flow)
                                        display_height = height
                                        st.components.v1.html(preview_html, height=display_height, scrolling=True)
                                        if st.session_state.flow_layout != 'horizontal':
                                            st.caption("📺 SERP (via Playwright)")
                                    else:
                                        # Try screenshot API directly (as fallback after Playwright 403, try cleaned)
                                        screenshot_url = get_screenshot_url(serp_url, device=device_all, try_cleaned=True)
                                        if screenshot_url:
                                            screenshot_html = f'<img src="{screenshot_url}" style="width:100%;height:auto;" />'
                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                            preview_html = inject_unique_id(preview_html, 'serp_screenshot_direct', serp_url, device_all, current_flow)
                                            st.components.v1.html(preview_html, height=height, scrolling=True)
                                            if st.session_state.flow_layout != 'horizontal':
                                                st.caption("📸 SERP (Screenshot API)")
                                        else:
                                            st.warning("⚠️ Could not load SERP. Set SCREENSHOT_API_KEY in secrets")
                            else:
                                # Playwright not available - try screenshot API
                                screenshot_url = get_screenshot_url(serp_url, device=device_all)
                                if screenshot_url:
                                    screenshot_html = f'<img src="{screenshot_url}" style="width:100%;height:auto;" />'
                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                    preview_html = inject_unique_id(preview_html, 'serp_screenshot_noplaywright', serp_url, device_all, current_flow)
                                    st.components.v1.html(preview_html, height=height, scrolling=True)
                                    if st.session_state.flow_layout != 'horizontal':
                                        st.caption("📸 SERP (Screenshot API)")
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
        
            landing_preview_container = landing_card_left if st.session_state.flow_layout == 'vertical' and landing_card_left else stage_4_container
        
            if adv_url and pd.notna(adv_url) and str(adv_url).strip():
                with landing_preview_container:
                    with st.spinner("🏠 Loading Landing Page..."):
                        rendered_successfully = False
                    
                        # PRIORITY 1: Try Playwright FIRST (best anti-detection, bypasses most 403s)
                        if playwright_available:
                            try:
                                page_html = capture_with_playwright(adv_url, device=device_all)
                                if page_html:
                                    # Orientation based on device type: laptop=landscape, mobile/tablet=portrait
                                    orientation = 'horizontal' if device_all == 'laptop' else 'vertical'
                                    if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all, orientation=orientation)
                                        preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                        st.components.v1.html(preview_html, height=height, scrolling=True)
                                        st.caption("📸 Screenshot (ScreenshotOne API)")
                                        rendered_successfully = True
                                    else:
                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all, orientation=orientation)
                                        preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                        st.components.v1.html(preview_html, height=height, scrolling=True)
                                        st.caption("🤖 Playwright")
                                        rendered_successfully = True
                            except Exception:
                                pass
                    
                    # PRIORITY 2: If Playwright failed OR unavailable, try Screenshot API as fallback
                    if not rendered_successfully:
                        screenshot_url = get_screenshot_url(adv_url, device=device_all, try_cleaned=True)
                        if screenshot_url:
                            try:
                                screenshot_html = f'<img src="{screenshot_url}" style="width:100%;height:auto;" />'
                                preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all)
                                preview_html = inject_unique_id(preview_html, 'landing_screenshot_fallback', adv_url, device_all, current_flow)
                                st.components.v1.html(preview_html, height=height, scrolling=True)
                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                rendered_successfully = True
                            except Exception:
                                pass
                    
                    # If still not rendered, show error
                    if not rendered_successfully:
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
                        st.components.v1.html(preview_html, height=height, scrolling=True)
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
        
        # Close wrapper div for horizontal layout - show Landing Page URL below preview + DEBUG INFO
        if st.session_state.flow_layout == 'horizontal':
            adv_url = current_flow.get('Destination_Url', '') or current_flow.get('reporting_destination_url', '')
            
            # Calculate cleaned URL for debug
            cleaned_url = clean_url_for_capture(adv_url) if adv_url and pd.notna(adv_url) else None
            
            # Show landing page URL only (clean display, no debug)
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