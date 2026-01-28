# -*- coding: utf-8 -*-
"""
Flow analysis and selection functions
"""

import streamlit as st
import pandas as pd
from urllib.parse import urlparse
from src.utils import safe_float
from datetime import datetime, timedelta


def parse_ts_to_datetime(ts_value):
    """Convert ts format (YYYYMMDDHH) to datetime object
    Example: 2026010504 -> datetime(2026, 1, 5, 4)
    """
    try:
        ts_str = str(int(ts_value))
        if len(ts_str) == 10:
            year = int(ts_str[0:4])
            month = int(ts_str[4:6])
            day = int(ts_str[6:8])
            hour = int(ts_str[8:10])
            return datetime(year, month, day, hour)
    except:
        pass
    return None


def filter_by_date_range(df, start_date, start_hour, end_date, end_hour):
    """Filter dataframe by date range using ts column
    Args:
        df: DataFrame with 'ts' column (format: YYYYMMDDHH)
        start_date: datetime.date object
        start_hour: int (0-23)
        end_date: datetime.date object
        end_hour: int (0-23)
    Returns:
        Filtered DataFrame
    """
    if 'ts' not in df.columns:
        return df
    
    # Create start and end datetime
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(hour=start_hour)
    end_dt = datetime.combine(end_date, datetime.min.time()).replace(hour=end_hour)
    
    # Parse ts column and filter
    df = df.copy()
    df['_temp_dt'] = df['ts'].apply(parse_ts_to_datetime)
    filtered = df[(df['_temp_dt'] >= start_dt) & (df['_temp_dt'] <= end_dt)]
    filtered = filtered.drop(columns=['_temp_dt'])
    
    return filtered


def filter_by_threshold(df, entity_col, threshold_pct=5.0):
    """Filter dataframe to only include entities with >= threshold% of total data
    Args:
        df: DataFrame
        entity_col: Column name (e.g., 'keyword_term', 'publisher_domain')
        threshold_pct: Minimum percentage (default 5.0%)
    Returns:
        Filtered DataFrame
    """
    if entity_col not in df.columns:
        return df
    
    # Count rows per entity
    entity_counts = df[entity_col].value_counts()
    total_rows = len(df)
    
    # Calculate percentage
    entity_pcts = (entity_counts / total_rows) * 100
    
    # Filter entities >= threshold
    valid_entities = entity_pcts[entity_pcts >= threshold_pct].index.tolist()
    
    # Filter dataframe
    filtered = df[df[entity_col].isin(valid_entities)]
    
    return filtered


def find_default_flow(df):
    """Find the best performing flow - prioritize conversions, then clicks, then impressions"""
    try:
        # Make a copy to avoid SettingWithCopyWarning
        df = df.copy()
        
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
            # Last resort: return ANY row if available (even with 0 metrics)
            if len(df) > 0:
                return df.iloc[0].to_dict()
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


