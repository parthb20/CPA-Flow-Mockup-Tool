# -*- coding: utf-8 -*-
"""
CPA Flow Analysis Tool - Main Application
Modular architecture for maintainability
"""

# Import the original file for now - will be gradually refactored
# This allows incremental migration while maintaining functionality

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# For now, import everything from the original file
# TODO: Gradually migrate to modular imports
exec(open('cpa_flow_mockup.py').read())
