# -*- coding: utf-8 -*-
"""
CPA Flow Analysis Tool - Main Application
Modular architecture for maintainability
"""

import streamlit as st

# Page config - MUST be FIRST Streamlit command (before any imports that use Streamlit)
st.set_page_config(page_title="CPA Flow Analysis v2", page_icon="📊", layout="wide")

import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, urljoin
import re
import html

# Import from modules (after page config)
from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
from src.utils import safe_float, safe_int
from src.flow_analysis import find_default_flow
from src.similarity import calculate_similarities
from src.serp import generate_serp_mockup
from src.renderers import (
    render_mini_device_preview,
    render_similarity_score,
    inject_unique_id,
    create_screenshot_html,
    parse_creative_html
)
from src.screenshot import get_screenshot_url, capture_with_playwright
from src.ui_components import render_flow_combinations_table, render_what_is_flow_section, render_selected_flow_display
from src.filters import render_advanced_filters, apply_flow_filtering
from src.flow_display import render_flow_journey

# Try to import playwright (for 403 bypass)
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
    
    # Note: Browsers should be pre-installed via packages.txt
    # Skip auto-install to prevent blocking app startup
except Exception:
    PLAYWRIGHT_AVAILABLE = False
    # Don't show warning here - it's optional

# Get API keys from secrets - safe access pattern
API_KEY = ""
SCREENSHOT_API_KEY = ""
THUMIO_REFERER_DOMAIN = ""

# Safely access secrets - catch all exceptions
try:
    try:
        API_KEY = str(st.secrets["FASTROUTER_API_KEY"]).strip()
    except Exception:
        try:
            API_KEY = str(st.secrets["OPENAI_API_KEY"]).strip()
        except Exception:
            API_KEY = ""
except Exception:
    API_KEY = ""

try:
    SCREENSHOT_API_KEY = str(st.secrets["SCREENSHOT_API_KEY"]).strip()
except Exception:
    SCREENSHOT_API_KEY = ""

try:
    THUMIO_REFERER_DOMAIN = str(st.secrets["THUMIO_REFERER_DOMAIN"]).strip()
except Exception:
    THUMIO_REFERER_DOMAIN = ""

THUMIO_CONFIGURED = False  # Disabled - Playwright only!

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
    
    /* Global dropdown arrow for all selectboxes */
    .stSelectbox [data-baseweb="select"] {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'%3E%3Cpath fill='%23666' d='M8 11L3 6h10z'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: right 12px center !important;
        padding-right: 40px !important;
    }
    .stSelectbox [data-baseweb="select"] > div {
        background-color: white !important;
    }
    .stSelectbox input {
        background-color: white !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
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

# Session state initialization
for key in ['data_a', 'data_b', 'loading_done', 'default_flow', 'current_flow', 'view_mode', 'flow_layout', 'similarities', 'last_campaign_key']:
    if key not in st.session_state:
        if key == 'view_mode':
            st.session_state[key] = 'basic'
        elif key == 'flow_layout':
            st.session_state[key] = 'horizontal'
        else:
            st.session_state[key] = None

# Main title - BIG and BOLD at top
st.markdown("""
    <div style="margin: 0 0 20px 0; padding: 20px 0 16px 0; border-bottom: 3px solid #e2e8f0;">
        <h1 style="font-size: 64px; font-weight: 900; color: #0f172a; margin: 0; padding: 0; line-height: 1.2; letter-spacing: -1px; font-family: system-ui, -apple-system, sans-serif;">
            📊 <strong>CPA Flow Analysis</strong>
        </h1>
    </div>
""", unsafe_allow_html=True)

# Auto-load from Google Drive (sequential loading for Streamlit Cloud compatibility)
if not st.session_state.loading_done:
    with st.spinner("Loading data..."):
        try:
            # Load CSV first (critical)
            st.session_state.data_a = load_csv_from_gdrive(FILE_A_ID)
            
            # Load JSON second (nice to have)
            st.session_state.data_b = load_json_from_gdrive(FILE_B_ID)
            
            st.session_state.loading_done = True
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            st.session_state.loading_done = True

# No view mode toggle here - moved to flow controls
# Reduce spacing - minimal margin
st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)

