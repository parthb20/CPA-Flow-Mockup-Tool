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
from src.config import FILE_A_ID, FILE_B_ID, FILE_C_ID, FILE_D_ID, SERP_BASE_URL
from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
from src.creative_renderer import load_creative_requests, load_prerendered_responses, render_creative_via_weaver, parse_keyword_array_from_flow
from src.utils import safe_float, safe_int
from src.flow_analysis import find_default_flow
from src.similarity import calculate_similarities
from src.serp import generate_serp_mockup
from src.renderers import (
    render_mini_device_preview,
    render_similarity_score,
    inject_unique_id,
    create_screenshot_html
)
from src.screenshot import get_screenshot_url, capture_with_playwright
from src.ui_components import render_flow_combinations_table, render_what_is_flow_section, render_selected_flow_display
from src.filters import render_advanced_filters, apply_flow_filtering
from src.flow_display import render_flow_journey

# Try to import playwright (for 403 bypass)
# Note: Playwright requires browser binaries which may not be available on Streamlit Cloud
# Fallback rendering will be used automatically if unavailable
try:
    from playwright.sync_api import sync_playwright
    from pathlib import Path
    
    # Check if browser binaries are installed
    browser_path = Path.home() / ".cache" / "ms-playwright"
    browsers_exist = browser_path.exists() and list(browser_path.glob("chromium*"))
    
    PLAYWRIGHT_AVAILABLE = browsers_exist
    
except Exception:
    PLAYWRIGHT_AVAILABLE = False

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

