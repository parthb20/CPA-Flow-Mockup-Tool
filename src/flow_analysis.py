# -*- coding: utf-8 -*-
"""
Flow analysis and selection functions
"""

import streamlit as st
import pandas as pd
from urllib.parse import urlparse
from src.utils import safe_float


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
            metric_positive = filtered[filtered[sort_metric] > 0]
            if len(metric_positive) > 0:
                filtered = metric_positive
            
            # Sort by timestamp (most recent) and metric (highest)
            if 'ts' in filtered.columns:
                filtered = filtered.sort_values(['ts', sort_metric], ascending=[False, False])
            else:
                filtered = filtered.sort_values(sort_metric, ascending=False)
            
            # Return the best row
            return filtered.iloc[0].to_dict()
        
        return None
    except Exception as e:
        # Use print instead of st.error to avoid import issues
        # st.error will be called by the caller if needed
        print(f"Error finding default flow: {str(e)}")
        return None