if st.session_state.data_a is not None and len(st.session_state.data_a) > 0:
    df = st.session_state.data_a
    
    # Select Advertiser and Campaign - preserve selection when switching views
    col1, col2 = st.columns(2)
    with col1:
        advertisers = ['-- Select Advertiser --'] + sorted(df['Advertiser_Name'].dropna().unique().tolist())
        # Preserve advertiser selection
        default_adv_idx = 0
        if 'preserved_advertiser' in st.session_state and st.session_state.preserved_advertiser in advertisers:
            default_adv_idx = advertisers.index(st.session_state.preserved_advertiser)
        selected_advertiser = st.selectbox("Advertiser", advertisers, index=default_adv_idx)
        if selected_advertiser != '-- Select Advertiser --':
            st.session_state.preserved_advertiser = selected_advertiser
    
    if selected_advertiser and selected_advertiser != '-- Select Advertiser --':
        with col2:
            campaigns = ['-- Select Campaign --'] + sorted(df[df['Advertiser_Name'] == selected_advertiser]['Campaign_Name'].dropna().unique().tolist())
            # Preserve campaign selection
            default_camp_idx = 0
            if 'preserved_campaign' in st.session_state and st.session_state.preserved_campaign in campaigns:
                default_camp_idx = campaigns.index(st.session_state.preserved_campaign)
            selected_campaign = st.selectbox("Campaign", campaigns, key='campaign_selector', index=default_camp_idx)
            if selected_campaign != '-- Select Campaign --':
                st.session_state.preserved_campaign = selected_campaign
        
        # Reset flow when campaign changes - CLEAR ALL OLD DATA IMMEDIATELY
        campaign_key = f"{selected_advertiser}_{selected_campaign}"
        if 'last_campaign_key' not in st.session_state:
            st.session_state.last_campaign_key = None
        
        # Preserve campaign selection when switching views
        if 'preserved_campaign' not in st.session_state:
            st.session_state.preserved_campaign = None
        
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
            
            # Render table using module
            render_flow_combinations_table(campaign_df)
            
            # NO spacing between table and What is Flow
            st.markdown("<div style='margin-top: 0; margin-bottom: 0;'></div>", unsafe_allow_html=True)
            
            # Render "What is Flow" section using module
            render_what_is_flow_section()
            
            # NO spacing before Flow Journey
            st.markdown("<div style='margin: 0; padding: 0;'></div>", unsafe_allow_html=True)
            
            # Find default flow if not set
            if st.session_state.default_flow is None:
                with st.spinner("Finding best performing flow..."):
                    st.session_state.default_flow = find_default_flow(campaign_df)
                    st.session_state.current_flow = st.session_state.default_flow.copy() if st.session_state.default_flow else None
            
            if st.session_state.current_flow:
                current_flow = st.session_state.current_flow
                
                # Advanced mode: Show keyword and domain filters
                if st.session_state.view_mode == 'advanced':
                    # Reduce spacing
                    st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                
                # Render filters and get filter state
                filters_changed, selected_keyword_filter, selected_domain_filter = render_advanced_filters(campaign_df, current_flow)
                
                # Reduce spacing - minimal margin instead of divider
                st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                
                # Apply filtering logic using module
                current_flow, final_filtered = apply_flow_filtering(
                    campaign_df, current_flow, filters_changed, selected_keyword_filter, selected_domain_filter
                )
                
                # Update session state
                st.session_state.current_flow = current_flow
                
                # Show selected flow details using module
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
                else:
                    single_view = None
                
                # No extra spacing needed
                pass
                
                # Add Flow Journey title with explanation - ZERO GAPS
                st.markdown("""
                <h2 style="font-size: 52px; font-weight: 900; color: #0f172a; margin: 0; padding: 0; line-height: 1.2; letter-spacing: -1px; font-family: system-ui;">
                    <strong>🔄 Flow Journey</strong>
                </h2>
                <p style="font-size: 14px; color: #64748b; font-weight: 400; margin: 0 0 2px 0; line-height: 1.6; font-family: system-ui;">
                    A flow is the complete user journey: Publisher → Creative → SERP → Landing Page. 
                    Each stage can be customized using the filters above. We automatically select the best-performing combination based on conversions, clicks, and impressions.
                </p>
                """, unsafe_allow_html=True)
                
                # Show flow stats directly (no success messages)
                if len(final_filtered) > 0:
                    # Show selected flow stats
                    single_view = final_filtered.iloc[0]
                    flow_imps = safe_int(single_view.get('impressions', 0))
                    flow_clicks = safe_int(single_view.get('clicks', 0))
                    flow_convs = safe_int(single_view.get('conversions', 0))
                    flow_ctr = (flow_clicks / flow_imps * 100) if flow_imps > 0 else 0
                    flow_cvr = (flow_convs / flow_clicks * 100) if flow_clicks > 0 else 0
                    
                    render_selected_flow_display(single_view, flow_imps, flow_clicks, flow_convs, flow_ctr, flow_cvr)
                
                # Render Flow Journey using module (heading now shown above)
                render_flow_journey(
                    campaign_df=campaign_df,
                    current_flow=current_flow,
                    api_key=API_KEY,
                    playwright_available=PLAYWRIGHT_AVAILABLE,
                    thumio_configured=THUMIO_CONFIGURED,
                    thumio_referer_domain=THUMIO_REFERER_DOMAIN
                )
            
            else:
                st.warning("No data available for this campaign")
else:
    st.error("❌ Could not load data - Check FILE_A_ID and file sharing settings")
