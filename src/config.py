"""
Configuration constants and settings
"""

# Google Drive File IDs
FILE_A_ID = "1_SEziSRFL6_UC1WyfbyZFv3FZ73zBZL-"  # Main CSV file (.csv.gz) - REQUIRED
FILE_B_ID = "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9"  # SERP templates JSON file - REQUIRED
FILE_C_ID = "1MrcmOzWo-TAmKJ6VV0FtA5PxBGJNGnkJ"  # File C - Creative requests (.csv.gz): creative_id, rensize, request - OPTIONAL if FILE_D_ID is set
FILE_D_ID = "115rTSWMZiL18xh8MdlFisaBqbGDbjKsn"  # File D - Pre-rendered creative responses (.csv): creative_id, size, status, error, adcode - RECOMMENDED (makes FILE_C optional)

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
        'chrome_height': 68  # 22px status bar + 46px URL bar
    },
    'tablet': {
        'width': 820,  # Portrait width
        'height': 1180,  # Portrait height
        'target_width_portrait': 280,  # Target display width when in portrait
        'target_width_landscape': 360,  # Target display width when in landscape
        'chrome_height': 88
    },
    'laptop': {
        'width': 1920,  # Wider laptop (16:9 ratio for true widescreen)
        'height': 1080,  # Standard height
        'target_width_portrait': 300,  # Target display width when in portrait (tall view)
        'target_width_landscape': 640,  # Target display width when in landscape (very wide)
        'chrome_height': 48
    }
}

# Default table settings
DEFAULT_TABLE_FILTER = 'Best'
DEFAULT_TABLE_COUNT = 10
DEFAULT_TABLE_SORT = 'Impressions'