# Custom CSS - RESPONSIVE VERSION
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
    
    /* RESPONSIVE TEXT - scales between min and max based on viewport */
    h1:not(.main-title), h2, h3, h4, h5, h6, p, span, div, label, .stMarkdown {
        color: #0f172a !important;
        font-weight: 500 !important;
        font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem) !important; /* 14-16px */
    }
    
    /* Don't override the main title - it has its own inline styles */
    h1:not(.main-title) { 
        font-weight: 700 !important; 
        font-size: clamp(1.75rem, 1.5rem + 1.25vw, 2rem) !important; /* 28-32px */
    }
    
    /* Ensure main title is properly sized - RESPONSIVE & BIG */
    .main-title {
        font-size: clamp(2.5rem, 2rem + 2.5vw, 4.5rem) !important; /* 40-72px */
        font-weight: 900 !important;
        color: #0f172a !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.3 !important;
        letter-spacing: 0.01em !important;
        word-spacing: normal !important;
        white-space: normal !important;
    }
    
    h2 { 
        font-weight: 700 !important; 
        font-size: clamp(1.375rem, 1.2rem + 0.9vw, 1.625rem) !important; /* 22-26px */
    }
    h3 { 
        font-weight: 700 !important; 
        font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem) !important; /* 20-22px */
    }
    
    /* Buttons - RESPONSIVE & CONSISTENT */
    .stButton > button,
    button[data-testid*="baseButton"],
    .stButton button {
        background-color: white !important;
        color: #0f172a !important;
        border: 2px solid #cbd5e1 !important;
        font-weight: 600 !important;
        font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem) !important; /* 14-16px */
        padding: clamp(0.4rem, 0.3rem + 0.4vw, 0.6rem) clamp(0.875rem, 0.7rem + 0.8vw, 1.25rem) !important;
        border-radius: 0.375rem !important;
        min-height: auto !important;
        height: auto !important;
    }
    .stButton > button:hover,
    button[data-testid*="baseButton"]:hover {
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
    
    /* Popover buttons specifically - WHITE BACKGROUND */
    .stPopover > button,
    button[data-testid*="popover"],
    [data-testid*="stPopover"] button {
        background-color: white !important;
        color: #0f172a !important;
        border: 2px solid #cbd5e1 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1rem !important;
    }
    
    /* Flow navigation buttons - VERY COMPACT */
    button[key*="prev_flow"],
    button[key*="next_flow"] {
        padding: 0.25rem 0.5rem !important;
        font-size: 0.875rem !important;
        min-height: 1.75rem !important;
        max-height: 2rem !important;
        width: auto !important;
    }
    
    /* Dropdowns - RESPONSIVE */
    [data-baseweb="select"] { background-color: white !important; }
    [data-baseweb="select"] > div { 
        background-color: white !important; 
        border-color: #cbd5e1 !important; 
    }
    [data-baseweb="select"] span { 
        color: #0f172a !important; 
        font-weight: 500 !important; 
        font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem) !important; /* 14-16px */
    }
    [role="listbox"] { 
        background-color: white !important; 
    }
    [role="option"] { 
        background-color: white !important; 
        color: #0f172a !important; 
    }
    [role="option"]:hover { 
        background-color: #f8fafc !important; 
        color: #0f172a !important; 
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
    
    /* Metrics - RESPONSIVE */
    [data-testid="stMetric"] {
        background: white;
        padding: clamp(0.75rem, 0.6rem + 0.8vw, 1rem);
        border-radius: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem);
        border: 2px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    [data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-weight: 700 !important;
        font-size: clamp(1.5rem, 1.3rem + 1vw, 1.75rem) !important; /* 24-28px */
    }
    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 600 !important;
        font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem) !important; /* 12-14px */
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
    
    /* Flow Card - RESPONSIVE */
    .flow-card {
        background: white;
        border: 2px solid #e2e8f0;
        border-radius: clamp(0.5rem, 0.4rem + 0.6vw, 0.75rem);
        padding: clamp(1rem, 0.8rem + 1vw, 1.25rem);
        margin: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem) 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .flow-stage {
        text-align: center;
        padding: clamp(0.75rem, 0.6rem + 0.8vw, 1rem);
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border: 2px solid #3b82f6;
        border-radius: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem);
        margin: 0 clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem);
    }
    
    .flow-arrow {
        font-size: clamp(1.5rem, 1.3rem + 1vw, 2rem); /* 24-32px */
        color: #3b82f6;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 clamp(0.25rem, 0.2rem + 0.25vw, 0.3125rem);
    }
    
    .similarity-card {
        background: white;
        border-radius: clamp(0.5rem, 0.4rem + 0.6vw, 0.75rem);
        padding: clamp(1rem, 0.8rem + 1vw, 1.25rem);
        border: 2px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .score-box {
        display: inline-block;
        padding: clamp(0.75rem, 0.6rem + 0.8vw, 1rem) clamp(1.25rem, 1rem + 1.25vw, 1.5rem);
        border-radius: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem);
        border: 3px solid;
        font-size: clamp(2rem, 1.75rem + 1.3vw, 2.625rem); /* 32-42px */
        font-weight: 700;
        margin: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem) 0;
    }
    
    .score-excellent { border-color: #22c55e; background: linear-gradient(135deg, #22c55e15, #22c55e08); color: #22c55e; }
    .score-good { border-color: #3b82f6; background: linear-gradient(135deg, #3b82f615, #3b82f608); color: #3b82f6; }
    .score-moderate { border-color: #eab308; background: linear-gradient(135deg, #eab30815, #eab30808); color: #eab308; }
    .score-weak { border-color: #f97316; background: linear-gradient(135deg, #f9731615, #f9731608); color: #f97316; }
    .score-poor { border-color: #ef4444; background: linear-gradient(135deg, #ef444415, #ef444408); color: #ef4444; }
    
    .info-box {
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        padding: clamp(1rem, 0.8rem + 1vw, 1.125rem);
        border-radius: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem);
        border: 1px solid #bae6fd;
        border-left: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem) solid #3b82f6;
        margin: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem) 0;
        line-height: 1.8;
        font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem); /* 14-16px */
        color: #0f172a !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-weight: 500;
    }
    .info-box p, .info-box div, .info-box span {
        color: #0f172a !important;
        background: transparent !important;
    }
    
    /* Custom Loading Spinner - Circular Arrow */
    .stSpinner > div {
        border-color: #3b82f6 !important;
        border-right-color: transparent !important;
    }
    
    /* Streamlit's native spinner styling */
    [data-testid="stSpinner"] {
        color: #3b82f6 !important;
    }
    
    /* Remove empty space from element containers */
    .main .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Reduce element container spacing - MORE AGGRESSIVE */
    .element-container {
        margin-bottom: 0.15rem !important;
    }
    
    /* Reduce space between main sections */
    .main > div > div > div > div {
        margin-bottom: 0.25rem !important;
    }
    
    /* Remove empty divs that create unnecessary space */
    div:empty {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Reduce vertical block spacing */
    [data-testid="stVerticalBlock"] > div {
        gap: 0 !important;
    }
    
    /* Compact row spacing */
    [data-testid="column"] {
        padding: 0 0.5rem !important;
    }
    
    /* Remove spacing from horizontal blocks */
    [data-testid="stHorizontalBlock"] {
        gap: 0.5rem !important;
    }
    
    /* Remove extra margins from element containers */
    .element-container:has(> .row-widget) {
        margin-bottom: 0 !important;
    }
    
    /* AGGRESSIVE: Hide specific empty containers that create gaps */
    .element-container:empty,
    div[data-testid="stVerticalBlock"]:empty,
    div[data-testid="stHorizontalBlock"]:empty {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
    }
    
    /* Remove gaps between advertiser/campaign and flow journey */
    .main > div > div > div {
        margin-bottom: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Session state initialization
for key in ['data_a', 'data_b', 'data_c', 'data_d', 'loading_done', 'default_flow', 'current_flow', 'view_mode', 'flow_layout', 'similarities', 'last_campaign_key', 'all_flows', 'current_flow_index', 'last_filter_key', 'show_time_filter', 'flow_type']:
    if key not in st.session_state:
        if key == 'view_mode':
            st.session_state[key] = 'basic'
        elif key == 'flow_layout':
            st.session_state[key] = 'horizontal'
        elif key == 'current_flow_index':
            st.session_state[key] = 0
        elif key == 'all_flows':
            st.session_state[key] = []
        elif key == 'show_time_filter':
            st.session_state[key] = False
        elif key == 'flow_type':
            st.session_state[key] = 'Best'
        else:
            st.session_state[key] = None

# Main title - BIG and BOLD at top - RESPONSIVE
st.markdown("""
    <div style="margin: 0 0 clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem) 0; padding: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem) 0; border-bottom: clamp(2px, 0.1rem + 0.15vw, 3px) solid #e2e8f0;">
        <h1 style="font-size: clamp(2.5rem, 2rem + 2.5vw, 4rem); font-weight: 900; color: #0f172a; margin: 0; padding: 0; line-height: 1.2; letter-spacing: -1px; font-family: system-ui, -apple-system, sans-serif;">
            📊 CPA Flow Analysis
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
            
            # Load File D (pre-rendered responses) - silently
            if FILE_D_ID and FILE_D_ID.strip() != "":
                st.session_state.data_d = load_prerendered_responses(FILE_D_ID)
            else:
                st.session_state.data_d = None
            
            # Load File C (creative requests) - silently, optional
            if FILE_C_ID and FILE_C_ID.strip() != "":
                st.session_state.data_c = load_creative_requests(FILE_C_ID)
            else:
                st.session_state.data_c = None
            
            st.session_state.loading_done = True
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            st.session_state.loading_done = True

# No view mode toggle here - moved to flow controls

if st.session_state.data_a is not None and len(st.session_state.data_a) > 0:
    df = st.session_state.data_a
    
    # Select Advertiser, Campaign, Use Full Data, and Time filter at top
    col1, col2, col3, col4 = st.columns([1.5, 1.5, 1, 1.5])
    with col1:
        # Find advertiser column (handle case variations)
        adv_col = next((col for col in df.columns if col.lower() == 'advertiser_name'), 'Advertiser_Name')
        advertisers = ['-- Select Advertiser --'] + sorted(df[adv_col].dropna().unique().tolist())
        # Preserve advertiser selection
        default_adv_idx = 0
        if 'preserved_advertiser' in st.session_state and st.session_state.preserved_advertiser in advertisers:
            default_adv_idx = advertisers.index(st.session_state.preserved_advertiser)
        selected_advertiser = st.selectbox("Advertiser", advertisers, index=default_adv_idx)
        if selected_advertiser != '-- Select Advertiser --':
            st.session_state.preserved_advertiser = selected_advertiser
    
    if selected_advertiser and selected_advertiser != '-- Select Advertiser --':
        with col2:
            # Find campaign column (handle case variations)
            camp_col = next((col for col in df.columns if col.lower() == 'campaign_name'), 'Campaign_Name')
            campaigns = ['-- Select Campaign --'] + sorted(df[df[adv_col] == selected_advertiser][camp_col].dropna().unique().tolist())
            # Preserve campaign selection
            default_camp_idx = 0
            if 'preserved_campaign' in st.session_state and st.session_state.preserved_campaign in campaigns:
                default_camp_idx = campaigns.index(st.session_state.preserved_campaign)
            selected_campaign = st.selectbox("Campaign", campaigns, key='campaign_selector', index=default_camp_idx)
            if selected_campaign != '-- Select Campaign --':
                st.session_state.preserved_campaign = selected_campaign
        
        # Use Full Data checkbox - aligned with dropdown VALUES (not labels)
        with col3:
            # Add spacer to match dropdown label height PLUS the dropdown's top padding
            st.markdown('<div style="height: 1.65rem;"></div>', unsafe_allow_html=True)
            use_full_data = st.checkbox(
                "Use Full Data",
                value=False,
                help="Bypass 5% threshold filter",
                key='use_full_data_toggle'
            )
        
        # Time Filter at top right - clean and minimal
        with col4:
            from datetime import date, timedelta
            today = date.today()
            # Default to January 2026 (Jan 1 - Jan 31)
            jan_start = date(2026, 1, 1)
            jan_end = date(2026, 1, 31)
            
            # Initialize defaults to January
            if 'start_date' not in st.session_state:
                st.session_state.start_date = jan_start
            if 'end_date' not in st.session_state:
                st.session_state.end_date = jan_end
            if 'start_hour' not in st.session_state:
                st.session_state.start_hour = 0
            if 'end_hour' not in st.session_state:
                st.session_state.end_hour = 23
            
            # CSS for Time button and checkbox
            st.markdown("""
                <style>
                /* Compact Time popover button */
                button[data-testid*="popover"] {
                    background-color: white !important;
                    color: #1f2937 !important;
                    border: 2px solid #cbd5e1 !important;
                    padding: 0.25rem 0.5rem !important;
                    font-size: 0.8rem !important;
                    min-height: 1.8rem !important;
                    max-width: 100px !important;
                }
                
                /* Remove special checkbox background */
                [data-testid="stCheckbox"] {
                    background: transparent !important;
                }
                </style>
            """, unsafe_allow_html=True)
            with st.popover("🕐 Time", use_container_width=False):
                # Hour selection first
                st.markdown("**Hour Range**")
                hour_row = st.columns(2)
                with hour_row[0]:
                    start_hour = st.selectbox("Start", options=list(range(24)), index=st.session_state.get('start_hour', 0), format_func=lambda x: f"{x:02d}:00", key='start_hour_filter')
                    st.session_state.start_hour = start_hour
                with hour_row[1]:
                    end_hour = st.selectbox("End", options=list(range(24)), index=st.session_state.get('end_hour', 23), format_func=lambda x: f"{x:02d}:00", key='end_hour_filter')
                    st.session_state.end_hour = end_hour
                
                # Date range selection - interactive drag calendar
                st.markdown("**Date Range**")
                date_range = st.date_input(
                    "Select Range",
                    value=(st.session_state.get('start_date', jan_start), st.session_state.get('end_date', jan_end)),
                    min_value=date(2026, 1, 1),
                    max_value=date(2026, 12, 31),
                    key='date_range_filter',
                    label_visibility="collapsed"
                )
                
                # Handle date range tuple
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    st.session_state.start_date = date_range[0]
                    st.session_state.end_date = date_range[1]
                elif isinstance(date_range, date):
                    st.session_state.start_date = date_range
                    st.session_state.end_date = date_range
            
            # Use current values
            start_date = st.session_state.get('start_date', jan_start)
            end_date = st.session_state.get('end_date', jan_end)
            start_hour = st.session_state.get('start_hour', 0)
            end_hour = st.session_state.get('end_hour', 23)
        
        # Hidden defaults
        entity_threshold = 0.0 if use_full_data else 5.0
        num_flows = 5
        include_serp_in_flow = False  # Always false, hidden
        
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
            campaign_df = df[(df[adv_col] == selected_advertiser) & (df[camp_col] == selected_campaign)].copy()
            
            # Check if we have data
            if len(campaign_df) == 0:
                st.warning("⚠️ No rows found for this campaign. Check advertiser/campaign names match exactly.")
                st.stop()
            
            # === FLOW FILTERS - LIGHT & CLEAN ===
            st.markdown("""
                <style>
                /* Force light theme for ALL inputs */
                .stDateInput > div > div > input,
                .stDateInput input,
                .stDateInput,
                .stSelectbox > div > div,
                .stSelectbox > div > div > div,
                .stSelectbox input,
                .stCheckbox,
                .stRadio > div,
                [data-baseweb="select"],
                [data-baseweb="select"] > div,
                [data-baseweb="input"],
                [data-baseweb="base-input"],
                [data-baseweb="calendar"],
                [data-baseweb="datepicker"] {
                    background-color: white !important;
                    color: #1f2937 !important;
                    border-color: #d1d5db !important;
                }
                
                /* Fix Popover - WHITE BACKGROUND */
                .stPopover,
                [data-baseweb="popover"],
                [data-baseweb="popover"] > div,
                .stPopover > div,
                .stPopover [data-baseweb="popover"] {
                    background-color: white !important;
                    color: #1f2937 !important;
                }
                
                /* Popover content */
                [data-baseweb="popover"] [data-baseweb="layer"] {
                    background-color: white !important;
                }
                
                /* Popover inner content */
                .stPopover div[data-testid="stVerticalBlock"],
                .stPopover div {
                    background-color: white !important;
                    color: #1f2937 !important;
                }
                
                /* Date picker calendar - FIX BLACK ELEMENTS */
                [data-baseweb="calendar"],
                [data-baseweb="calendar"] *,
                [data-baseweb="calendar"] div,
                [data-baseweb="calendar"] button,
                [data-baseweb="calendar"] span,
                [data-baseweb="calendar"] [role="gridcell"] {
                    background-color: white !important;
                    color: #1f2937 !important;
                }
                
                /* Calendar header */
                [data-baseweb="calendar"] [data-baseweb="select"],
                [data-baseweb="calendar"] select {
                    background-color: white !important;
                    color: #1f2937 !important;
                }
                
                /* Selected/highlighted dates */
                [data-baseweb="calendar"] button[aria-selected="true"],
                [data-baseweb="calendar"] [aria-selected="true"] {
                    background-color: #3b82f6 !important;
                    color: white !important;
                }
                
                /* Hover states for calendar */
                [data-baseweb="calendar"] button:hover {
                    background-color: #f3f4f6 !important;
                    color: #1f2937 !important;
                }
                
                /* Dropdown menus */
                [data-baseweb="popover"],
                [data-baseweb="menu"],
                [role="listbox"],
                [role="option"] {
                    background-color: white !important;
                    color: #1f2937 !important;
                }
                
                /* Hover states */
                [role="option"]:hover,
                [data-baseweb="menu"] li:hover {
                    background-color: #f3f4f6 !important;
                    color: #1f2937 !important;
                }
                
                /* Selected state */
                [aria-selected="true"] {
                    background-color: #e5e7eb !important;
                    color: #1f2937 !important;
                }
                
                /* Radio buttons - Custom styled with colors */
                .stRadio > div {
                    flex-direction: row !important;
                    gap: 1rem !important;
                    justify-content: flex-start !important;
                    align-items: center !important;
                }
                .stRadio label {
                    font-size: clamp(1rem, 0.9rem + 0.5vw, 1.125rem) !important;
                    font-weight: 600 !important;
                    padding: clamp(0.625rem, 0.5rem + 0.5vw, 0.75rem) clamp(1.5rem, 1.2rem + 1.5vw, 2rem) !important;
                    border-radius: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem) !important;
                    background: white !important;
                    border: 2px solid #d1d5db !important;
                    cursor: pointer !important;
                    transition: all 0.2s ease !important;
                    min-width: clamp(5rem, 4rem + 5vw, 6.25rem) !important;
                    text-align: center !important;
                    color: #1f2937 !important;
                }
                .stRadio label:hover {
                    border-color: #9ca3af !important;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
                }
                
                /* Best flow - green */
                .stRadio label:has(input[value="Best"]:checked) {
                    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%) !important;
                    color: #1f2937 !important;
                    border-color: #10b981 !important;
                    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2) !important;
                }
                
                /* Worst flow - red */
                .stRadio label:has(input[value="Worst"]:checked) {
                    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%) !important;
                    color: #1f2937 !important;
                    border-color: #ef4444 !important;
                    box-shadow: 0 2px 4px rgba(239, 68, 68, 0.2) !important;
                }
                
                .stRadio input[type="radio"] {
                    display: none !important;
                }
                
                /* Buttons - clean and consistent */
                .stButton > button {
                    background-color: white !important;
                    color: #1f2937 !important;
                    border: 2px solid #d1d5db !important;
                    border-radius: 0.5rem !important;
                    font-weight: 600 !important;
                    transition: all 0.2s ease !important;
                }
                .stButton > button:hover:not(:disabled) {
                    border-color: #9ca3af !important;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
                    background-color: #f9fafb !important;
                }
                .stButton > button:disabled {
                    opacity: 0.4 !important;
                    cursor: not-allowed !important;
                }
                
                /* Custom styles applied via inline later */
                </style>
            """, unsafe_allow_html=True)
            
            # Initialize flow type if not set
            if 'flow_type' not in st.session_state:
                st.session_state.flow_type = 'Best'
            
            flow_type = st.session_state.flow_type
            
            st.markdown("---")
            # === END FILTERS ===
            
            # Apply date filter
            from src.flow_analysis import filter_by_date_range, filter_by_threshold
            campaign_df = filter_by_date_range(campaign_df, start_date, start_hour, end_date, end_hour)
            
            if len(campaign_df) == 0:
                st.warning("⚠️ No data found for selected date range. Please adjust filters.")
                st.stop()
            
            # Apply threshold filters only if not using full data
            if entity_threshold > 0:
                original_len = len(campaign_df)
                campaign_df = filter_by_threshold(campaign_df, 'keyword_term', entity_threshold)
                campaign_df = filter_by_threshold(campaign_df, 'publisher_domain', entity_threshold)
                
                if len(campaign_df) == 0:
                    st.warning(f"⚠️ No keywords/domains meet the {entity_threshold}% threshold. Try lowering the threshold.")
                    st.stop()
            
            # Convert numeric columns to proper types FIRST
            campaign_df['impressions'] = pd.to_numeric(campaign_df['impressions'], errors='coerce').fillna(0)
            campaign_df['clicks'] = pd.to_numeric(campaign_df['clicks'], errors='coerce').fillna(0)
            campaign_df['conversions'] = pd.to_numeric(campaign_df['conversions'], errors='coerce').fillna(0)
            
            # Calculate CTR and CVR per row
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
            
            # Find top flows if not set or if filters changed
            # Use a key to track if filters changed
            filter_key = f"{start_date}_{start_hour}_{end_date}_{end_hour}_{flow_type}_{entity_threshold}_{num_flows}_{use_full_data}_{include_serp_in_flow}"
            if 'last_filter_key' not in st.session_state:
                st.session_state.last_filter_key = None
            
            if st.session_state.last_filter_key != filter_key:
                # Filters changed, recalculate flows
                st.session_state.last_filter_key = filter_key
                st.session_state.all_flows = []
                st.session_state.current_flow_index = 0
            
            if len(st.session_state.get('all_flows', [])) == 0:
                with st.spinner(f"Finding top {num_flows} {flow_type.lower()} flows..."):
                    from src.flow_analysis import find_top_n_best_flows, find_top_n_worst_flows
                    
                    if flow_type == "Best":
                        flows = find_top_n_best_flows(campaign_df, n=num_flows, include_serp_filter=include_serp_in_flow)
                    else:  # Worst
                        flows = find_top_n_worst_flows(campaign_df, n=num_flows, include_serp_filter=include_serp_in_flow)
                    
                    if flows:
                        st.session_state.all_flows = flows
                        st.session_state.current_flow_index = 0
                        st.session_state.default_flow = flows[0]
                        st.session_state.current_flow = flows[0].copy()
                    else:
                        st.error(f"❌ No {flow_type.lower()} flows found with current filters.")
                        st.stop()
            
            if st.session_state.current_flow:
                current_flow = st.session_state.current_flow
                
                # Render filters and get filter state
                filters_changed, selected_keyword_filter, selected_domain_filter = render_advanced_filters(campaign_df, current_flow)
                
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
                
                # Add Flow Journey title with explanation - RESPONSIVE
                st.markdown("""
                <h2 style="font-size: clamp(2.5rem, 2rem + 2.5vw, 3.5rem); font-weight: 900; color: #0f172a; margin: 0; padding: 0; line-height: 1.2; letter-spacing: -1px; font-family: system-ui;">
                    <strong>🔄 Flow Journey</strong>
                </h2>
                <p style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem); color: #64748b; font-weight: 400; margin: 0 0 0.25rem 0; line-height: 1.6; font-family: system-ui;">
                    A flow is the complete user journey: Publisher → Creative → SERP → Landing Page. Each stage can be customized using the filters above. We automatically select the best-performing combination based on conversions, clicks, and impressions.
                </p>
                    """, unsafe_allow_html=True)
                
                # === FLOW NAVIGATION - Arrows INLINE with flow count ===
                if len(st.session_state.get('all_flows', [])) > 1:
                    nav_cols = st.columns([0.7, 0.7, 1.6, 2])
                    
                    # Best Flows button
                    with nav_cols[0]:
                        if st.button("Best Flows", key='best_button', use_container_width=True):
                            st.session_state.flow_type = 'Best'
                            st.rerun()
                    
                    # Worst Flows button
                    with nav_cols[1]:
                        if st.button("Worst Flows", key='worst_button', use_container_width=True):
                            st.session_state.flow_type = 'Worst'
                            st.rerun()
                    
                    # Arrow + Flow count + Arrow in ONE inline div
                    with nav_cols[2]:
                        prev_disabled = st.session_state.current_flow_index == 0
                        next_disabled = st.session_state.current_flow_index >= len(st.session_state.all_flows) - 1
                        
                        # Display: Arrow emoji Flow X of Y Arrow emoji - all inline, NO BOXES
                        left_arrow_html = f'<span id="prev_arrow" style="cursor: {"pointer" if not prev_disabled else "default"}; opacity: {"1" if not prev_disabled else "0.3"}; font-size: 1.2rem; margin-right: 0.5rem; user-select: none;">⬅️</span>'
                        right_arrow_html = f'<span id="next_arrow" style="cursor: {"pointer" if not next_disabled else "default"}; opacity: {"1" if not next_disabled else "0.3"}; font-size: 1.2rem; margin-left: 0.5rem; user-select: none;">➡️</span>'
                        
                        st.markdown(f'''
                            <div style="display: flex; align-items: center; justify-content: center; padding-top: 3px;">
                                {left_arrow_html}
                                <span style="font-size: 0.85rem; color: #64748b; font-weight: 600;">Flow {st.session_state.current_flow_index + 1} of {len(st.session_state.all_flows)}</span>
                                {right_arrow_html}
                            </div>
                            <script>
                            document.getElementById('prev_arrow')?.addEventListener('click', function() {{
                                if ({str(not prev_disabled).lower()}) {{
                                    window.location.href = '?nav=prev&t=' + Date.now();
                                }}
                            }});
                            document.getElementById('next_arrow')?.addEventListener('click', function() {{
                                if ({str(not next_disabled).lower()}) {{
                                    window.location.href = '?nav=next&t=' + Date.now();
                                }}
                            }});
                            </script>
                        ''', unsafe_allow_html=True)
                        
                        # Handle navigation via query params
                        import streamlit as st
                        query_params = st.query_params
                        if 'nav' in query_params:
                            if query_params['nav'] == 'prev' and not prev_disabled:
                                st.session_state.current_flow_index = max(0, st.session_state.current_flow_index - 1)
                                st.session_state.current_flow = st.session_state.all_flows[st.session_state.current_flow_index].copy()
                                st.query_params.clear()
                                st.rerun()
                            elif query_params['nav'] == 'next' and not next_disabled:
                                st.session_state.current_flow_index = min(len(st.session_state.all_flows) - 1, st.session_state.current_flow_index + 1)
                                st.session_state.current_flow = st.session_state.all_flows[st.session_state.current_flow_index].copy()
                                st.query_params.clear()
                                st.rerun()
                    
                    # CSS for buttons - LIGHT GREEN/RED backgrounds with borders when clicked
                    best_bg = 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)' if flow_type == 'Best' else 'white'
                    best_border = '3px solid #10b981' if flow_type == 'Best' else '2px solid #d1d5db'
                    best_color = '#065f46'  # Always dark green text
                    best_shadow = '0 0 0 3px rgba(16, 185, 129, 0.2)' if flow_type == 'Best' else 'none'
                    
                    worst_bg = 'linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)' if flow_type == 'Worst' else 'white'
                    worst_border = '3px solid #ef4444' if flow_type == 'Worst' else '2px solid #d1d5db'
                    worst_color = '#991b1b'  # Always dark red text
                    worst_shadow = '0 0 0 3px rgba(239, 68, 68, 0.2)' if flow_type == 'Worst' else 'none'
                    
                    # SUPER SPECIFIC CSS to override global button styles
                    st.markdown(f"""
                        <style>
                        /* Target Best button - be ULTRA specific */
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button,
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child button[kind="secondary"] {{
                            background: {best_bg} !important;
                            border: {best_border} !important;
                            color: {best_color} !important;
                            box-shadow: {best_shadow} !important;
                            padding: 0.3rem 0.6rem !important;
                            font-size: 0.8rem !important;
                            font-weight: 700 !important;
                            min-height: 1.75rem !important;
                            height: 1.75rem !important;
                        }}
                        
                        /* Target Worst button - be ULTRA specific */
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) .stButton > button,
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) button[kind="secondary"] {{
                            background: {worst_bg} !important;
                            border: {worst_border} !important;
                            color: {worst_color} !important;
                            box-shadow: {worst_shadow} !important;
                            padding: 0.3rem 0.6rem !important;
                            font-size: 0.8rem !important;
                            font-weight: 700 !important;
                            min-height: 1.75rem !important;
                            height: 1.75rem !important;
                        }}
                        
                        /* Override hover for these buttons */
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child .stButton > button:hover {{
                            background: {best_bg} !important;
                            border: {best_border} !important;
                        }}
                        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) .stButton > button:hover {{
                            background: {worst_bg} !important;
                            border: {worst_border} !important;
                        }}
                        </style>
                    """, unsafe_allow_html=True)
                
                # Show flow stats directly (no success messages)
                if len(final_filtered) > 0:
                    # Get stats from the SPECIFIC flow record (not aggregated)
                    # A flow is: Advertiser -> Campaign -> Publisher URL -> Keyword -> SERP URL -> Landing Page URL
                    # Stats should be for THIS specific combination, not summed across multiple records
                    
                    flow_imps = safe_int(current_flow.get('impressions', 0))
                    flow_clicks = safe_int(current_flow.get('clicks', 0))
                    flow_convs = safe_int(current_flow.get('conversions', 0))
                    
                    # Calculate rates for this specific flow
                    flow_ctr = (flow_clicks / flow_imps * 100) if flow_imps > 0 else 0
                    flow_cvr = (flow_convs / flow_clicks * 100) if flow_clicks > 0 else 0
                    
                    # Use current_flow as single_view (it's already the selected flow record)
                    single_view = current_flow
                    
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
                
                # ============================================================
                # FILTERS, TABLE, AND OVERVIEW - MOVED BELOW FLOW JOURNEY
                # ============================================================
                
                st.markdown("<br><br>", unsafe_allow_html=True)
                
                # Show aggregated table with big title - RESPONSIVE
                st.markdown("""
                <div style="margin-bottom: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem); margin-top: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem);">
                    <h2 style="font-size: clamp(2.25rem, 1.9rem + 1.8vw, 3rem); font-weight: 900; color: #0f172a; margin: 0; padding: 0; text-align: left; line-height: 1;">
                        📊 Flow Combinations Overview
                    </h2>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Render table using module
                render_flow_combinations_table(campaign_df)
                
                # Render "What is Flow" section using module
                render_what_is_flow_section()
            else:
                st.warning("⚠️ Data is too granular - no entities meet the 5% threshold. Please enable 'Use Full Data' option above to see all flows.")
else:
    st.error("❌ Could not load data - Check FILE_A_ID and file sharing settings")
