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

# Device dimensions - these are PORTRAIT dimensions
# Horizontal orientation will swap width/height automatically
DEVICE_DIMENSIONS = {
    'mobile': {
        'width': 390,  # Portrait width
        'height': 844,  # Portrait height
        'target_width_portrait': 280,  # Target display width when in portrait
        'target_width_landscape': 360,  # Target display width when in landscape (wider to show landscape properly)
        'chrome_height': 90
    },
    'tablet': {
        'width': 820,  # Portrait width
        'height': 1180,  # Portrait height
        'target_width_portrait': 280,  # Target display width when in portrait
        'target_width_landscape': 420,  # Target display width when in landscape
        'chrome_height': 88
    },
    'laptop': {
        'width': 1440,  # Standard width (16:10 ratio)
        'height': 900,  # Standard height
        'target_width_portrait': 340,  # Target display width when in portrait (tall view)
        'target_width_landscape': 440,  # Target display width when in landscape (normal laptop)
        'chrome_height': 48
    }
}

# Default table settings
DEFAULT_TABLE_FILTER = 'Best'
DEFAULT_TABLE_COUNT = 10
DEFAULT_TABLE_SORT = 'Impressions'
