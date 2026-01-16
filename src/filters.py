# -*- coding: utf-8 -*-
"""
Filter Logic for CPA Flow Analysis Tool
Handles flow filtering and selection logic
"""

import streamlit as st
import pandas as pd
from src.flow_analysis import find_default_flow
from src.utils import safe_float, safe_int


def render_advanced_filters(campaign_df, current_flow):
    """Render advanced mode filters and return filter state"""
    filters_changed = False
    
    if st.session_state.view_mode == 'advanced':
        # Message above filters
        st.info("✨ Use filters below to change flow")
        
        # Single unified filter - searchable selectbox
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
            else:
                selected_domain_filter = 'All'
        
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
        /* Ensure selectbox shows dropdown arrow and is clickable */
        .stSelectbox [data-baseweb="select"] {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'%3E%3Cpath fill='%23666' d='M8 11L3 6h10z'/%3E%3C/svg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: right 12px center !important;
            padding-right: 40px !important;
            cursor: pointer !important;
        }
        .stSelectbox [data-baseweb="select"] > div {
            background-color: white !important;
            cursor: pointer !important;
        }
        /* Make the entire selectbox area clickable */
        .stSelectbox > div {
            cursor: pointer !important;
        }
        .stSelectbox > div > div {
            cursor: pointer !important;
            pointer-events: auto !important;
        }
        /* Make entire selectbox clickable - override any blocking */
        .stSelectbox [data-baseweb="select"] {
            pointer-events: auto !important;
            cursor: pointer !important;
        }
        .stSelectbox [data-baseweb="select"] * {
            pointer-events: auto !important;
            cursor: pointer !important;
        }
        /* Ensure the dropdown trigger button is clickable */
        .stSelectbox [data-baseweb="select"] button {
            pointer-events: auto !important;
            cursor: pointer !important;
            z-index: 9999 !important;
            position: relative !important;
        }
        /* Make the entire selectbox container clickable */
        .stSelectbox {
            pointer-events: auto !important;
            cursor: pointer !important;
        }
        .stSelectbox > div {
            pointer-events: auto !important;
            cursor: pointer !important;
        }
        /* Target the actual clickable area */
        .stSelectbox [data-baseweb="popover"] {
            pointer-events: auto !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Check if filters were changed from default/current flow
        if selected_keyword_filter != 'All' and selected_keyword_filter != current_kw_val:
            filters_changed = True
        if selected_domain_filter != 'All' and selected_domain_filter != current_dom_val:
            filters_changed = True
        
        return filters_changed, selected_keyword_filter, selected_domain_filter
    
    return False, 'All', 'All'


def apply_flow_filtering(campaign_df, current_flow, filters_changed, selected_keyword_filter, selected_domain_filter):
    """Apply filtering logic and return updated flow and filtered dataframe"""
    final_filtered = pd.DataFrame()
    
    # Apply filtering logic
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
    
    return current_flow, final_filtered
