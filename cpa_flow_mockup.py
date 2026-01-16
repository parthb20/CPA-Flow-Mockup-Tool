# -*- coding: utf-8 -*-
"""
CPA Flow Analysis Tool - Main Application
Modular architecture for maintainability
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse, urljoin
import re
import html
from concurrent import futures

# Import from modules
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
        pass
except Exception as e:
    PLAYWRIGHT_AVAILABLE = False
    st.warning(f"Playwright not available: {str(e)[:50]}")

# Page config - MUST be first Streamlit command
st.set_page_config(page_title="CPA Flow Analysis v2", page_icon="📊", layout="wide")

# Get API keys from secrets
try:
    API_KEY = st.secrets.get("FASTROUTER_API_KEY", st.secrets.get("OPENAI_API_KEY", "")).strip()
    SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()
    THUMIO_REFERER_DOMAIN = st.secrets.get("THUMIO_REFERER_DOMAIN", "").strip()
    # Debug: Check if API key is loaded
    if not API_KEY:
        st.warning("⚠️ API key not found. Please add FASTROUTER_API_KEY or OPENAI_API_KEY to Streamlit secrets.")
except Exception as e:
    API_KEY = ""
    SCREENSHOT_API_KEY = ""
    THUMIO_REFERER_DOMAIN = ""
    st.warning(f"⚠️ Error loading secrets: {str(e)[:100]}")

THUMIO_CONFIGURED = True  # Always True - free tier works without setup!

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

# Proper SaaS-style title - REALLY BIG and BOLD (like a logo)
st.markdown("""
    <div style="margin-bottom: 8px; margin-top: -40px; padding-top: 0px; padding-bottom: 8px; border-bottom: 3px solid #e2e8f0;">
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
                # Table filter controls
                table_col1, table_col2, table_col3 = st.columns(3)
                with table_col1:
                    table_filter = st.selectbox("Filter:", ['Best', 'Worst', 'Overall'], index=0, key='table_filter')
                with table_col2:
                    table_count = st.selectbox("Rows:", [5, 10, 15], index=1, key='table_count')
                with table_col3:
                    table_sort = st.selectbox("Sort by:", ['Impressions', 'Clicks', 'Conversions', 'CTR', 'CVR'], index=0, key='table_sort')
                
                # Aggregate by domain + keyword
                agg_df = campaign_df.groupby(['publisher_domain', 'keyword_term']).agg({
                    'impressions': 'sum',
                    'clicks': 'sum',
                    'conversions': 'sum'
                }).reset_index()
                
                agg_df['CTR'] = agg_df.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
                agg_df['CVR'] = agg_df.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
                
                # Calculate weighted averages for CTR and CVR
                total_imps = agg_df['impressions'].sum()
                total_clicks = agg_df['clicks'].sum()
                weighted_avg_ctr = (agg_df['clicks'].sum() / total_imps * 100) if total_imps > 0 else 0
                weighted_avg_cvr = (agg_df['conversions'].sum() / total_clicks * 100) if total_clicks > 0 else 0
                
                # Map sort column names
                sort_map = {
                    'Impressions': 'impressions',
                    'Clicks': 'clicks',
                    'Conversions': 'conversions',
                    'CTR': 'CTR',
                    'CVR': 'CVR'
                }
                sort_col = sort_map.get(table_sort, 'impressions')
                
                # Sort based on filter
                if table_filter == 'Best':
                    agg_df = agg_df.sort_values(sort_col, ascending=False)
                elif table_filter == 'Worst':
                    agg_df = agg_df.sort_values(sort_col, ascending=True)
                else:  # Overall - show all
                    agg_df = agg_df.sort_values(sort_col, ascending=False)
                
                # Show selected count
                agg_df = agg_df.head(table_count).reset_index(drop=True)
                
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
            st.markdown("<div style='margin-top: 8px; margin-bottom: 8px;'></div>", unsafe_allow_html=True)
            
            # Simplified, easy-to-read flow explanation with consistent styling
            st.markdown("""
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 8px 0;">
                <h3 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">🔄 What is a Flow?</h3>
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
                
                # Flow layout toggle - lighter colors, bold and large
                st.markdown("""
                <style>
                button[key='horiz_btn'], button[key='vert_btn'] {
                    font-weight: 700 !important;
                    font-size: 16px !important;
                }
                button[key='horiz_btn']:has-text("Horizontal") {
                    background-color: #e0f2fe !important;
                }
                </style>
                """, unsafe_allow_html=True)
                layout_col1, layout_col2, layout_col3, layout_col4 = st.columns([1, 1, 3, 1])
                with layout_col1:
                    if st.button("↔️ **Horizontal**", key='horiz_btn', type="primary" if st.session_state.flow_layout == 'horizontal' else "secondary", use_container_width=True):
                        st.session_state.flow_layout = 'horizontal'
                        st.rerun()
                with layout_col2:
                    if st.button("↕️ **Vertical**", key='vert_btn', type="primary" if st.session_state.flow_layout == 'vertical' else "secondary", use_container_width=True):
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
                    
                    # Single unified filter - searchable selectbox
                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        keywords = sorted(campaign_df['keyword_term'].dropna().unique().tolist())
                        current_kw_val = current_flow.get('keyword_term', '')
                        default_kw_idx = 0
                        if current_kw_val in keywords:
                            default_kw_idx = keywords.index(current_kw_val) + 1  # +1 because 'All' is first
                        # Use selectbox with search - Streamlit selectbox has built-in search
                        selected_keyword_filter = st.selectbox("🔑 Filter by Keyword:", ['All'] + keywords, index=default_kw_idx, key='kw_filter_adv')
                    
                    with filter_col2:
                        if 'publisher_domain' in campaign_df.columns:
                            domains = sorted(campaign_df['publisher_domain'].dropna().unique().tolist())
                            current_dom_val = current_flow.get('publisher_domain', '')
                            default_dom_idx = 0
                            if current_dom_val in domains:
                                default_dom_idx = domains.index(current_dom_val) + 1  # +1 because 'All' is first
                            selected_domain_filter = st.selectbox("🌐 Filter by Domain:", ['All'] + domains, index=default_dom_idx, key='dom_filter_adv')
                    
                    # Add CSS to style selectboxes with dropdown arrow indicator and remove black bars
                    st.markdown("""
                    <style>
                    /* Remove black background from inputs */
                    .stSelectbox > div > div {
                        background-color: white !important;
                        border-color: #cbd5e1 !important;
                    }
                    .stSelectbox > div > div > div {
                        background-color: white !important;
                    }
                    /* Remove black search bars */
                    .stSelectbox input {
                        background-color: white !important;
                        color: #0f172a !important;
                        border-color: #cbd5e1 !important;
                    }
                    /* Ensure selectbox shows dropdown arrow */
                    .stSelectbox [data-baseweb="select"] {
                        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'%3E%3Cpath fill='%23666' d='M8 11L3 6h10z'/%3E%3C/svg%3E") !important;
                        background-repeat: no-repeat !important;
                        background-position: right 12px center !important;
                        padding-right: 40px !important;
                    }
                    .stSelectbox [data-baseweb="select"] > div {
                        background-color: white !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # Check if filters were changed from default/current flow
                    if selected_keyword_filter != 'All' and selected_keyword_filter != current_kw_val:
                        filters_changed = True
                    if selected_domain_filter != 'All' and selected_domain_filter != current_dom_val:
                        filters_changed = True
                
                # Reduce spacing - minimal margin instead of divider
                st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                
                # Apply filtering logic - RESTORE OLD CONSISTENT LOGIC FOR ALL
                # Always use find_default_flow logic - it finds best performing flow consistently
                if st.session_state.view_mode == 'basic' or (st.session_state.view_mode == 'advanced' and not filters_changed):
                    # Basic view OR Advanced default: Use find_default_flow (best performing)
                    st.session_state.default_flow = find_default_flow(campaign_df)
                    if st.session_state.default_flow:
                        current_flow = st.session_state.default_flow.copy()
                        # Get the actual row with max timestamp for this flow
                        final_filtered = campaign_df[
                            (campaign_df['keyword_term'] == current_flow.get('keyword_term', '')) &
                            (campaign_df['publisher_domain'] == current_flow.get('publisher_domain', ''))
                        ]
                        if 'serp_template_name' in campaign_df.columns:
                            final_filtered = final_filtered[final_filtered['serp_template_name'] == current_flow.get('serp_template_name', '')]
                        if len(final_filtered) > 0:
                            # Prefer views with conversions > 0, then clicks > 0, then impressions > 0
                            conv_positive = final_filtered[final_filtered['conversions'].apply(safe_float) > 0]
                            if len(conv_positive) > 0:
                                final_filtered = conv_positive
                            else:
                                clicks_positive = final_filtered[final_filtered['clicks'].apply(safe_float) > 0]
                                if len(clicks_positive) > 0:
                                    final_filtered = clicks_positive
                                else:
                                    imps_positive = final_filtered[final_filtered['impressions'].apply(safe_float) > 0]
                                    if len(imps_positive) > 0:
                                        final_filtered = imps_positive
                            
                            if 'timestamp' in final_filtered.columns:
                                best_view = final_filtered.loc[final_filtered['timestamp'].idxmax()]
                            else:
                                # Sort by conversions desc, then clicks desc, then impressions desc
                                final_filtered = final_filtered.sort_values(['conversions', 'clicks', 'impressions'], ascending=False)
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
                        <div style="font-size: 11px; color: #64748b; padding: 6px 0;">
                            <div><strong>Domain:</strong></div>
                            <div style="margin-left: 8px; margin-top: 2px;">{html.escape(str(domain))}</div>
                            <div style="margin-top: 4px;"><strong>URL:</strong></div>
                            <div style="margin-left: 8px; margin-top: 2px;">{html.escape(str(url)[:40])}{'...' if len(str(url)) > 40 else ''}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[2]:
                        keyword = current_flow.get('keyword_term', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 6px 0;">
                            <strong>Keyword:</strong> {html.escape(str(keyword))}
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[4]:
                        serp_url = SERP_BASE_URL + str(current_flow.get('serp_template_key', '')) if current_flow.get('serp_template_key') else 'N/A'
                        serp_key = current_flow.get('serp_template_key', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 6px 0;">
                            <div><strong>SERP URL:</strong></div>
                            <div style="margin-left: 8px; margin-top: 2px;">{html.escape(str(serp_url)[:50])}{'...' if len(str(serp_url)) > 50 else ''}</div>
                            <div style="margin-top: 4px;"><strong>SERP Key:</strong></div>
                            <div style="margin-left: 8px; margin-top: 2px;">{html.escape(str(serp_key))}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with desc_cols[6]:
                        landing_url = current_flow.get('reporting_destination_url', 'N/A')
                        st.markdown(f"""
                        <div style="font-size: 11px; color: #64748b; padding: 6px 0;">
                            <div><strong>Landing URL:</strong></div>
                            <div style="margin-left: 8px; margin-top: 2px;">{html.escape(str(landing_url)[:40])}{'...' if len(str(landing_url)) > 40 else ''}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Now create columns for the actual cards
                    stage_cols = st.columns([1, 0.05, 0.7, 0.05, 1, 0.05, 1], gap='small')
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
                            st.markdown('### <strong>📰 Publisher URL</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>📰 Publisher URL</strong>', unsafe_allow_html=True)
                    
                    if st.session_state.view_mode == 'basic':
                        st.caption(f"**Domain:** {current_dom}")
                        if current_url and pd.notna(current_url):
                            st.markdown(f"**URL:** [{current_url}]({current_url})", unsafe_allow_html=True)
                    
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
                                            except Exception:
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                            display_height = height
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
                                                    st.info("💡 Install Playwright for better rendering, or screenshots will use thum.io free tier (1000/month)")
                                                    st.markdown(f"[🔗 Open in new tab]({pub_url})")
                                        elif THUMIO_CONFIGURED:
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
                                            except Exception:
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(pub_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'pub_screenshot', pub_url, device_all, current_flow)
                                                            display_height = height
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
                    
                    if st.session_state.flow_layout == 'vertical' and card_col_right:
                        with card_col_right:
                            st.markdown("""
                            <div style="margin-bottom: 8px;">
                                <span style="font-weight: 600; color: #0f172a; font-size: 13px;">
                                    📰 Publisher URL Details
                                    <span title="Similarity scores measure how well different parts of your ad flow match: Keyword → Ad (ad matches keyword), Ad → Page (landing page matches ad), Keyword → Page (overall flow consistency)" style="cursor: help; color: #3b82f6; font-size: 12px; margin-left: 4px;">ℹ️</span>
                                </span>
                            </div>
                            """, unsafe_allow_html=True)
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
                
                # Stage 2: Creative
                if st.session_state.flow_layout == 'vertical':
                    st.markdown("<br>", unsafe_allow_html=True)
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
                        creative_card_left, creative_card_right = st.columns([0.5, 0.5])
                        with creative_card_left:
                            st.markdown('### <strong>🎨 Creative</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>🎨 Creative</strong>', unsafe_allow_html=True)
                    
                    creative_id = current_flow.get('creative_id', 'N/A')
                    creative_name = current_flow.get('creative_template_name', 'N/A')
                    creative_size = current_flow.get('creative_size', 'N/A')
                    
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
                                    if st.session_state.flow_layout == 'horizontal':
                                        st.components.v1.html(creative_html, height=400, scrolling=True)
                                    else:
                                        st.components.v1.html(creative_html, height=400, scrolling=True)
                                    
                                    if st.session_state.view_mode == 'advanced' or st.session_state.flow_layout == 'vertical':
                                        with st.expander("👁️ View Raw Ad Code"):
                                            st.code(raw_adcode[:500], language='html')
                                else:
                                    st.warning("⚠️ Empty creative JSON")
                            except Exception as e:
                                st.error(f"⚠️ Creative error: {str(e)[:100]}")
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
                    
                    if st.session_state.flow_layout == 'vertical' and creative_card_right:
                        with creative_card_right:
                            keyword = current_flow.get('keyword_term', 'N/A')
                            creative_size = current_flow.get('creative_size', 'N/A')
                            creative_name = current_flow.get('creative_template_name', 'N/A')
                            
                            st.markdown("**🎨 Creative Details**")
                            st.markdown(f"""
                            <div style="display: inline-flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: #64748b;"><strong>Keyword:</strong> {keyword}</span>
                                <span style="font-size: 12px; color: #64748b;"><strong>Size:</strong> {creative_size}</span>
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>Template:</strong> {creative_name}</span>' if creative_name != 'N/A' else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
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
                        stage_3_container = stage_cols[4]
                    else:
                        stage_3_container = st.container()
                    serp_card_left = None
                    serp_card_right = None
                
                with stage_3_container:
                    if st.session_state.flow_layout == 'vertical':
                        serp_card_left, serp_card_right = st.columns([0.6, 0.4])
                        with serp_card_left:
                            st.markdown('### <strong>📄 SERP</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>📄 SERP</strong>', unsafe_allow_html=True)
                    
                    serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
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
                                    if PLAYWRIGHT_AVAILABLE:
                                        with st.spinner("🔄 Using browser automation..."):
                                            page_html = capture_with_playwright(serp_url, device=device_all)
                                            if page_html:
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
                                                if THUMIO_CONFIGURED:
                                                    screenshot_url = get_screenshot_url(serp_url, device=device_all, full_page=False)
                                                    if screenshot_url:
                                                        screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                        preview_html = inject_unique_id(preview_html, 'serp_screenshot', serp_url, device_all, current_flow)
                                                        display_height = height
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
                    
                    if st.session_state.flow_layout == 'vertical' and serp_card_right:
                        with serp_card_right:
                            serp_name = current_flow.get('serp_template_name', current_flow.get('serp_template_id', 'N/A'))
                            
                            st.markdown("**📄 SERP Details**")
                            st.markdown(f"""
                            <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: #64748b;"><strong>Template:</strong> {serp_name}</span>
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>URL:</strong> <a href="{serp_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{serp_url[:50]}{"..." if len(serp_url) > 50 else ""}</a></span>' if serp_url else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
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
                
                # Stage 4: Landing Page
                if st.session_state.flow_layout == 'vertical':
                    st.markdown("<br>", unsafe_allow_html=True)
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
                        landing_card_left, landing_card_right = st.columns([0.6, 0.4])
                        with landing_card_left:
                            st.markdown('### <strong>🎯 Landing Page</strong>', unsafe_allow_html=True)
                    else:
                        st.markdown('### <strong>🎯 Landing Page</strong>', unsafe_allow_html=True)
                    
                    adv_url = current_flow.get('reporting_destination_url', '')
                    flow_clicks = safe_int(current_flow.get('clicks', 0))
                    
                    if st.session_state.view_mode == 'basic' and adv_url and pd.notna(adv_url) and st.session_state.flow_layout == 'horizontal':
                        st.markdown(f"**Landing URL:** [{adv_url}]({adv_url})", unsafe_allow_html=True)
                    
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
                                            except Exception:
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                            display_height = height
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
                                                    st.markdown(f"[🔗 Open in new tab]({adv_url})")
                                        elif THUMIO_CONFIGURED:
                                            try:
                                                screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                    display_height = height
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
                                            if THUMIO_CONFIGURED:
                                                try:
                                                    screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                    if screenshot_url:
                                                        screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                        preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                        preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                        display_height = height
                                                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                        st.caption("📸 Screenshot (thum.io)")
                                                    else:
                                                        st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                                except:
                                                    st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                            else:
                                                st.error(f"❌ HTML rendering failed: {str(html_error)[:100]}")
                                    else:
                                        if PLAYWRIGHT_AVAILABLE:
                                            try:
                                                with st.spinner("🔄 Trying browser automation..."):
                                                    page_html = capture_with_playwright(adv_url, device=device_all)
                                                    if page_html:
                                                        preview_html, height, _ = render_mini_device_preview(page_html, is_url=False, device=device_all)
                                                        preview_html = inject_unique_id(preview_html, 'landing_playwright', adv_url, device_all, current_flow)
                                                        display_height = height
                                                        st.components.v1.html(preview_html, height=display_height, scrolling=False)
                                                        if st.session_state.flow_layout != 'horizontal':
                                                            st.caption("🤖 Rendered via browser automation")
                                                    else:
                                                        raise Exception("Playwright returned empty HTML")
                                            except Exception:
                                                if THUMIO_CONFIGURED:
                                                    try:
                                                        screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                        if screenshot_url:
                                                            screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                            preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                            display_height = height
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
                                            try:
                                                screenshot_url = get_screenshot_url(adv_url, device=device_all, full_page=False)
                                                if screenshot_url:
                                                    screenshot_html = create_screenshot_html(screenshot_url, device=device_all, referer_domain=THUMIO_REFERER_DOMAIN)
                                                    preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device_all, use_srcdoc=True)
                                                    preview_html = inject_unique_id(preview_html, 'landing_screenshot', adv_url, device_all, current_flow)
                                                    display_height = height
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
                    
                    if st.session_state.flow_layout == 'vertical' and landing_card_right:
                        with landing_card_right:
                            adv_url = current_flow.get('reporting_destination_url', '')
                            
                            st.markdown("**🎯 Landing Page Details**")
                            st.markdown(f"""
                            <div style="display: inline-flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px;">
                                {f'<span style="font-size: 12px; color: #64748b;"><strong>Landing URL:</strong> <a href="{adv_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">{adv_url[:50]}{"..." if len(adv_url) > 50 else ""}</a></span>' if adv_url and pd.notna(adv_url) else ''}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if 'similarities' not in st.session_state or st.session_state.similarities is None:
                                if API_KEY:
                                    st.session_state.similarities = calculate_similarities(current_flow)
                                else:
                                    st.session_state.similarities = {}
                            
                            if 'similarities' in st.session_state and st.session_state.similarities:
                                render_similarity_score('kwd_to_page', st.session_state.similarities,
                                                       custom_title="Ad Copy → Landing Page Similarity",
                                                       tooltip_text="Measures overall flow consistency from keyword to landing page. Higher scores indicate better end-to-end alignment.")
                
                # Similarity Scores Section for Horizontal Layout
                if st.session_state.flow_layout == 'horizontal':
                    st.markdown("<div style='margin-top: 4px; margin-bottom: 4px;'></div>", unsafe_allow_html=True)
                    st.markdown("""
                        <h2 style="font-size: 28px; font-weight: 700; color: #0f172a; margin: 20px 0 15px 0;">
                            🧠 Similarity Scores
                        </h2>
                    """, unsafe_allow_html=True)
                    
                    if 'similarities' not in st.session_state or st.session_state.similarities is None:
                        if API_KEY:
                            st.session_state.similarities = calculate_similarities(current_flow)
                        else:
                            st.session_state.similarities = {}
                    
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
            
            else:
                st.warning("No data available for this campaign")
else:
    st.error("❌ Could not load data - Check FILE_A_ID and file sharing settings")