def find_top_n_best_flows(df, n=5, include_serp_filter=False):
    """Find top N best performing flows
    Args:
        df: DataFrame with flow data
        n: Number of top flows to return (default 5)
        include_serp_filter: If True, include serp_template in grouping
    Returns:
        List of dictionaries, each representing a flow (sorted best to worst)
    """
    try:
        df = df.copy()
        
        # Convert numeric columns
        df['conversions'] = df['conversions'].apply(safe_float)
        df['impressions'] = df['impressions'].apply(safe_float)
        df['clicks'] = df['clicks'].apply(safe_float)
        
        # Calculate CVR for sorting
        df['cvr'] = df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
        
        # Ensure ts is datetime
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'], errors='coerce', format='mixed')
        
        # Get domain if not present
        if 'publisher_domain' not in df.columns:
            if 'publisher_url' in df.columns:
                df['publisher_domain'] = df['publisher_url'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
            elif 'Serp_URL' in df.columns:
                df['publisher_domain'] = df['Serp_URL'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
        
        # Build grouping columns
        group_cols = ['keyword_term', 'publisher_domain']
        if include_serp_filter:
            if 'serp_template_name' in df.columns:
                group_cols.append('serp_template_name')
            elif 'serp_template_id' in df.columns:
                group_cols.append('serp_template_id')
        
        # Filter to rows with conversions > 0 and clicks > 0
        valid_df = df[(df['conversions'] > 0) & (df['clicks'] > 0)]
        
        if len(valid_df) == 0:
            # Fall back to clicks > 0
            valid_df = df[df['clicks'] > 0]
            if len(valid_df) == 0:
                return []
        
        # Group by keyword + domain (+ serp if enabled) and calculate metrics
        agg_df = valid_df.groupby(group_cols, dropna=False).agg({
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()
        
        # Calculate CVR for each combination
        agg_df['cvr'] = agg_df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
        
        # Sort by CVR desc, then conversions desc, then clicks desc
        agg_df = agg_df.sort_values(['cvr', 'conversions', 'clicks'], ascending=[False, False, False])
        
        # Get top N combinations
        top_combos = agg_df.head(n)
        
        # For each combo, get the most recent view with valid metrics
        flows = []
        for _, combo in top_combos.iterrows():
            filtered = valid_df.copy()
            for col in group_cols:
                filtered = filtered[filtered[col] == combo[col]]
            
            if len(filtered) > 0:
                # Sort by timestamp desc
                if 'ts' in filtered.columns:
                    filtered = filtered.sort_values('ts', ascending=False)
                
                # Get most recent
                flow = filtered.iloc[0].to_dict()
                flows.append(flow)
        
        return flows
    except Exception as e:
        print(f"Error finding top N flows: {str(e)}")
        return []


def find_top_n_worst_flows(df, n=5, include_serp_filter=False):
    """Find top N worst performing flows
    Logic: Lowest CVR among keyword-domain combinations,
           choose latest view_id with highest timestamp
    Args:
        df: DataFrame with flow data
        n: Number of worst flows to return (default 5)
        include_serp_filter: If True, include serp_template in grouping
    Returns:
        List of dictionaries, each representing a flow (sorted worst to best)
    """
    try:
        df = df.copy()
        
        # Convert numeric columns
        df['conversions'] = df['conversions'].apply(safe_float)
        df['impressions'] = df['impressions'].apply(safe_float)
        df['clicks'] = df['clicks'].apply(safe_float)
        
        # Calculate CVR
        df['cvr'] = df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
        
        # Ensure ts is datetime
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'], errors='coerce', format='mixed')
        
        # Get domain if not present
        if 'publisher_domain' not in df.columns:
            if 'publisher_url' in df.columns:
                df['publisher_domain'] = df['publisher_url'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
            elif 'Serp_URL' in df.columns:
                df['publisher_domain'] = df['Serp_URL'].apply(lambda x: urlparse(str(x)).netloc if pd.notna(x) else '')
        
        # Build grouping columns
        group_cols = ['keyword_term', 'publisher_domain']
        if include_serp_filter:
            if 'serp_template_name' in df.columns:
                group_cols.append('serp_template_name')
            elif 'serp_template_id' in df.columns:
                group_cols.append('serp_template_id')
        
        # Group by keyword + domain (+ serp if enabled) and calculate CVR
        agg_df = df.groupby(group_cols, dropna=False).agg({
            'conversions': 'sum',
            'clicks': 'sum',
            'impressions': 'sum'
        }).reset_index()
        
        # Calculate CVR for each combination
        agg_df['cvr'] = agg_df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
        
        # Sort by CVR ascending (lowest CVR first), then by clicks descending
        agg_df = agg_df.sort_values(['cvr', 'clicks'], ascending=[True, False])
        
        # Get worst combinations (up to n*10 to ensure we find enough 0-conversion flows)
        worst_combos = agg_df.head(n * 10)
        
        # For each combo, GET ONLY 0 conversion rows (skip if none exist)
        flows = []
        for _, combo in worst_combos.iterrows():
            if len(flows) >= n:
                break
                
            filtered = df.copy()
            for col in group_cols:
                filtered = filtered[filtered[col] == combo[col]]
            
            if len(filtered) > 0:
                # ONLY get rows with 0 conversions - ULTRA STRICT CHECK
                zero_conv = filtered[
                    (filtered['conversions'] == 0) | 
                    (filtered['conversions'] == 0.0) |
                    (filtered['conversions'].isna()) |
                    (filtered['conversions'] < 0.01)  # Handle floating point
                ]
                
                if len(zero_conv) > 0:
                    # Sort by timestamp desc (latest first)
                    if 'ts' in zero_conv.columns:
                        zero_conv = zero_conv.sort_values('ts', ascending=False)
                    
                    # Triple check conversions is truly 0
                    flow = zero_conv.iloc[0].to_dict()
                    conv_val = flow.get('conversions', 0)
                    if conv_val == 0 or conv_val == 0.0 or pd.isna(conv_val) or conv_val < 0.01:
                        flows.append(flow)
                # If no 0 conversion rows, skip this combo entirely
        
        return flows
    except Exception as e:
        print(f"Error finding worst flows: {str(e)}")
        return []
