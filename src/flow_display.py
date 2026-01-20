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

from src.config import SERP_BASE_URL
from src.renderers import (
    render_mini_device_preview,
    render_similarity_score,
    inject_unique_id,
    parse_creative_html
)
from src.screenshot import get_screenshot_url, capture_with_playwright, capture_page_with_fallback
from src.serp import generate_serp_mockup
from src.similarity import calculate_similarities


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
    /* Make dropdowns extra compact */
    div[data-testid="stSelectbox"] > div > div {
        min-height: 36px !important;
        height: 36px !important;
    }
    div[data-testid="stSelectbox"] > div > div > div {
        padding: 6px 10px !important;
        font-size: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # All controls in one row - Layout, Device, Domain, Keyword
    control_col1, control_col2, control_col3, control_col4 = st.columns([1.2, 1.2, 2, 2])
    
    with control_col1:
        st.markdown('<p style="font-size: 13px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;">Layout</p>', unsafe_allow_html=True)
        layout_choice = st.selectbox("", ['↔️ Horizontal', '↕️ Vertical'], 
                                     index=0 if st.session_state.flow_layout == 'horizontal' else 1, 
                                     key='layout_dropdown', label_visibility="collapsed")
        if (layout_choice == '↔️ Horizontal' and st.session_state.flow_layout != 'horizontal') or \
           (layout_choice == '↕️ Vertical' and st.session_state.flow_layout != 'vertical'):
            st.session_state.flow_layout = 'horizontal' if layout_choice == '↔️ Horizontal' else 'vertical'
            st.rerun()
    
    with control_col2:
        st.markdown('<p style="font-size: 13px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;">Device</p>', unsafe_allow_html=True)
        device_all = st.selectbox("", ['📱 Mobile', '📱 Tablet', '💻 Laptop'], 
                                 key='device_all', index=0, label_visibility="collapsed")
        # Extract actual device name
        device_all = device_all.split(' ')[1].lower()
    
    with control_col3:
        st.markdown('<p style="font-size: 13px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;">Domain</p>', unsafe_allow_html=True)
        domains = ['All Domains'] + sorted(campaign_df['publisher_domain'].dropna().unique().tolist()) if 'publisher_domain' in campaign_df.columns else ['All Domains']
        selected_domain_inline = st.selectbox("", domains, key='domain_inline_filter', label_visibility="collapsed")
        if selected_domain_inline != 'All Domains':
            campaign_df = campaign_df[campaign_df['publisher_domain'] == selected_domain_inline]
    
    with control_col4:
        st.markdown('<p style="font-size: 13px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;">Keyword</p>', unsafe_allow_html=True)
        keywords = ['All Keywords'] + sorted(campaign_df['keyword_term'].dropna().unique().tolist()) if 'keyword_term' in campaign_df.columns else ['All Keywords']
        selected_keyword_inline = st.selectbox("", keywords, key='keyword_inline_filter', label_visibility="collapsed")
        if selected_keyword_inline != 'All Keywords':
            campaign_df = campaign_df[campaign_df['keyword_term'] == selected_keyword_inline]
    
    # ZERO GAPS CSS
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
        /* Remove spacing from horizontal block containers */
        .stHorizontalBlock {
            margin: 0 !important;
            padding: 0 !important;
        }
        .stHorizontalBlock > div {
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create columns for the actual cards - NO gap to prevent spacing
        stage_cols = st.columns([1, 0.7, 1, 1], gap='small')
    else:
        # Vertical layout - cards extend full width, details inline within card boundaries
        stage_cols = None
    
    # Stage 1: Publisher URL
    if st.session_state.flow_layout == 'vertical':
        st.markdown("<br>", unsafe_allow_html=True)
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
                st.markdown('<h3 style="font-size: 32px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>📰 Publisher URL</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: 24px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;"><strong>📰 Publisher URL</strong></h3>', unsafe_allow_html=True)
        
        pub_url = current_flow.get('publisher_url', '')
        preview_container = card_col_left if st.session_state.flow_layout == 'vertical' and card_col_left else stage_1_container
        
        if pub_url and pub_url != 'NOT_FOUND' and pd.notna(pub_url) and str(pub_url).strip():
            with preview_container:
                try:
                    user_agents = [
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
                    ]
                    head_response = None
                    for ua in user_agents:
                        try:
                            head_response = requests.head(pub_url, timeout=5, headers={'User-Agent': ua})
                            if head_response.status_code == 200:
                                break
                        except:
                            continue
                    
                    if not head_response:
                        iframe_blocked = False
                    else:
                        x_frame = head_response.headers.get('X-Frame-Options', '').upper()
                        csp = head_response.headers.get('Content-Security-Policy', '')
                        iframe_blocked = ('DENY' in x_frame or 'SAMEORIGIN' in x_frame or 'frame-ancestors' in csp.lower())
                except:
                    iframe_blocked = False
                
                if not iframe_blocked:
                    try:
                        preview_html, height, _ = render_mini_device_preview(pub_url, is_url=True, device=device_all, display_url=pub_url)
                        preview_html = inject_unique_id(preview_html, 'pub_iframe', pub_url, device_all, current_flow)
                        display_height = height
                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                        if st.session_state.flow_layout != 'horizontal':
                            st.caption("📺 Iframe")
                    except:
                        iframe_blocked = True
                
                if iframe_blocked:
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
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(pub_url, device=device_all)
                                        if page_html:
                                            # Check if it's a screenshot fallback
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'pub_screenshot_fallback', pub_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("🤖 Rendered via browser automation")
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    st.warning("🚫 Could not load page")
                                    st.info("💡 Set SCREENSHOT_API_KEY in secrets for screenshot fallback")
                                    st.markdown(f"[🔗 Open in new tab]({pub_url})")
                            else:
                                st.warning("🚫 Could not load page")
                                st.markdown(f"[🔗 Open in new tab]({pub_url})")
                        elif response.status_code == 200:
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
                                display_height = height
                                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                st.caption("📄 HTML")
                            except Exception as html_error:
                                st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                        else:
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(pub_url, device=device_all)
                                        if page_html:
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'pub_screenshot_fallback', pub_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'pub_playwright', pub_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("🤖 Rendered via browser automation")
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    st.error(f"❌ HTTP {response.status_code}")
                            else:
                                st.error(f"❌ HTTP {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:100]}")
        else:
            with preview_container:
                st.warning("⚠️ No valid publisher URL in data")
        
        if st.session_state.flow_layout == 'vertical' and card_col_right:
            with card_col_right:
                # Add spacing at top to push info down and prevent overlap
                st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="margin-bottom: 12px;">
                    <span style="font-weight: 900; color: #0f172a; font-size: 18px;">
                        📰 Publisher URL Details
                        <span title="Similarity scores measure how well different parts of your ad flow match: Keyword → Ad (ad matches keyword), Ad → Page (landing page matches ad), Keyword → Page (overall flow consistency)" style="cursor: help; color: #3b82f6; font-size: 12px; margin-left: 4px;">ℹ️</span>
                    </span>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 12px; font-size: 13px;">
                    <div style="font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>Domain</strong></div>
                    <div style="margin-left: 0; margin-top: 4px; word-break: break-word; color: #64748b; font-size: 12px;">{html.escape(str(current_dom))}</div>
                    {f'<div style="margin-top: 10px; font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>URL</strong></div><div style="margin-left: 0; margin-top: 4px; word-break: break-word; color: #64748b; font-size: 11px;"><a href="{current_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(current_url))}</a></div>' if current_url and pd.notna(current_url) else ''}
                </div>
                """, unsafe_allow_html=True)
        
        # Close wrapper div for horizontal layout
        if st.session_state.flow_layout == 'horizontal':
            # Show info BELOW card preview in horizontal layout - ALWAYS show
            st.markdown(f"""
            <div style='margin-top: 12px; font-size: 13px;'>
                <div style='font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;'><strong>Domain</strong></div>
                <div style='margin-left: 0; margin-top: 4px; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 12px;'>{html.escape(str(current_dom))}</div>
                {f'<div style="margin-top: 10px; font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>URL</strong></div><div style="margin-left: 0; margin-top: 4px; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 11px;"><a href="{current_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(current_url))}</a></div>' if current_url and pd.notna(current_url) else ''}
            </div>
            """, unsafe_allow_html=True)
    
    # Arrow divs removed - no longer needed
    
    # Stage 2: Creative
    if st.session_state.flow_layout == 'vertical':
        st.markdown("<br>", unsafe_allow_html=True)
        stage_2_container = st.container()
        creative_card_left = None
        creative_card_right = None
    else:
        stage_2_container = stage_cols[1]
        creative_card_left = None
        creative_card_right = None
    
    with stage_2_container:
        if st.session_state.flow_layout == 'vertical':
            creative_card_left, creative_card_right = st.columns([0.5, 0.5])
            with creative_card_left:
                st.markdown('<h3 style="font-size: 32px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>🎨 Creative</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: 24px; font-weight: 900; color: #0f172a; margin: 0 0 6px 0; font-family: system-ui;"><strong>🎨 Creative</strong></h3>', unsafe_allow_html=True)
        
        creative_id = current_flow.get('creative_id', 'N/A')
        creative_name = current_flow.get('creative_template_name', 'N/A')
        creative_size = current_flow.get('creative_size', 'N/A')
        keyword = current_flow.get('keyword_term', 'N/A')
        
        # Keyword will be shown BELOW card preview
        
        if st.session_state.flow_layout != 'vertical':
            if st.session_state.view_mode == 'advanced':
                with st.expander("⚙️", expanded=False):
                    st.caption(f"**ID:** {creative_id}")
                    st.caption(f"**Name:** {creative_name}")
                    st.caption(f"**Size:** {creative_size}")
        
        creative_preview_container = creative_card_left if st.session_state.flow_layout == 'vertical' and creative_card_left else stage_2_container
        response_value = current_flow.get('response', None)
        
        with creative_preview_container:
            if response_value and pd.notna(response_value) and str(response_value).strip():
                try:
                    creative_html, raw_adcode = parse_creative_html(response_value)
                    if creative_html and raw_adcode:
                        # Same height for both layouts to match other boxes
                        st.components.v1.html(creative_html, height=600, scrolling=True)
                        
                        if st.session_state.view_mode == 'advanced' or st.session_state.flow_layout == 'vertical':
                            with st.expander("👁️ View Raw Ad Code"):
                                st.code(raw_adcode[:500], language='html')
                    else:
                        st.warning("⚠️ Empty creative JSON")
                except Exception as e:
                    st.error(f"⚠️ Creative error: {str(e)[:100]}")
            else:
                min_height = 600
                st.markdown(f"""
                <div style="min-height: {min_height}px; display: flex; align-items: center; justify-content: center; background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 8px;">
                    <div style="text-align: center; color: #64748b;">
                        <div style="font-size: 48px; margin-bottom: 8px;">⚠️</div>
                        <div style="font-weight: 600; font-size: 14px;">No creative data</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        if st.session_state.flow_layout == 'vertical' and creative_card_right:
            with creative_card_right:
                # Show creative details to the RIGHT
                st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                
                keyword = current_flow.get('keyword_term', 'N/A')
                creative_size = current_flow.get('creative_size', 'N/A')
                creative_name = current_flow.get('creative_template_name', 'N/A')
                
                st.markdown("<h4 style='font-size: 18px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0;'>🎨 Creative Details</h4>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 12px; font-size: 13px;">
                    <div style="font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>Keyword</strong></div>
                    <div style="margin-left: 0; margin-top: 4px; word-break: break-word; color: #64748b; font-size: 12px;">{html.escape(str(keyword))}</div>
                    <div style="margin-top: 10px; font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>Size</strong></div>
                    <div style="margin-left: 0; margin-top: 4px; word-break: break-word; color: #64748b; font-size: 12px;">{html.escape(str(creative_size))}</div>
                </div>
                """, unsafe_allow_html=True)
                
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if api_key:
                        st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                if 'similarities' in st.session_state and st.session_state.similarities:
                    # Show Keyword → Ad similarity
                    render_similarity_score('kwd_to_ad', st.session_state.similarities,
                                           custom_title="Keyword → Ad Copy Similarity",
                                           tooltip_text="Measures how well the ad creative matches the search keyword. Higher scores indicate better keyword-ad alignment.")
        
        # Close wrapper div for horizontal layout
        if st.session_state.flow_layout == 'horizontal':
            # Show keyword BELOW card preview in horizontal layout - ALWAYS show
            keyword = current_flow.get('keyword_term', 'N/A')
            st.markdown(f"""
            <div style='margin-top: 12px; font-size: 13px;'>
                <div style='font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;'><strong>Keyword</strong></div>
                <div style='margin-left: 0; margin-top: 4px; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 12px;'>{html.escape(str(keyword))}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Arrow divs removed - no longer needed
    
    # Stage 3: SERP
    serp_template_key = current_flow.get('serp_template_key', '')
    if serp_template_key and pd.notna(serp_template_key) and str(serp_template_key).strip():
        serp_url = SERP_BASE_URL + str(serp_template_key)
    else:
        serp_url = None
    
    if st.session_state.flow_layout == 'vertical':
        st.markdown("<br>", unsafe_allow_html=True)
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
                st.markdown('<h3 style="font-size: 32px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>📄 SERP</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: 28px; font-weight: 900; color: #0f172a; margin: 0 0 8px 0; font-family: system-ui;"><strong>📄 SERP</strong></h3>', unsafe_allow_html=True)
        
        serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
        serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
        serp_key = current_flow.get('serp_template_key', 'N/A')
        
        # SERP info removed from above card - will be shown BELOW card preview
        
        if st.session_state.flow_layout != 'horizontal':
            st.caption(f"**Template:** {serp_name}")
        
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
                # Add spacing at top
                st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                
                # Show SERP details to the RIGHT - Template AFTER similarity
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if api_key:
                        st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                if 'similarities' in st.session_state and st.session_state.similarities:
                    render_similarity_score('ad_to_page', st.session_state.similarities,
                                           custom_title="Ad Copy → Landing Page Similarity",
                                           tooltip_text="Measures how well the landing page fulfills the promises made in the ad copy. Higher scores indicate better ad-page consistency.")
                
                # NOW show SERP URL below similarity (remove Template line)
                serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
                
                st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
                st.markdown("<h4 style='font-size: 18px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0;'>📄 SERP Details</h4>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 12px; font-size: 13px;">
                    {f'<div style="font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>URL</strong></div><div style="margin-left: 0; margin-top: 4px; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 11px;"><a href="{serp_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(serp_url))}</a></div>' if serp_url and serp_url != 'N/A' else ''}
                </div>
                """, unsafe_allow_html=True)
        
        # Close wrapper div for horizontal layout
        if st.session_state.flow_layout == 'horizontal':
            # Show SERP URL BELOW card preview in horizontal layout (no Template line)
            serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
            st.markdown(f"""
            <div style='margin-top: 12px; font-size: 13px;'>
                {f'<div style="font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>URL</strong></div><div style="margin-left: 0; margin-top: 4px; word-break: break-all; overflow-wrap: anywhere; color: #64748b; font-size: 11px;"><a href="{serp_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(serp_url))}</a></div>' if serp_url and serp_url != 'N/A' else ''}
            </div>
            """, unsafe_allow_html=True)
    
    # Arrow divs removed - no longer needed
    
    # Stage 4: Landing Page
    if st.session_state.flow_layout == 'vertical':
        st.markdown("<br>", unsafe_allow_html=True)
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
                st.markdown('<h3 style="font-size: 32px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0; line-height: 1.2; letter-spacing: -0.5px; font-family: system-ui;"><strong>🎯 Landing Page</strong></h3>', unsafe_allow_html=True)
        else:
            st.markdown('<h3 style="font-size: 28px; font-weight: 900; color: #0f172a; margin: 0 0 8px 0; font-family: system-ui;"><strong>🎯 Landing Page</strong></h3>', unsafe_allow_html=True)
        
        adv_url = current_flow.get('reporting_destination_url', '')
        flow_clicks = current_flow.get('clicks', 0)
        
        # Landing URL will be shown BELOW card preview
        
        # Old code removed
        if False:
            st.markdown(f"""
            <div style="margin-bottom: 8px; font-size: 13px;">
                <div style="font-weight: 700; color: #0f172a; margin-bottom: 4px;"><strong>Landing URL:</strong></div>
                <div style="margin-left: 8px; word-break: break-word;"><a href="{adv_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(adv_url))}</a></div>
            </div>
            """, unsafe_allow_html=True)
        
        landing_preview_container = landing_card_left if st.session_state.flow_layout == 'vertical' and landing_card_left else stage_4_container
        
        if adv_url and pd.notna(adv_url) and str(adv_url).strip():
            with landing_preview_container:
                try:
                    head_response = requests.head(adv_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                    x_frame = head_response.headers.get('X-Frame-Options', '').upper()
                    csp = head_response.headers.get('Content-Security-Policy', '')
                    iframe_blocked = ('DENY' in x_frame or 'SAMEORIGIN' in x_frame or 'frame-ancestors' in csp.lower())
                except:
                    iframe_blocked = False
                
                if not iframe_blocked:
                    try:
                        preview_html, height, _ = render_mini_device_preview(adv_url, is_url=True, device=device_all, display_url=adv_url)
                        preview_html = inject_unique_id(preview_html, 'landing_iframe', adv_url, device_all, current_flow)
                        display_height = height
                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                        st.caption("📺 Iframe")
                    except:
                        iframe_blocked = True
                
                if iframe_blocked:
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
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(adv_url, device=device_all)
                                        if page_html:
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_screenshot_fallback', adv_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("📸 Screenshot (ScreenshotOne API)")
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                st.components.v1.html(preview_html, height=height, scrolling=False)
                                                st.caption("🤖 Rendered via browser automation (bypassed 403)")
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    st.warning("🚫 Could not load page")
                                    st.info("💡 Set SCREENSHOT_API_KEY in secrets for screenshot fallback")
                                    st.markdown(f"[🔗 Open in new tab]({adv_url})")
                            else:
                                st.warning("🚫 Could not load page")
                                st.markdown(f"[🔗 Open landing page]({adv_url})")
                        elif response.status_code == 200:
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
                                display_height = height
                                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                st.caption("📄 HTML")
                            except Exception as html_error:
                                st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                        else:
                            if playwright_available:
                                try:
                                    with st.spinner("🔄 Trying browser automation..."):
                                        page_html = capture_with_playwright(adv_url, device=device_all)
                                        if page_html:
                                            if '<!-- SCREENSHOT_FALLBACK -->' in page_html:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_screenshot_fallback', adv_url, device_all, current_flow)
                                                display_height = height
                                                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                if st.session_state.flow_layout != 'horizontal':
                                                    st.caption("📸 Screenshot (ScreenshotOne API)")
                                            else:
                                                preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                display_height = height
                                                st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                if st.session_state.flow_layout != 'horizontal':
                                                    st.caption("🤖 Rendered via browser automation")
                                        else:
                                            raise Exception("Playwright returned empty HTML")
                                except Exception:
                                    st.error(f"❌ HTTP {response.status_code}")
                            else:
                                st.error(f"❌ HTTP {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:100]}")
        else:
            with landing_preview_container:
                st.warning("No landing page URL")
        
        if st.session_state.flow_layout == 'vertical' and landing_card_right:
            with landing_card_right:
                adv_url = current_flow.get('reporting_destination_url', '')
                
                st.markdown("<h4 style='font-size: 18px; font-weight: 900; color: #0f172a; margin: 0 0 12px 0;'>🎯 Landing Page Details</h4>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="margin-bottom: 12px; font-size: 13px;">
                    {f'<div style="font-weight: 900; color: #0f172a; font-size: 14px; margin-bottom: 4px;"><strong>Landing URL</strong></div><div style="margin-left: 0; margin-top: 4px; word-break: break-word; color: #64748b; font-size: 11px;"><a href="{adv_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{html.escape(str(adv_url))}</a></div>' if adv_url and pd.notna(adv_url) else ''}
                </div>
                """, unsafe_allow_html=True)
                
                if 'similarities' not in st.session_state or st.session_state.similarities is None:
                    if api_key:
                        st.session_state.similarities = calculate_similarities(current_flow)
                    else:
                        st.session_state.similarities = {}
                
                if 'similarities' in st.session_state and st.session_state.similarities:
                    st.markdown("<h4 style='font-size: 18px; font-weight: 700; color: #0f172a; margin: 12px 0 8px 0;'>🔗 Keyword → Landing Page Similarity</h4>", unsafe_allow_html=True)
                    render_similarity_score('kwd_to_page', st.session_state.similarities,
                                           custom_title="Keyword → Landing Page Similarity",
                                           tooltip_text="Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment.")
    
    # Similarity Scores Section for Horizontal Layout
    if st.session_state.flow_layout == 'horizontal':
        # Add MORE spacing before Similarity Scores to prevent overlap
        st.markdown("<div style='margin-top: 40px; margin-bottom: 8px;'></div>", unsafe_allow_html=True)
        st.markdown("""
            <h2 style="font-size: 28px; font-weight: 900; color: #0f172a; margin: 20px 0 15px 0; display: block;">
                🧠 Similarity Scores
            </h2>
        """, unsafe_allow_html=True)
        
        # Calculate similarities if not already calculated
        if 'similarities' not in st.session_state or st.session_state.similarities is None:
            if api_key:
                with st.spinner("Calculating similarity scores..."):
                    st.session_state.similarities = calculate_similarities(current_flow)
            else:
                st.session_state.similarities = {}
        
        # Render similarity scores - check if we have actual valid data (not just error dicts)
        has_similarities = False
        if 'similarities' in st.session_state and st.session_state.similarities:
            similarities = st.session_state.similarities
            if isinstance(similarities, dict) and len(similarities) > 0:
                # Check if we have at least one valid score (not an error)
                for key in ['kwd_to_ad', 'ad_to_page', 'kwd_to_page']:
                    if key in similarities:
                        score_data = similarities[key]
                        if isinstance(score_data, dict) and not score_data.get('error', False) and 'final_score' in score_data:
                            has_similarities = True
                            break
        
        if has_similarities:
            score_cols = st.columns(3, gap='small')
            
            with score_cols[0]:
                render_similarity_score('kwd_to_ad', st.session_state.similarities,
                                       custom_title="Keyword → Ad Copy Similarity",
                                       tooltip_text="Measures how well the ad creative matches the search keyword. Higher scores indicate better keyword-ad alignment.")
            
            with score_cols[1]:
                render_similarity_score('ad_to_page', st.session_state.similarities,
                                       custom_title="Ad Copy → Landing Page Similarity",
                                       tooltip_text="Measures how well the landing page fulfills the promises made in the ad copy. Higher scores indicate better ad-page consistency.")
            
            with score_cols[2]:
                render_similarity_score('kwd_to_page', st.session_state.similarities,
                                       custom_title="Keyword → Landing Page Similarity",
                                       tooltip_text="Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment.")
        else:
            # Show helpful error message
            if api_key:
                if 'similarities' in st.session_state and st.session_state.similarities:
                    similarities = st.session_state.similarities
                    if isinstance(similarities, dict):
                        # Check what's in similarities
                        error_keys = [k for k, v in similarities.items() if isinstance(v, dict) and v.get('error')]
                        valid_keys = [k for k, v in similarities.items() if isinstance(v, dict) and not v.get('error') and 'final_score' in v]
                        if error_keys and not valid_keys:
                            # Show actual error details
                            error_details = []
                            for k in error_keys:
                                err = similarities[k]
                                error_msg = err.get('body', err.get('status_code', 'unknown'))
                                error_details.append(f"**{k}**: {error_msg}")
                            st.error(f"❌ **Similarity calculation failed:**\n\n" + "\n\n".join(error_details))
                        elif valid_keys:
                            st.info(f"⏳ Some similarity scores are still calculating... ({len(valid_keys)}/{len(similarities)} complete)")
                        else:
                            st.info("⏳ Similarity scores are being calculated...")
                    else:
                        st.warning("⚠️ Similarity scores format error.")
                else:
                    st.warning("⚠️ Similarity scores could not be calculated. Check API key configuration.")
            else:
                st.info("⏳ Add API key to calculate similarity scores")