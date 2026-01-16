"""Minimal test to identify Streamlit Cloud errors"""
import streamlit as st

st.set_page_config(page_title="Test", page_icon="📊", layout="wide")

try:
    # Test imports one by one
    st.write("Testing imports...")
    
    from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
    st.write("✓ config imported")
    
    from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
    st.write("✓ data_loader imported")
    
    from src.utils import safe_float, safe_int
    st.write("✓ utils imported")
    
    from src.flow_analysis import find_default_flow
    st.write("✓ flow_analysis imported")
    
    from src.similarity import calculate_similarities
    st.write("✓ similarity imported")
    
    from src.serp import generate_serp_mockup
    st.write("✓ serp imported")
    
    from src.renderers import render_mini_device_preview
    st.write("✓ renderers imported")
    
    from src.screenshot import get_screenshot_url
    st.write("✓ screenshot imported")
    
    from src.ui_components import render_flow_combinations_table
    st.write("✓ ui_components imported")
    
    from src.filters import render_advanced_filters
    st.write("✓ filters imported")
    
    from src.flow_display import render_flow_journey
    st.write("✓ flow_display imported")
    
    st.success("✅ All imports successful!")
    
except Exception as e:
    st.error(f"❌ Import failed: {type(e).__name__}: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
