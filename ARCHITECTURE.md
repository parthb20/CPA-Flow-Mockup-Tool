# Architecture Overview

## Current Structure

The application has been refactored into a modular architecture for better maintainability:

```
CPA Flow Mockup Tool/
├── src/                          # Source modules
│   ├── __init__.py              # Package initialization
│   ├── config.py                # Configuration constants (file IDs, URLs, defaults)
│   ├── utils.py                 # Utility functions (safe_float, safe_int)
│   ├── data_loader.py          # Google Drive data loading (CSV, JSON, ZIP, GZIP)
│   ├── flow_analysis.py         # Flow finding logic (find_default_flow)
│   ├── similarity.py            # Similarity calculations (API calls, scoring)
│   ├── serp.py                  # SERP template processing
│   ├── renderers.py             # UI rendering (device previews, similarity scores)
│   └── screenshot.py           # Screenshot capture (thum.io, Playwright)
│
├── app.py                       # Main Streamlit app (currently imports original)
├── cpa_flow_mockup.py          # Original monolithic file (still functional)
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
└── .gitignore                   # Git ignore rules
```

## What's Been Done

### ✅ Completed
1. **Fixed syntax error** - Removed extra `else:` statement causing indentation error
2. **Created modular structure** - Separated code into logical modules:
   - **config.py**: All configuration constants in one place
   - **utils.py**: Helper functions for data conversion
   - **data_loader.py**: Google Drive file loading with ZIP/GZIP support
   - **flow_analysis.py**: Core logic for finding best performing flows
   - **similarity.py**: AI similarity scoring functions
   - **serp.py**: SERP template generation
   - **renderers.py**: Device previews and UI components
   - **screenshot.py**: Screenshot capture utilities
3. **Created documentation** - README.md with usage instructions
4. **Created .gitignore** - Proper ignore rules for Python/Streamlit projects

### ⚠️ Current State
- **app.py** currently just imports the original `cpa_flow_mockup.py` file
- The original file still works and contains all the UI logic
- Modules are ready but not yet integrated into main app

## What Needs to Be Done

### Option 1: Gradual Migration (Recommended)
Gradually migrate the main app logic from `cpa_flow_mockup.py` to use the new modules:

1. **Update imports in app.py**:
   ```python
   from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
   from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
   from src.flow_analysis import find_default_flow
   from src.similarity import calculate_similarities
   from src.renderers import render_mini_device_preview, render_similarity_score
   from src.serp import generate_serp_mockup
   ```

2. **Migrate UI sections**:
   - Keep the Streamlit UI code in `app.py`
   - Replace function calls to use imported modules
   - Test each section as you migrate

3. **Benefits**:
   - Can test incrementally
   - Original file remains as backup
   - Easier to debug issues

### Option 2: Keep Current Structure
- Keep using `cpa_flow_mockup.py` as-is
- Use modules for new features only
- Gradually refactor when making changes

## Next Steps

### Immediate Actions:
1. **Test the current setup**:
   ```bash
   streamlit run app.py
   ```
   This should work exactly like before since it imports the original file.

2. **Verify modules work**:
   - Check that all imports resolve correctly
   - Test individual module functions if needed

3. **Choose migration strategy**:
   - **Option A**: Keep current structure, use modules for new code
   - **Option B**: Gradually migrate main app to use modules
   - **Option C**: Full rewrite using modules (most work, cleanest result)

### For GitHub:
1. **Initialize git** (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Modular architecture"
   ```

2. **Create GitHub repo** and push:
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

3. **Files to commit**:
   - ✅ `src/` directory (all modules)
   - ✅ `app.py` (main entry point)
   - ✅ `requirements.txt`
   - ✅ `README.md`
   - ✅ `.gitignore`
   - ⚠️ `cpa_flow_mockup.py` (original - can keep as backup or remove)

## Module Responsibilities

### `src/config.py`
- File IDs for Google Drive
- SERP base URL
- Default settings
- Device dimensions

### `src/utils.py`
- `safe_float()` - Safe float conversion
- `safe_int()` - Safe integer conversion

### `src/data_loader.py`
- `load_csv_from_gdrive()` - Load CSV files (handles ZIP/GZIP)
- `load_json_from_gdrive()` - Load JSON files
- `process_file_content()` - Detect and decompress file types

### `src/flow_analysis.py`
- `find_default_flow()` - Find best performing flow based on conversions/clicks/impressions

### `src/similarity.py`
- `calculate_similarities()` - Calculate keyword→ad, ad→page, keyword→page scores
- `call_similarity_api()` - API calls to FastRouter/OpenAI
- `fetch_page_content()` - Extract text from landing pages
- `get_score_class()` - Get CSS class for score display

### `src/serp.py`
- `generate_serp_mockup()` - Generate SERP HTML with ad injection

### `src/renderers.py`
- `render_mini_device_preview()` - Device previews with chrome
- `render_similarity_score()` - Similarity score cards
- `parse_creative_html()` - Parse creative JSON
- `inject_unique_id()` - Force component re-rendering
- `create_screenshot_html()` - Screenshot display HTML

### `src/screenshot.py`
- `get_screenshot_url()` - Generate thum.io URLs
- `capture_with_playwright()` - Browser automation for 403 bypass

## Benefits of This Structure

1. **Maintainability**: Each module has a single responsibility
2. **Testability**: Can test modules independently
3. **Reusability**: Functions can be imported and reused
4. **Readability**: Easier to find and understand code
5. **Collaboration**: Multiple developers can work on different modules
6. **Scalability**: Easy to add new features without touching everything

## Migration Checklist

When ready to fully migrate:

- [ ] Update `app.py` to import from modules
- [ ] Replace function calls with module imports
- [ ] Test all features work correctly
- [ ] Remove unused code from original file
- [ ] Update documentation
- [ ] Test on Streamlit Cloud
- [ ] Archive or remove `cpa_flow_mockup.py`

## Current Status

✅ **Working**: Original file still functions perfectly
✅ **Modules Created**: All core functionality extracted
⚠️ **Integration**: Modules ready but not yet integrated
📝 **Next**: Choose migration strategy and execute
