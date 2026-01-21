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
        
        # Ensure ts is datetime (suppress warning)
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'], errors='coerce', format='mixed')
        
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
        # CRITICAL: When aggregating conversions, only sum rows where clicks > 0
        # When aggregating clicks, only sum rows where impressions > 0
        if sort_metric == 'conversions':
            # Only consider rows with conversions > 0 AND clicks > 0 for aggregation
            valid_df = df[(df['conversions'] > 0) & (df['clicks'] > 0)]
            if len(valid_df) == 0:
                # No valid conversion rows, fall back to clicks
                sort_metric = 'clicks'
                valid_df = df[(df['clicks'] > 0) & (df['impressions'] > 0)]
                if len(valid_df) == 0:
                    # No valid click rows, fall back to impressions
                    sort_metric = 'impressions'
                    valid_df = df[df['impressions'] > 0]
        elif sort_metric == 'clicks':
            # Only consider rows with clicks > 0 AND impressions > 0 for aggregation
            valid_df = df[(df['clicks'] > 0) & (df['impressions'] > 0)]
            if len(valid_df) == 0:
                # No valid click rows, fall back to impressions
                sort_metric = 'impressions'
                valid_df = df[df['impressions'] > 0]
        else:
            valid_df = df[df['impressions'] > 0]
        
        if len(valid_df) == 0:
            return None
        
        agg_df = valid_df.groupby(group_cols, dropna=False)[sort_metric].sum().reset_index()
        
        # Find THE BEST keyword+domain+SERP combination
        best_combo = agg_df.nlargest(1, sort_metric).iloc[0]
        
        # CRITICAL: Filter from valid_df (not df) to ensure we only get rows with valid metrics
        # valid_df already has the constraint: conversions > 0 AND clicks > 0 (or clicks > 0 AND impressions > 0, etc.)
        filtered = valid_df.copy()
        for col in group_cols:
            filtered = filtered[filtered[col] == best_combo[col]]
        
        # Step 2: From best keyword+domain+SERP combo, pick most recent view WITH the metric
        if len(filtered) == 0:
            # No valid rows for this combo - should not happen, but return None to be safe
            return None
        
        # CRITICAL: Double-check that we still have valid metrics after filtering
        # This ensures we never pick a row with conversions but 0 clicks
        if sort_metric == 'conversions':
            # Must have conversions > 0 AND clicks > 0
            filtered = filtered[(filtered['conversions'] > 0) & (filtered['clicks'] > 0)]
            if len(filtered) == 0:
                return None
        elif sort_metric == 'clicks':
            # Must have clicks > 0 AND impressions > 0
            filtered = filtered[(filtered['clicks'] > 0) & (filtered['impressions'] > 0)]
            if len(filtered) == 0:
                return None
        
        # IMPORTANT: Prefer rows with valid landing URLs when multiple options exist
        # Check if we have reporting_destination_url column
        has_landing_url_col = 'reporting_destination_url' in filtered.columns
        if has_landing_url_col:
            # Filter to rows with valid landing URLs first
            valid_landing = filtered[
                filtered['reporting_destination_url'].notna() & 
                (filtered['reporting_destination_url'] != '') &
                (filtered['reporting_destination_url'].astype(str).str.strip() != '')
            ]
            if len(valid_landing) > 0:
                filtered = valid_landing
        
        # Sort by timestamp (most recent) and metric (highest), then by supporting metrics
        if 'ts' in filtered.columns:
            if sort_metric == 'conversions':
                # Sort by conversions desc, then clicks desc, then timestamp desc
                filtered = filtered.sort_values(['conversions', 'clicks', 'ts'], ascending=[False, False, False])
            elif sort_metric == 'clicks':
                # Sort by clicks desc, then impressions desc, then timestamp desc
                filtered = filtered.sort_values(['clicks', 'impressions', 'ts'], ascending=[False, False, False])
            else:
                filtered = filtered.sort_values(['ts', sort_metric], ascending=[False, False])
        else:
            if sort_metric == 'conversions':
                filtered = filtered.sort_values(['conversions', 'clicks'], ascending=[False, False])
            elif sort_metric == 'clicks':
                filtered = filtered.sort_values(['clicks', 'impressions'], ascending=[False, False])
            else:
                filtered = filtered.sort_values(sort_metric, ascending=False)
        
        # Return the best row
        return filtered.iloc[0].to_dict()
    except Exception as e:
        # Use print instead of st.error to avoid import issues
        # st.error will be called by the caller if needed
        print(f"Error finding default flow: {str(e)}")
        return None
