# -*- coding: utf-8 -*-
"""
UI Components for CPA Flow Analysis Tool
Handles table rendering, selected flow display, and info sections
"""

import streamlit as st
import pandas as pd
import html


def render_flow_combinations_table(campaign_df):
    """Render the Flow Combinations Overview table with filters"""
    if 'publisher_domain' not in campaign_df.columns or 'keyword_term' not in campaign_df.columns:
        st.warning("Could not generate table - missing required columns")
        return
    
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
    
    # Create styled table HTML
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
        
        # Determine CTR color
        if ctr_val >= weighted_avg_ctr:
            ctr_bg = "#dcfce7"
            ctr_color = "#166534"
        else:
            ctr_bg = "#fee2e2"
            ctr_color = "#991b1b"
        
        # Determine CVR color
        if cvr_val >= weighted_avg_cvr:
            cvr_bg = "#dcfce7"
            cvr_color = "#166534"
        else:
            cvr_bg = "#fee2e2"
            cvr_color = "#991b1b"
        
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
    
    # Calculate dynamic height
    num_rows = len(agg_df)
    table_height = max(200, 80 + (num_rows * 45))
    
    # Render table
    st.components.v1.html(table_html, height=table_height, scrolling=False)


def render_what_is_flow_section():
    """Render the 'What is a Flow?' explanation section"""
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


def render_selected_flow_display(single_view, flow_imps, flow_clicks, flow_convs, flow_ctr, flow_cvr):
    """Render the Selected Flow display with performance metrics"""
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
