"""
Configuration constants and settings
"""

# Google Drive File IDs
FILE_A_ID = "17_JKUhXfBYlWZZEKUStRgFQhL3Ty-YZu"  # Main CSV file
FILE_B_ID = "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9"  # SERP templates JSON file

# SERP URL base - template key gets appended
SERP_BASE_URL = "https://related.performmedia.com/search/?srprc=3&oscar=1&a=100&q=nada+vehicle+value+by+vin&mkt=perform&purl=forbes.com/home&tpid="

# Thum.io API configuration
THUMIO_API_KEY = None  # Set via environment variable or Streamlit secrets
THUMIO_REFERER_DOMAIN = None  # Set via environment variable or Streamlit secrets

# API Configuration
OPENAI_API_KEY = None  # Set via environment variable or Streamlit secrets

# Device dimensions
DEVICE_DIMENSIONS = {
    'mobile': {'width': 390, 'height': 844},      # iPhone-like portrait
    'tablet': {'width': 1024, 'height': 768},     # iPad landscape
    'laptop': {'width': 1920, 'height': 1080}     # Full HD desktop
}

# Default table settings
DEFAULT_TABLE_FILTER = 'Best'
DEFAULT_TABLE_COUNT = 10
DEFAULT_TABLE_SORT = 'Impressions'
