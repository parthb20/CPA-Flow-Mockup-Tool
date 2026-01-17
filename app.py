# -*- coding: utf-8 -*-
"""
CPA Flow Analysis Tool - Main Application Entry Point
This file is the entry point for Streamlit Cloud deployment
It executes the main application code from cpa_flow_mockup.py
Version: 2.0 - with ScreenshotOne API integration
"""

# Execute the main application file
# Streamlit Cloud looks for app.py or streamlit_app.py by default
with open('cpa_flow_mockup.py', 'r', encoding='utf-8') as f:
    code = f.read()
    exec(compile(code, 'cpa_flow_mockup.py', 'exec'))
