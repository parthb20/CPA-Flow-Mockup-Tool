#!/usr/bin/env python3
"""
Test script to simulate app startup and catch errors
"""

import sys
import traceback

print("Testing app startup...")
print("=" * 60)

try:
    print("1. Testing imports...")
    import streamlit as st
    print("   [OK] streamlit imported")
    
    import pandas as pd
    print("   [OK] pandas imported")
    
    print("\n2. Testing module imports...")
    from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
    print("   [OK] src.config imported")
    
    from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
    print("   [OK] src.data_loader imported")
    
    from src.utils import safe_float, safe_int
    print("   [OK] src.utils imported")
    
    from src.flow_analysis import find_default_flow
    print("   [OK] src.flow_analysis imported")
    
    from src.similarity import calculate_similarities
    print("   [OK] src.similarity imported")
    
    from src.serp import generate_serp_mockup
    print("   [OK] src.serp imported")
    
    from src.renderers import (
        render_mini_device_preview,
        render_similarity_score,
        inject_unique_id,
        create_screenshot_html,
        parse_creative_html
    )
    print("   [OK] src.renderers imported")
    
    from src.screenshot import get_screenshot_url, capture_with_playwright
    print("   [OK] src.screenshot imported")
    
    from src.ui_components import render_flow_combinations_table, render_what_is_flow_section, render_selected_flow_display
    print("   [OK] src.ui_components imported")
    
    from src.filters import render_advanced_filters, apply_flow_filtering
    print("   [OK] src.filters imported")
    
    from src.flow_display import render_flow_journey
    print("   [OK] src.flow_display imported")
    
    print("\n3. Testing st.secrets access...")
    # Test secrets access without actually running Streamlit
    try:
        # Check if st.secrets exists
        if hasattr(st, 'secrets'):
            print("   [OK] st.secrets exists")
            # Try to access a key (will fail but that's OK)
            try:
                test_key = st.secrets.get("TEST_KEY", None)
                print("   [OK] st.secrets.get() works")
            except AttributeError:
                # st.secrets doesn't have .get() method - that's expected
                print("   [INFO] st.secrets doesn't have .get() method (expected)")
                try:
                    test_key = st.secrets["TEST_KEY"]
                except (KeyError, AttributeError, TypeError):
                    print("   [OK] st.secrets[key] access pattern works (raises expected errors)")
        else:
            print("   [WARN] st.secrets doesn't exist (might be OK in test environment)")
    except Exception as e:
        print(f"   [ERROR] Error accessing st.secrets: {e}")
        traceback.print_exc()
    
    print("\n4. Testing page config...")
    # Can't actually call st.set_page_config() outside Streamlit context
    # But we can check if the function exists
    if hasattr(st, 'set_page_config'):
        print("   [OK] st.set_page_config exists")
    else:
        print("   [ERROR] st.set_page_config not found!")
    
    print("\n" + "=" * 60)
    print("[OK] All imports successful! App should start correctly.")
    print("\nTo run the app:")
    print("  streamlit run cpa_flow_mockup.py")
    
except Exception as e:
    print("\n" + "=" * 60)
    print(f"[ERROR] Import failed: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
