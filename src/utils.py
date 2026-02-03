# -*- coding: utf-8 -*-
"""
Utility functions for data processing and formatting
"""

import pandas as pd


def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        return float(value) if pd.notna(value) else default
    except:
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    try:
        return int(float(value)) if pd.notna(value) else default
    except:
        return default