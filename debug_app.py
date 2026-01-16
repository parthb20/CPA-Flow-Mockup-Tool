# -*- coding: utf-8 -*-
"""
Debug script to identify deployment issues
"""
import streamlit as st

st.title("Debug App - Testing Imports")

try:
    st.write("1. Testing pandas import...")
    import pandas as pd
    st.success("✅ Pandas OK")
    
    st.write("2. Testing config import...")
    from src.config import FILE_A_ID
    st.success(f"✅ Config OK - FILE_A_ID: {FILE_A_ID[:10]}...")
    
    st.write("3. Testing utils import...")
    from src.utils import safe_float
    st.success("✅ Utils OK")
    
    st.write("4. Testing flow_analysis import...")
    from src.flow_analysis import find_default_flow
    st.success("✅ Flow Analysis OK")
    
    st.write("5. Testing flow_display import...")
    from src.flow_display import render_flow_journey
    st.success("✅ Flow Display OK")
    
    st.write("6. Testing all imports from main app...")
    from src.data_loader import load_csv_from_gdrive
    from src.similarity import calculate_similarities
    from src.serp import generate_serp_mockup
    from src.renderers import render_mini_device_preview
    from src.screenshot import get_screenshot_url
    from src.ui_components import render_flow_combinations_table
    from src.filters import render_advanced_filters
    st.success("✅ All imports OK!")
    
    st.balloons()
    st.success("🎉 App should work! No import errors detected.")
    
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
