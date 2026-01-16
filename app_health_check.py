#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Health Check App - Tests all imports and basic functionality
"""

import streamlit as st

st.set_page_config(page_title="Health Check", page_icon="🏥", layout="wide")

st.title("🏥 App Health Check")

errors = []
warnings = []

# Test 1: Python version
st.subheader("1️⃣ Python Environment")
import sys
st.success(f"Python {sys.version}")

# Test 2: Core imports
st.subheader("2️⃣ Core Libraries")
try:
    import pandas as pd
    st.success(f"✓ Pandas {pd.__version__}")
except Exception as e:
    errors.append(f"Pandas: {e}")
    st.error(f"✗ Pandas: {e}")

try:
    import requests
    st.success(f"✓ Requests")
except Exception as e:
    errors.append(f"Requests: {e}")
    st.error(f"✗ Requests: {e}")

# Test 3: Module imports
st.subheader("3️⃣ Application Modules")

modules = [
    ('src.config', 'Config'),
    ('src.utils', 'Utils'),
    ('src.data_loader', 'Data Loader'),
    ('src.flow_analysis', 'Flow Analysis'),
    ('src.flow_display', 'Flow Display'),
    ('src.similarity', 'Similarity'),
    ('src.renderers', 'Renderers'),
]

for module_name, display_name in modules:
    try:
        __import__(module_name)
        st.success(f"✓ {display_name}")
    except Exception as e:
        errors.append(f"{display_name}: {e}")
        st.error(f"✗ {display_name}: {e}")

# Test 4: Secrets
st.subheader("4️⃣ Secrets Configuration")
try:
    if hasattr(st, 'secrets'):
        secrets_available = dir(st.secrets)
        if 'FASTROUTER_API_KEY' in secrets_available or 'OPENAI_API_KEY' in secrets_available:
            st.success("✓ API Keys configured")
        else:
            warnings.append("No API keys found in secrets")
            st.warning("⚠ No API keys in secrets (similarity features disabled)")
    else:
        warnings.append("Secrets not available")
        st.warning("⚠ Secrets not available")
except Exception as e:
    warnings.append(f"Secrets error: {e}")
    st.warning(f"⚠ Secrets: {e}")

# Test 5: Data files
st.subheader("5️⃣ Data Configuration")
try:
    from src.config import FILE_A_ID, FILE_B_ID
    st.success(f"✓ FILE_A_ID: {FILE_A_ID[:20]}...")
    st.success(f"✓ FILE_B_ID: {FILE_B_ID[:20]}...")
except Exception as e:
    errors.append(f"Config: {e}")
    st.error(f"✗ Config: {e}")

# Summary
st.subheader("📊 Summary")
if not errors:
    st.success("✅ ALL TESTS PASSED!")
    st.balloons()
else:
    st.error(f"❌ {len(errors)} error(s) found")
    for err in errors:
        st.code(err)

if warnings:
    st.warning(f"⚠️ {len(warnings)} warning(s)")
    for warn in warnings:
        st.code(warn)
