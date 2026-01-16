# Migration Guide

## Current Status

The codebase has been refactored into a modular structure. The original `cpa_flow_mockup.py` file is still functional and serves as the main application.

## Module Structure Created

✅ **Completed:**
- `src/config.py` - Configuration constants
- `src/utils.py` - Utility functions
- `src/data_loader.py` - Data loading functions
- `src/flow_analysis.py` - Flow finding logic
- `src/similarity.py` - Similarity calculations
- `src/serp.py` - SERP template processing
- `src/renderers.py` - Rendering functions
- `src/screenshot.py` - Screenshot utilities

## Next Steps for Full Migration

### Step 1: Update app.py to use modules

Replace the `exec()` statement in `app.py` with proper imports:

```python
# Instead of:
exec(open('cpa_flow_mockup.py').read())

# Use:
from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
from src.utils import safe_float, safe_int
from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
from src.flow_analysis import find_default_flow
from src.similarity import calculate_similarities, get_score_class
from src.serp import generate_serp_mockup
from src.renderers import (
    render_mini_device_preview,
    render_similarity_score,
    inject_unique_id,
    create_screenshot_html,
    parse_creative_html
)
from src.screenshot import get_screenshot_url, capture_with_playwright
```

### Step 2: Migrate main UI logic

Extract the main Streamlit UI code from `cpa_flow_mockup.py` into `app.py`, using the imported modules.

### Step 3: Test and verify

- Test all functionality works with modular imports
- Verify no regressions
- Check performance

### Step 4: Clean up

- Remove `cpa_flow_mockup.py` (or keep as backup)
- Update documentation
- Add unit tests

## Benefits of Modular Structure

1. **Maintainability**: Easier to find and fix bugs
2. **Testability**: Each module can be tested independently
3. **Reusability**: Functions can be imported and reused
4. **Collaboration**: Multiple developers can work on different modules
5. **Documentation**: Each module has clear responsibilities

## File Size Comparison

- Original: `cpa_flow_mockup.py` - ~3300 lines
- Modular: Split into 8 focused modules (~100-300 lines each)

## Import Examples

```python
# Configuration
from src.config import FILE_A_ID, DEFAULT_TABLE_COUNT

# Utilities
from src.utils import safe_float, safe_int

# Data loading
from src.data_loader import load_csv_from_gdrive

# Flow analysis
from src.flow_analysis import find_default_flow

# Similarity
from src.similarity import calculate_similarities

# Rendering
from src.renderers import render_mini_device_preview
```
