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
    
    # Table filter controls - COMPACT
    table_col1, table_col2, table_col3, spacer = st.columns([1, 1, 1.5, 2])
    with table_col1:
        table_filter = st.selectbox("Filter:", ['Best', 'Worst', 'Overall'], index=0, key='table_filter')
    with table_col2:
        table_count = st.selectbox("Rows:", [5, 10, 15], index=1, key='table_count')
    with table_col3:
        table_sort = st.selectbox("Sort:", ['Impressions', 'Clicks', 'Conversions', 'CTR', 'CVR'], index=0, key='table_sort')
    
    # Calculate OVERALL stats from FULL campaign data (before filtering)
    overall_imps_full = campaign_df['impressions'].sum()
    overall_clicks_full = campaign_df['clicks'].sum()
    overall_convs_full = campaign_df['conversions'].sum()
    overall_ctr_full = (overall_clicks_full / overall_imps_full * 100) if overall_imps_full > 0 else 0
    overall_cvr_full = (overall_convs_full / overall_clicks_full * 100) if overall_clicks_full > 0 else 0
    
    # Aggregate by domain + keyword
    agg_df = campaign_df.groupby(['publisher_domain', 'keyword_term']).agg({
        'impressions': 'sum',
        'clicks': 'sum',
        'conversions': 'sum'
    }).reset_index()
    
    agg_df['CTR'] = agg_df.apply(lambda x: (x['clicks']/x['impressions']*100) if x['impressions']>0 else 0, axis=1)
    agg_df['CVR'] = agg_df.apply(lambda x: (x['conversions']/x['clicks']*100) if x['clicks']>0 else 0, axis=1)
    
    # Calculate weighted averages for CTR and CVR (for coloring)
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
    
    # Create styled table HTML - RESPONSIVE
    table_html = """
    <style>
    .flow-table {
        width: 100%;
        border-collapse: collapse;
        background: white !important;
        margin: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem) 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        border: 1px solid #e2e8f0;
    }
    .flow-table th {
        background: #f8fafc !important;
        color: #000000 !important;
        font-weight: 700;
        padding: clamp(0.625rem, 0.5rem + 0.6vw, 0.75rem);
        text-align: left;
        border-bottom: 2px solid #cbd5e1;
        border-right: 1px solid #e2e8f0;
        font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);
    }
    .flow-table th:last-child {
        border-right: none;
    }
    .flow-table td {
        padding: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem) clamp(0.625rem, 0.5rem + 0.6vw, 0.75rem);
        border-bottom: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        color: #000000 !important;
        background: white !important;
        font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);
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
    
    # Add Overall Stats row at the bottom - using FULL campaign data
    table_html += f"""
        <tr style="background: #f1f5f9 !important; font-weight: 700; border-top: 2px solid #cbd5e1;">
            <td colspan="2" style="background: #f1f5f9 !important; color: #000000 !important; font-weight: 700;">OVERALL</td>
            <td style="background: #f1f5f9 !important; color: #000000 !important; font-weight: 700;">{int(overall_imps_full):,}</td>
            <td style="background: #f1f5f9 !important; color: #000000 !important; font-weight: 700;">{int(overall_clicks_full):,}</td>
            <td style="background: #f1f5f9 !important; color: #000000 !important; font-weight: 700;">{int(overall_convs_full):,}</td>
            <td style="background: #f1f5f9 !important; color: #1e40af !important; font-weight: 700;">{overall_ctr_full:.2f}%</td>
            <td style="background: #f1f5f9 !important; color: #1e40af !important; font-weight: 700;">{overall_cvr_full:.2f}%</td>
        </tr>
    </tbody>
    </table>
    """
    
    # Calculate dynamic height - cap at 500px to show overall stats
    num_rows = len(agg_df) + 1  # +1 for overall row
    table_height = min(500, max(250, 80 + (num_rows * 45)))
    
    # Render table (Overall stats are already in the table as a row)
    st.components.v1.html(table_html, height=table_height, scrolling=False)


def render_what_is_flow_section():
    """Render the 'What is a Flow?' explanation section - DISABLED"""
    pass  # Removed per user request


def render_api_key_info_section():
    """Render the API key information section explaining Fast Router setup"""
    st.markdown("""
    <div style="background: #fff7ed; padding: 16px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 8px 0;">
        <h3 style="font-size: 20px; font-weight: 700; color: #0f172a; margin: 0 0 12px 0;">🔑 API Key Setup for Similarity Calculations</h3>
        <p style="font-size: 15px; color: #334155; margin: 8px 0; line-height: 1.6;">
            <strong style="font-weight: 700; color: #0f172a;">Why is an API key needed?</strong> The similarity scores (Keyword → Ad Copy, Ad Copy → Landing Page, Keyword → Landing Page) are calculated using AI models via Fast Router. Without an API key, similarity scores will not be displayed.
        </p>
        <div style="margin-top: 16px;">
            <h4 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 8px 0;">Fast Router Setup Steps:</h4>
            <ol style="font-size: 14px; color: #334155; margin: 8px 0; padding-left: 20px; line-height: 1.8;">
                <li><strong style="font-weight: 600;">Request access:</strong> Get invited and accept the invitation</li>
                <li><strong style="font-weight: 600;">Get added to project:</strong> Join "Team Akshay" project</li>
                <li><strong style="font-weight: 600;">Install package:</strong> <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px;">pip install openai</code></li>
                <li><strong style="font-weight: 600;">Add API key:</strong> Add your Fast Router API key to Streamlit secrets (key name: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px;">FASTROUTER_API_KEY</code> or <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px;">OPENAI_API_KEY</code>)</li>
            </ol>
        </div>
        <div style="margin-top: 16px; background: #f8fafc; padding: 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
            <h4 style="font-size: 15px; font-weight: 700; color: #0f172a; margin: 0 0 8px 0;">Sample Code (with request tags):</h4>
            <pre style="background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; line-height: 1.5; margin: 0;"><code>from openai import OpenAI

