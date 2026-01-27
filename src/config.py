"""
Configuration constants and settings
"""

# Google Drive File IDs
FILE_A_ID = "1DXR77Tges9kkH3x7pYin2yo9De7cxqpc"  # Main CSV file (.csv.gz) - REQUIRED
FILE_B_ID = "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9"  # SERP templates JSON file - REQUIRED
FILE_C_ID = "1MrcmOzWo-TAmKJ6VV0FtA5PxBGJNGnkJ"  # File C - Creative requests (.csv.gz): creative_id, rensize, request - OPTIONAL if FILE_D_ID is set
FILE_D_ID = "1Uz29aIA1YtrnqmJaROgiiG4q1CvJ6arK"  # File D - Pre-rendered creative responses (.csv): creative_id, size, status, error, adcode - RECOMMENDED (makes FILE_C optional)

# SERP URL base - template key gets appended
SERP_BASE_URL = "https://related.performmedia.com/search/?srprc=3&oscar=1&a=100&q=nada+vehicle+value+by+vin&mkt=perform&purl=forbes.com/home&tpid="

# Thum.io API configuration
THUMIO_API_KEY = None  # Set via environment variable or Streamlit secrets
THUMIO_REFERER_DOMAIN = None  # Set via environment variable or Streamlit secrets

# API Configuration
OPENAI_API_KEY = None  # Set via environment variable or Streamlit secrets

# Device dimensions - these are PORTRAIT dimensions
# Horizontal orientation will swap width/height automatically
# RESPONSIVE: Use viewport-based scaling for consistent appearance
DEVICE_DIMENSIONS = {
    'mobile': {
        'width': 390,  # Portrait width
        'height': 844,  # Portrait height
        'target_width_portrait': '18vw',  # Responsive width (scales with viewport)
        'target_width_landscape': '22vw',  # Responsive width for landscape
        'min_width_portrait': 240,  # Minimum width in pixels
        'max_width_portrait': 320,  # Maximum width in pixels
        'min_width_landscape': 300,  # Minimum width in pixels
        'max_width_landscape': 420,  # Maximum width in pixels
        'chrome_height': 68  # 22px status bar + 46px URL bar
    },
    'tablet': {
        'width': 820,  # Portrait width
        'height': 1180,  # Portrait height
        'target_width_portrait': '18vw',  # Responsive width
        'target_width_landscape': '22vw',  # Responsive width for landscape
        'min_width_portrait': 240,  # Minimum width in pixels
        'max_width_portrait': 320,  # Maximum width in pixels
        'min_width_landscape': 300,  # Minimum width in pixels
        'max_width_landscape': 420,  # Maximum width in pixels
        'chrome_height': 88
    },
    'laptop': {
        'width': 1920,  # Wider laptop (16:9 ratio for true widescreen)
        'height': 1080,  # Standard height
        'target_width_portrait': '20vw',  # Responsive width (slightly larger)
        'target_width_landscape': '35vw',  # Responsive width for landscape (much wider)
        'min_width_portrait': 260,  # Minimum width in pixels
        'max_width_portrait': 380,  # Maximum width in pixels
        'min_width_landscape': 500,  # Minimum width in pixels
        'max_width_landscape': 800,  # Maximum width in pixels
        'chrome_height': 48
    }
}

# Default table settings
DEFAULT_TABLE_FILTER = 'Best'
DEFAULT_TABLE_COUNT = 10
DEFAULT_TABLE_SORT = 'Impressions'
