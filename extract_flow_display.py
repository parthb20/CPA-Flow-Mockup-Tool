# Temporary script to extract flow display section
with open('cpa_flow_mockup.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extract lines 887-1867 (0-indexed: 886-1866)
flow_section = ''.join(lines[886:1867])

# Create the module file
header = '''# -*- coding: utf-8 -*-
"""
Flow Display Module
Renders the complete Flow Journey with all 4 stages
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import html

from src.config import SERP_BASE_URL
from src.utils import safe_int
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


def render_flow_journey(current_flow, campaign_df, API_KEY, PLAYWRIGHT_AVAILABLE, THUMIO_CONFIGURED, THUMIO_REFERER_DOMAIN):
    """Render the complete Flow Journey with all 4 stages"""
'''

# Remove the leading indentation (16 spaces) from each line
flow_section_unindented = '\n'.join([line[16:] if len(line) > 16 and line[:16] == '                ' else line.rstrip() for line in flow_section.split('\n')])

with open('src/flow_display.py', 'w', encoding='utf-8') as out:
    out.write(header)
    out.write(flow_section_unindented)

print('Created src/flow_display.py')
