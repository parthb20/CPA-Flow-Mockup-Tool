#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
Run this before running the main app to catch import errors
"""

print("Testing imports...")

try:
    import streamlit as st
    print("✅ streamlit")
except Exception as e:
    print(f"❌ streamlit: {e}")
    exit(1)

try:
    import pandas as pd
    print("✅ pandas")
except Exception as e:
    print(f"❌ pandas: {e}")
    exit(1)

try:
    import requests
    print("✅ requests")
except Exception as e:
    print(f"❌ requests: {e}")
    exit(1)

try:
    from bs4 import BeautifulSoup
    print("✅ beautifulsoup4")
except Exception as e:
    print(f"❌ beautifulsoup4: {e}")
    exit(1)

try:
    from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
    print("✅ src.config")
except Exception as e:
    print(f"❌ src.config: {e}")
    exit(1)

try:
    from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
    print("✅ src.data_loader")
except Exception as e:
    print(f"❌ src.data_loader: {e}")
    exit(1)

try:
    from src.utils import safe_float, safe_int
    print("✅ src.utils")
except Exception as e:
    print(f"❌ src.utils: {e}")
    exit(1)

try:
    from src.flow_analysis import find_default_flow
    print("✅ src.flow_analysis")
except Exception as e:
    print(f"❌ src.flow_analysis: {e}")
    exit(1)

try:
    from src.similarity import calculate_similarities
    print("✅ src.similarity")
except Exception as e:
    print(f"❌ src.similarity: {e}")
    exit(1)

try:
    from src.serp import generate_serp_mockup
    print("✅ src.serp")
except Exception as e:
    print(f"❌ src.serp: {e}")
    exit(1)

try:
    from src.renderers import (
        render_mini_device_preview,
        render_similarity_score,
        inject_unique_id,
        create_screenshot_html,
        parse_creative_html
    )
    print("✅ src.renderers")
except Exception as e:
    print(f"❌ src.renderers: {e}")
    exit(1)

try:
    from src.screenshot import get_screenshot_url, capture_with_playwright
    print("✅ src.screenshot")
except Exception as e:
    print(f"❌ src.screenshot: {e}")
    exit(1)

try:
    from src.ui_components import render_flow_combinations_table, render_what_is_flow_section, render_selected_flow_display
    print("✅ src.ui_components")
except Exception as e:
    print(f"❌ src.ui_components: {e}")
    exit(1)

try:
    from src.filters import render_advanced_filters, apply_flow_filtering
    print("✅ src.filters")
except Exception as e:
    print(f"❌ src.filters: {e}")
    exit(1)

try:
    from src.flow_display import render_flow_journey
    print("✅ src.flow_display")
except Exception as e:
    print(f"❌ src.flow_display: {e}")
    exit(1)

print("\n✅ All imports successful! App should run correctly.")
print("\nTo run the app:")
print("  streamlit run cpa_flow_mockup.py")
