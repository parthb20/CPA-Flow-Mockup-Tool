"""
Configuration constants and settings
"""

# Google Drive File IDs
FILE_A_ID = "1DXR77Tges9kkH3x7pYin2yo9De7cxqpc"  # Main CSV file (.csv.gz) - REQUIRED
FILE_B_ID = "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9"  # SERP templates JSON file - REQUIRED
FILE_D_ID = "1VjgRBBJJS3zJ9jKciiQzTpTmF0Y2oXgL"  # Pre-rendered creative responses (.csv): creative_id, creative_size, request - REQUIRED

# SERP URL base - template key gets appended
SERP_BASE_URL = "https://related.performmedia.com/search/?srprc=3&oscar=1&a=100&q=nada+vehicle+value+by+vin&mkt=perform&purl=forbes.com/home&tpid="

# Thum.io API configuration
THUMIO_API_KEY = None  # Set via environment variable or Streamlit secrets
THUMIO_REFERER_DOMAIN = None  # Set via environment variable or Streamlit secrets

# API Configuration
OPENAI_API_KEY = None  # Set via environment variable or Streamlit secrets

# Device dimensions - these are PORTRAIT dimensions
# Horizontal orientation will swap width/height automatically
# TRULY RESPONSIVE: Cards scale proportionally maintaining aspect ratio
DEVICE_DIMENSIONS = {
    'mobile': {
        'width': 390,  # Portrait width
        'height': 844,  # Portrait height
        # Use percentage of container width for truly responsive scaling
        'target_width_portrait': '22vw',  # 22% of viewport width
        'target_width_landscape': '22vw',  # Same for consistency
        'min_width_portrait': 280,  # Larger minimum for laptop screens
        'max_width_portrait': 380,  # Larger maximum for big screens
        'min_width_landscape': 280,
        'max_width_landscape': 380,
        'chrome_height': 68  # 22px status bar + 46px URL bar
    },
    'tablet': {
        'width': 820,  # Portrait width (9.7" iPad size)
        'height': 1180,  # Portrait height
        'target_width_portrait': '22vw',
        'target_width_landscape': '22vw',
        'min_width_portrait': 280,
        'max_width_portrait': 380,
        'min_width_landscape': 280,
        'max_width_landscape': 380,
        'chrome_height': 88
    },
    'laptop': {
        'width': 1366,  # Laptop width (landscape orientation, common 16:9 laptop)
        'height': 768,  # Laptop height
        'target_width_portrait': '22vw',  # Same for all devices
        'target_width_landscape': '22vw',  # Same for all devices
        'min_width_portrait': 340,  # LAPTOP minimum - BIGGER than mobile/tablet
        'max_width_portrait': 440,  # LAPTOP maximum - BIGGER than mobile/tablet
        'min_width_landscape': 340,  # LAPTOP landscape minimum
        'max_width_landscape': 440,  # LAPTOP landscape maximum
        'chrome_height': 48
    }
}

# Default table settings
DEFAULT_TABLE_FILTER = 'Best'
DEFAULT_TABLE_COUNT = 10
DEFAULT_TABLE_SORT = 'Impressions'
