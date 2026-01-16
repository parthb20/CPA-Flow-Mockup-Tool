# CPA Flow Analysis Tool

A comprehensive Streamlit application for analyzing and visualizing CPA (Cost Per Acquisition) ad flows. This tool helps you understand the complete user journey from publisher to landing page, with similarity scoring and performance metrics.

## Features

- **Flow Visualization**: Horizontal and vertical layouts for viewing ad flows
- **Device Previews**: Mobile, tablet, and laptop previews with realistic device chrome
- **Similarity Scoring**: AI-powered similarity scores between keyword, ad, and landing page
- **Performance Metrics**: CTR, CVR, and conversion tracking
- **SERP Integration**: SERP template rendering with ad injection
- **Screenshot Support**: Automatic screenshot capture with multiple fallback methods

## Architecture

The application is organized into modular components:

```
src/
├── __init__.py          # Package initialization
├── config.py            # Configuration constants
├── utils.py             # Utility functions
├── data_loader.py       # Google Drive data loading
├── flow_analysis.py     # Flow finding and analysis
├── similarity.py        # Similarity calculation
├── serp.py              # SERP template processing
├── renderers.py         # UI rendering functions
└── screenshot.py        # Screenshot capture

app.py                   # Main Streamlit application
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Streamlit secrets (`.streamlit/secrets.toml`):
```toml
FASTROUTER_API_KEY = "your-api-key"
SCREENSHOT_API_KEY = "your-thumio-key"  # Optional
THUMIO_REFERER_DOMAIN = "your-domain"   # Optional
```

3. Run the application:
```bash
streamlit run app.py
```

## Configuration

Edit `src/config.py` to configure:
- Google Drive file IDs
- SERP base URL
- Device dimensions
- Default table settings

## Usage

1. **Basic View**: Automatically selects the best performing flow
2. **Advanced View**: Filter by keyword and domain, with auto-selection of SERP and view_id
3. **Horizontal Layout**: View all flow stages in a single line
4. **Vertical Layout**: Detailed view with inline information

## Data Sources

- Main CSV file from Google Drive (FILE_A_ID)
- SERP templates JSON from Google Drive (FILE_B_ID)

## Dependencies

See `requirements.txt` for full list. Key dependencies:
- streamlit
- pandas
- requests
- beautifulsoup4
- playwright (optional, for 403 bypass)

## License

MIT License
