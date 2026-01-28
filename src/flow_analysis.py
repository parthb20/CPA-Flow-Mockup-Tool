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
        
        # Determine uniqueness columns based on data variety
        # All flow elements: keyword, domain, publisher_url, serp, creative, landing_page
        unique_cols = ['keyword_term', 'publisher_domain', 'publisher_url']
        
        # Add SERP to uniqueness
        if 'Serp_URL' in df.columns:
            unique_cols.append('Serp_URL')
        elif include_serp_filter:
            if 'serp_template_name' in df.columns:
                unique_cols.append('serp_template_name')
            elif 'serp_template_id' in df.columns:
                unique_cols.append('serp_template_id')
        
        # Add Creative (Ad_ID) to uniqueness
        if 'Ad_ID' in df.columns:
            unique_cols.append('Ad_ID')
        
        # Add Landing Page (Destination_Url) to uniqueness
        if 'Destination_Url' in df.columns:
            unique_cols.append('Destination_Url')
        
        # Check which columns have only 1 unique value (are filtered/constant)
        constant_cols = []
        for col in unique_cols[:]:  # iterate over copy
            if col in df.columns and df[col].nunique() == 1:
                constant_cols.append(col)
                unique_cols.remove(col)  # Remove from uniqueness check since it's constant
        
        # Group by unique_cols to find best combinations
        if len(unique_cols) > 0:
            agg_df = df.groupby(unique_cols, dropna=False).agg({
                'conversions': 'sum',
                'clicks': 'sum',
                'impressions': 'sum'
            }).reset_index()
            
            # Calculate CVR for ranking
            agg_df['cvr'] = agg_df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
            
            # Sort: converting combos first (conversions > 0), then by clicks desc
            agg_df = agg_df.sort_values(['conversions', 'clicks'], ascending=[False, False])
        else:
            # All columns are constant (unlikely but handle it)
            agg_df = pd.DataFrame()
        
        # Step 2: For each unique combination, pick best view_id
        flows = []
        seen_combinations = set()
        
        if len(agg_df) > 0:
            for _, combo in agg_df.iterrows():
                if len(flows) >= n:
                    break
                
                # Create combination key
                combo_key = tuple(str(combo.get(col, '')) for col in unique_cols)
                
                if combo_key in seen_combinations:
                    continue
                
                # Filter to this combination
                combo_df = df.copy()
                for col in unique_cols:
                    combo_df = combo_df[combo_df[col] == combo[col]]
                
                if len(combo_df) == 0:
                    continue
                
                # Within this combo, prioritize: conversions > 0 first, then high clicks, then latest timestamp
                sort_cols = ['conversions', 'clicks', 'ts'] if 'ts' in combo_df.columns else ['conversions', 'clicks']
                combo_df = combo_df.sort_values(sort_cols, ascending=False)
                
                # Get the best view_id (highest converting, latest timestamp)
                if len(combo_df) > 0:
                    row = combo_df.iloc[0]
                    seen_combinations.add(combo_key)
                    flow = row.to_dict()
                    flow['flow_rank'] = len(flows) + 1
                    flows.append(flow)
        else:
            # Fallback: just pick top N by conversions, clicks, timestamp
            sort_cols = ['conversions', 'clicks', 'ts'] if 'ts' in df.columns else ['conversions', 'clicks']
            df_sorted = df.sort_values(sort_cols, ascending=False)
            for i, row in enumerate(df_sorted.head(n).iterrows()):
                flow = row[1].to_dict()
                flow['flow_rank'] = i + 1
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
        
        # Determine uniqueness columns based on data variety
        # All flow elements: keyword, domain, publisher_url, serp, creative, landing_page
        unique_cols = ['keyword_term', 'publisher_domain', 'publisher_url']
        
        # Add SERP to uniqueness
        if 'Serp_URL' in df.columns:
            unique_cols.append('Serp_URL')
        elif include_serp_filter:
            if 'serp_template_name' in df.columns:
                unique_cols.append('serp_template_name')
            elif 'serp_template_id' in df.columns:
                unique_cols.append('serp_template_id')
        
        # Add Creative (Ad_ID) to uniqueness
        if 'Ad_ID' in df.columns:
            unique_cols.append('Ad_ID')
        
        # Add Landing Page (Destination_Url) to uniqueness
        if 'Destination_Url' in df.columns:
            unique_cols.append('Destination_Url')
        
        # Check which columns have only 1 unique value (are filtered/constant)
        constant_cols = []
        for col in unique_cols[:]:  # iterate over copy
            if col in df.columns and df[col].nunique() == 1:
                constant_cols.append(col)
                unique_cols.remove(col)  # Remove from uniqueness check since it's constant
        
        # CRITICAL: Filter for 0-conversions FIRST before any grouping
        zero_conv_df = df[
            (df['conversions'] == 0) | 
            (df['conversions'] == 0.0) |
            (df['conversions'].isna())
        ].copy()
        
        if len(zero_conv_df) == 0:
            return []
        
        # Calculate CVR and CTR for sorting
        zero_conv_df['cvr'] = zero_conv_df.apply(lambda row: row['conversions'] / row['clicks'] if row['clicks'] > 0 else 0, axis=1)
        zero_conv_df['ctr'] = zero_conv_df.apply(lambda row: row['clicks'] / row['impressions'] if row['impressions'] > 0 else 0, axis=1)
        
        # Sort by: CVR asc (lowest first), CTR asc (lowest first), timestamp desc (latest first)
        sort_cols = ['cvr', 'ctr', 'ts'] if 'ts' in zero_conv_df.columns else ['cvr', 'ctr']
        sort_order = [True, True, False] if 'ts' in zero_conv_df.columns else [True, True]
        zero_conv_df = zero_conv_df.sort_values(sort_cols, ascending=sort_order)
        
        # Step 2: Pick N flows with unique combinations
        flows = []
        seen_combinations = set()
        
        if len(unique_cols) > 0:
            for _, row in zero_conv_df.iterrows():
                if len(flows) >= n:
                    break
                
                # Create combination key from unique columns
                combo_key = tuple(str(row.get(col, '')) for col in unique_cols)
                
                # Skip if we've already picked a flow with this combination
                if combo_key in seen_combinations:
                    continue
                
                # VERIFY: conversions must be exactly 0
                conv_val = row.get('conversions', 0)
                if not (conv_val == 0 or conv_val == 0.0 or pd.isna(conv_val)):
                    continue
                
                # Add this flow
                seen_combinations.add(combo_key)
                flow = row.to_dict()
                flow['flow_rank'] = len(flows) + 1
                flows.append(flow)
        else:
            # Fallback: No varying columns, just pick top N by timestamp
            for i, row in enumerate(zero_conv_df.head(n).iterrows()):
                conv_val = row[1].get('conversions', 0)
                if conv_val == 0 or conv_val == 0.0 or pd.isna(conv_val):
                    flow = row[1].to_dict()
                    flow['flow_rank'] = i + 1
                    flows.append(flow)
        
        return flows
    except Exception as e:
        print(f"Error finding worst flows: {str(e)}")
        return []