client = OpenAI(
    base_url="https://go.fastrouter.ai/api/v1",
    api_key="sk-v1-YOUR_ACTUAL_API_KEY_HERE",
)

completion = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Your prompt"}],
    extra_body={"request_tags": ["&lt;BT&gt;/&lt;project_name&gt;"]}
)</code></pre>
            <p style="font-size: 13px; color: #64748b; margin: 8px 0 0 0;">
                <strong>Note:</strong> Request tags (e.g., <code style="background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 12px;">BT1/keyword_review</code>) are required to track usage by BT and project.
            </p>
        </div>
        <p style="font-size: 13px; color: #64748b; margin: 12px 0 0 0; font-style: italic;">
            Key name format: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px;">Parth Bhatt_Key - 17122025232034</code>
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_selected_flow_display(single_view, flow_imps, flow_clicks, flow_convs, flow_ctr, flow_cvr):
    """Render the Selected Flow display with performance metrics - RESPONSIVE"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-left: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem) solid #3b82f6; padding: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem); border-radius: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); margin: 0;">
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: clamp(0.625rem, 0.5rem + 0.6vw, 0.75rem);">
            <div><strong style="color: #64748b; font-size: clamp(0.8125rem, 0.75rem + 0.3vw, 0.9375rem); font-weight: 700;">Impressions</strong><div style="font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem); font-weight: 900; color: #0f172a;">{impressions:,}</div></div>
            <div><strong style="color: #64748b; font-size: clamp(0.8125rem, 0.75rem + 0.3vw, 0.9375rem); font-weight: 700;">Clicks</strong><div style="font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem); font-weight: 900; color: #0f172a;">{clicks:,}</div></div>
            <div><strong style="color: #64748b; font-size: clamp(0.8125rem, 0.75rem + 0.3vw, 0.9375rem); font-weight: 700;">Conversions</strong><div style="font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem); font-weight: 900; color: #0f172a;">{conversions:,}</div></div>
            <div><strong style="color: #64748b; font-size: clamp(0.8125rem, 0.75rem + 0.3vw, 0.9375rem); font-weight: 700;">CTR</strong><div style="font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem); font-weight: 900; color: #0f172a;">{ctr:.2f}%</div></div>
            <div><strong style="color: #64748b; font-size: clamp(0.8125rem, 0.75rem + 0.3vw, 0.9375rem); font-weight: 700;">CVR</strong><div style="font-size: clamp(1.25rem, 1.1rem + 0.75vw, 1.375rem); font-weight: 900; color: #0f172a;">{cvr:.2f}%</div></div>
        </div>
    </div>
    """.format(
        impressions=flow_imps,
        clicks=flow_clicks,
        conversions=flow_convs,
        ctr=flow_ctr,
        cvr=flow_cvr
    ), unsafe_allow_html=True)
