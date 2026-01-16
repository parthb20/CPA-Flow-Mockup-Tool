import sys
sys.path.insert(0, '.')

try:
    print("Testing imports...")
    from src.config import FILE_A_ID, FILE_B_ID, SERP_BASE_URL
    print("✓ config")
    
    from src.data_loader import load_csv_from_gdrive, load_json_from_gdrive
    print("✓ data_loader")
    
    from src.utils import safe_float, safe_int
    print("✓ utils")
    
    from src.flow_analysis import find_default_flow
    print("✓ flow_analysis")
    
    from src.similarity import calculate_similarities
    print("✓ similarity")
    
    from src.serp import generate_serp_mockup
    print("✓ serp")
    
    from src.renderers import (
        render_mini_device_preview,
        render_similarity_score,
        inject_unique_id,
        create_screenshot_html,
        parse_creative_html
    )
    print("✓ renderers")
    
    from src.screenshot import get_screenshot_url, capture_with_playwright
    print("✓ screenshot")
    
    from src.ui_components import render_flow_combinations_table, render_what_is_flow_section, render_selected_flow_display
    print("✓ ui_components")
    
    from src.filters import render_advanced_filters, apply_flow_filtering
    print("✓ filters")
    
    from src.flow_display import render_flow_journey
    print("✓ flow_display")
    
    print("\n✅ ALL IMPORTS SUCCESSFUL")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
