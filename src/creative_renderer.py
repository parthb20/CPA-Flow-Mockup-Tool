# -*- coding: utf-8 -*-
"""
Creative rendering functions - now using Response.adcode from File X
"""

import json
import html
import re
import warnings
import pandas as pd
import requests
from urllib.parse import quote

# Suppress SSL warnings
try:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
except:
    pass


DEFAULT_CIPHER_KEY = "dqkwfjkefq;"


def unescape_adcode(adcode):
    """
    Unescape ad code from Response.adcode column
    Similar to Ad_Code_Render.py logic
    """
    if not adcode or pd.isna(adcode):
        return ""
    
    adcode = str(adcode)
    
    # Unescape unicode sequences (\u003c, etc.)
    if '\\u' in adcode or '\\/' in adcode:
        try:
            # Use json.loads to unescape unicode sequences
            adcode = json.loads('"' + adcode + '"')
        except Exception:
            # Fallback: manual replacement
            adcode = adcode.replace('\\u003c', '<')
            adcode = adcode.replace('\\u003e', '>')
            adcode = adcode.replace('\\u003d', '=')
            adcode = adcode.replace('\\/', '/')
    
    # Unescape HTML entities
    if '&' in adcode:
        adcode = html.unescape(adcode)
    
    return adcode


def render_creative_from_adcode(adcode_raw, creative_size="300x250"):
    """
    Render creative directly from Response.adcode column
    
    Args:
        adcode_raw: Raw ad code from Response.adcode column
        creative_size: Creative size (e.g., "300x250")
    
    Returns:
        (rendered_html, error_message) tuple
    """
    if not adcode_raw or pd.isna(adcode_raw):
        return None, "No ad code available"
    
    try:
        # Unescape the ad code
        adcode = unescape_adcode(adcode_raw)
        
        # DEBUG: Check if ad code looks valid
        has_script = '<script' in adcode.lower() if adcode else False
        
        if not adcode:
            return None, "Ad code is empty after unescaping"
        
        if not has_script:
            return None, f"Ad code doesn't contain <script> tag. First 200 chars: {adcode[:200]}"
        
        # Parse creative size
        try:
            width, height = map(int, creative_size.split('x'))
        except:
            width, height = 300, 250
        
        # Wrap ad code in HTML container
        # Add timestamp for cache-busting
        import time
        timestamp = int(time.time() * 1000)
        
        rendered_html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        html, body {{
            width: 100%;
            height: 100%;
            font-family: Arial, sans-serif;
            background: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: visible;
        }}
        .ad-wrapper {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .ad-container {{
            width: {width}px;
            height: {height}px;
            background: white;
            position: relative;
            overflow: visible;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <div class="ad-wrapper">
        <div class="ad-container" id="ad-container">
            {adcode}
        </div>
    </div>
</body>
</html>
'''
        
        return rendered_html, None
        
    except Exception as e:
        return None, f"Error rendering creative: {str(e)}"


def load_creative_requests(file_id):
    """
    Load File C - Creative requests from Google Drive
    Expected format: .csv.gz (recommended) or .csv
    Expected columns: creative_id, rensize, request
    
    NOTE: Use .gz format to preserve JSON in request column properly
    """
    from src.data_loader import load_csv_from_gdrive
    import streamlit as st
    import csv
    
    if not file_id or file_id.strip() == "":
        return None
    
    try:
        # Increase field size limit for large JSON
        csv.field_size_limit(100000000)
        
        # Load silently unless there's an error
        
        # Load file (handles .gz automatically)
        df = load_csv_from_gdrive(file_id)
        
        if df is None or len(df) == 0:
            return None
        
        # Check if we have exactly 3 columns (good .gz or properly quoted CSV)
        if len(df.columns) == 3:
            df.columns = ['creative_id', 'rensize', 'request']
            return df
        
        # If more than 3 columns, JSON was split across cells - merge them
        if len(df.columns) > 3:
            # Create new dataframe with merged request
            merged_df = pd.DataFrame()
            merged_df['creative_id'] = df.iloc[:, 0]
            merged_df['rensize'] = df.iloc[:, 1]
            # Merge all columns from index 2 onwards with space separator
            merged_df['request'] = df.iloc[:, 2:].apply(
                lambda row: ' '.join([str(x) for x in row if pd.notna(x)]), 
                axis=1
            )
            return merged_df
        
        # Silent fail if not enough columns
        return None
        
    except Exception as e:
        # Silent fail - avoid blocking app startup
        return None


def load_prerendered_responses(file_id):
    """
    Load File D - Pre-rendered creative responses
    Expected format: CSV with columns: Creative_id, Creative_size, Request
    
    Returns:
        DataFrame with creative data, or None if loading fails
    """
    from src.data_loader import load_csv_from_gdrive
    import streamlit as st
    import re
    
    if not file_id or file_id.strip() == "":
        return None
    
    try:
        # Load CSV from Google Drive with debug
        df = load_csv_from_gdrive(file_id)
        
        if df is None or len(df) == 0:
            return None
        
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        # Create case-insensitive column mapping
        col_mapping = {col.lower(): col for col in df.columns}
        
        # Verify required columns (case-insensitive)
        required_cols = ['creative_id', 'creative_size', 'request']
        missing = [req_col for req_col in required_cols if req_col.lower() not in col_mapping]
        
        if missing:
            return None
        
        # Rename columns to standardized names if needed
        rename_map = {}
        for req_col in required_cols:
            actual_col = col_mapping.get(req_col.lower())
            if actual_col and actual_col != req_col:
                rename_map[actual_col] = req_col
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        # Clean the Request column: replace ||| with commas and handle quotes
        if 'request' in df.columns:
            def clean_request(val):
                if pd.isna(val) or val == '':
                    return val
                val_str = str(val)
                # Replace ||| with comma
                val_str = val_str.replace('|||', ',')
                # Remove extra backslashes from escaped quotes
                val_str = val_str.replace('\\"', '"')
                # Clean up any double quotes that might cause issues
                val_str = val_str.replace('""', '"')
                return val_str
            
            df['request'] = df['request'].apply(clean_request)
        
        # Keep only rows with valid creative_id
        df = df[df['creative_id'].notna()].copy()
        
        if len(df) == 0:
            return None
        
        return df
        
    except Exception as e:
        # Silent fail - avoid blocking app startup
        return None


def parse_keyword_array_from_flow(flow_data):
    """
    Extract keyword array from flow data
    Column name in File A: Creative_Keywords
    Format: '[{\"t\":\"kw1\"},{\"t\":\"kw2\"}]' (escaped JSON in CSV)
    Returns list maintaining order: [{"t":"kw1","idx":0},{"t":"kw2","idx":1},...]
    """
    keyword_array = flow_data.get('Creative_Keywords', None)
    
    if keyword_array and pd.notna(keyword_array):
        try:
            # Handle string format (may be escaped)
            if isinstance(keyword_array, str):
                # Try direct parse first
                try:
                    parsed = json.loads(keyword_array)
                except json.JSONDecodeError:
                    # Try unescaping then parsing (CSV may double-escape)
                    try:
                        unescaped = keyword_array.replace('\\"', '"').replace('\\\\', '\\')
                        parsed = json.loads(unescaped)
                    except:
                        # Last resort: try as raw string with ast
                        import ast
                        parsed = ast.literal_eval(keyword_array)
            # Already a list
            elif isinstance(keyword_array, list):
                parsed = keyword_array
            else:
                parsed = []
            
            # Add index to each keyword to preserve order (0-indexed from left)
            if parsed and isinstance(parsed, list):
                result = []
                for idx, kw in enumerate(parsed):
                    if isinstance(kw, dict) and 't' in kw:
                        result.append({"t": kw['t'], "idx": idx})
                    elif isinstance(kw, str):
                        result.append({"t": kw, "idx": idx})
                return result if result else parsed
        except Exception as e:
            # Silent fail - just return empty
            pass
    
    # Fallback: create from keyword_term
    keyword_term = flow_data.get('keyword_term', '')
    if keyword_term and pd.notna(keyword_term):
        return [{"t": str(keyword_term), "idx": 0}]
    
    return []


def _generate_lookup(key):
    """
    Generate lookup map from character to 1-indexed position in key
    Returns dict where key is character and value is position (1-indexed, 0 means not found)
    """
    lookup = {}
    for index, char in enumerate(key):
        lookup[char] = index + 1  # 1-indexed, 0 identifies if char is not present
    return lookup


def caesar_encrypt(text, key, shift=5):
    """
    Caesar cipher with shift - matches Go implementation
    Encrypts text using the provided key and a shift value
    Characters in the key are shifted within the key, characters not in key remain unchanged
    """
    if not text:
        return text

    key_list = list(key)
    key_len = len(key_list)
    lookups = _generate_lookup(key)
    encrypted = []

    for char in text:
        position_in_key = lookups.get(char, 0)  # 0 if not found
        if position_in_key == 0:
            # Character not in key, keep as-is
            encrypted.append(char)
        else:
            # Shift within the key: (positionInKey - 1 + shift) % keyLen
            new_index = (position_in_key - 1 + shift) % key_len
            new_char = key_list[new_index]
            encrypted.append(new_char)

    return ''.join(encrypted)


def encrypt_and_encode_keywords(keyword_array, cipher_key):
    """
    Convert keywords to JSON format, encrypt with Caesar cipher (shift 5), then URL encode
    keyword_array: [{"t":"kw1","idx":0},{"t":"kw2","idx":1},...] - order preserved from Creative_Keywords
    Returns URL-encoded encrypted string
    """
    if not keyword_array:
        return ""

    # Convert to [{"t":"kw1"},{"t":"kw2"}] format (preserve order, remove idx if present)
    kw_json_list = []
    for kw in keyword_array:
        if isinstance(kw, dict) and 't' in kw:
            kw_json_list.append({"t": kw["t"]})
        elif isinstance(kw, str):
            kw_json_list.append({"t": kw})
    
    # Convert to JSON string (compact, no spaces) - order maintained
    json_string = json.dumps(kw_json_list, separators=(',', ':'))

    # Encrypt using Caesar cipher with shift 5
    encrypted = caesar_encrypt(json_string, cipher_key, shift=5)

    # URL encode
    url_encoded = quote(encrypted, safe='')

    return url_encoded


def unescape_adcode(adcode):
    """
    Unescape only unicode sequences like \u003c, but preserve JavaScript string escaping
    This ensures mn_misc and other JSON strings remain valid
    """
    if not adcode:
        return adcode

    # Only unescape unicode sequences (\u003c, \u003e, etc.) and backslash escapes (\/, \")
    if '\\u' in adcode or '\\/' in adcode:
        try:
            # Use json.loads to unescape unicode sequences
            adcode = json.loads('"' + adcode + '"')
        except:
            # Fallback: just replace common unicode escapes manually
            adcode = adcode.replace('\\u003c', '<')
            adcode = adcode.replace('\\u003e', '>')
            adcode = adcode.replace('\\u003d', '=')
            adcode = adcode.replace('\\/', '/')

    # Handle HTML entities
    if '&' in adcode:
        adcode = html.unescape(adcode)

    return adcode


def replace_kd_in_adcode(adcode, url_encoded_kd):
    """
    Add or replace mn_kd variable in the script tag
    """
    if not url_encoded_kd:
        return adcode

    # Check if mn_kd already exists
    if 'mn_kd=' in adcode or 'mn_kd =' in adcode:
        # Replace existing mn_kd value
        adcode = re.sub(
            r'mn_kd\s*=\s*"[^"]*"',
            f'mn_kd="{url_encoded_kd}"',
            adcode
        )
    else:
        # Add mn_kd before the closing </script> of the first script tag
        match = re.search(r'(mn_csrsv2\s*=\s*"[^"]+";)(</script>)', adcode)
        if match:
            adcode = adcode[:match.end(1)] + f'mn_kd="{url_encoded_kd}";' + adcode[match.end(1):]
        else:
            # Fallback: try to find any </script> tag
            match = re.search(r'(;)(</script>)', adcode, re.IGNORECASE)
            if match:
                adcode = adcode[:match.end(1)] + f'mn_kd="{url_encoded_kd}";' + adcode[match.end(1):]

    return adcode


def get_prerendered_creative(creative_id, creative_size, prerendered_df):
    """Get pre-rendered creative from File D - parses Request JSON to extract creative info"""
    import streamlit as st
    import json
    
    if prerendered_df is None or len(prerendered_df) == 0:
        return None
    
    # Normalize creative_size format (remove spaces, make lowercase)
    creative_size_normalized = str(creative_size).replace(' ', '').lower()
    
    # Find column names (case-insensitive)
    id_col = None
    size_col = None
    request_col = None
    
    for col in prerendered_df.columns:
        col_lower = col.lower()
        if 'creative' in col_lower and 'id' in col_lower:
            id_col = col
        if 'creative' in col_lower and 'size' in col_lower:
            size_col = col
        if 'size' in col_lower and 'creative' not in col_lower and size_col is None:
            size_col = col
        if 'request' in col_lower:
            request_col = col
    
    if not id_col or not size_col or not request_col:
        return None
    
    # Normalize size column in dataframe (remove spaces, lowercase)
    prerendered_df['size_normalized'] = prerendered_df[size_col].astype(str).str.replace(' ', '').str.lower()
    
    # Match creative_id and normalized creative_size
    matches = prerendered_df[
        (prerendered_df[id_col].astype(str) == str(creative_id)) &
        (prerendered_df['size_normalized'] == creative_size_normalized)
    ]
    
    if len(matches) == 0:
        return None
    
    request_data = matches.iloc[0][request_col]
    if pd.notna(request_data) and str(request_data).strip():
        request_str = str(request_data)
        
        # Parse Request JSON to extract creative metadata
        try:
            # Request data is already cleaned (||| replaced with ,)
            request_json = json.loads(request_str)
            
            # Extract useful info
            crid = request_json.get('crid', creative_id)
            size = request_json.get('size', creative_size)
            domain = request_json.get('progDomain', 'N/A')
            
            # Create HTML placeholder showing the request data
            placeholder_html = f"""
            <div style="width: 100%; height: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        display: flex; flex-direction: column; align-items: center; justify-content: center; 
                        color: white; font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <div style="font-size: 48px; margin-bottom: 10px;">🎨</div>
                <div style="font-size: 20px; font-weight: bold; margin-bottom: 15px;">Creative {crid}</div>
                <div style="font-size: 14px; opacity: 0.9; margin-bottom: 5px;">Size: {size}</div>
                <div style="font-size: 12px; opacity: 0.8;">Domain: {domain}</div>
                <div style="margin-top: 20px; padding: 10px 20px; background: rgba(255,255,255,0.2); 
                            border-radius: 20px; font-size: 11px;">
                    📊 Bid Request Data Available
                </div>
            </div>
            """
            return placeholder_html
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return placeholder with basic info
            placeholder_html = f"""
            <div style="width: 100%; height: 100%; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        display: flex; flex-direction: column; align-items: center; justify-content: center; 
                        color: white; font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                <div style="font-size: 48px; margin-bottom: 10px;">🎨</div>
                <div style="font-size: 20px; font-weight: bold; margin-bottom: 15px;">Creative {creative_id}</div>
                <div style="font-size: 14px; opacity: 0.9;">Size: {creative_size}</div>
                <div style="margin-top: 20px; padding: 10px 20px; background: rgba(255,255,255,0.2); 
                            border-radius: 20px; font-size: 11px;">
                    ⚠️ Request Data Format Issue
                </div>
            </div>
            """
            return placeholder_html
    
    return None


def render_creative_via_weaver(creative_id, creative_size, keyword_array, creative_requests_df, cipher_key=None, prerendered_df=None):
    """
    Render creative using pre-rendered responses from File D
    NO WEAVER API - Just uses File D adcode directly
    
    Args:
        creative_id: Creative ID from flow
        creative_size: Creative size from flow (e.g., "300x250")
        prerendered_df: DataFrame from File D with pre-rendered responses
    
    Returns:
        (rendered_html, error_message) tuple
    """
    
    # Use pre-rendered response from File D
    if prerendered_df is not None:
        adcode = get_prerendered_creative(creative_id, creative_size, prerendered_df)
        if adcode:
            # Add expander to show full adcode for debugging (optional)
            # import streamlit as st
            # with st.expander("🔧 Debug: View Full Adcode"):
            #     st.code(adcode, language='html')
            # Wrap in HTML container
            try:
                width, height = map(int, creative_size.split('x'))
            except:
                width, height = 300, 250
            
            # Ensure scripts can execute by NOT escaping the adcode
            # Add error handling and loading indicator for external scripts
            # Add cache-busting timestamp
            import time
            cache_bust = int(time.time() * 1000)
            
            rendered_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        html, body {{ 
            width: 100%; 
            height: 100%; 
            overflow: hidden;
            background: #f8fafc;
            font-family: Arial, sans-serif;
        }}
        
        /* RESPONSIVE WRAPPER - Enable container queries */
        #wrapper {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            container-type: size;
            overflow: hidden;
        }}
        
        /* AD CONTAINER - Fixed size that will be scaled */
        #ad-container {{
            width: {width}px;
            height: {height}px;
            position: relative;
            transform-origin: center center;
            /* SCALE PROPORTIONALLY but NEVER exceed original size (max 1.0) */
            transform: scale(min(calc(100cqw / {width}px), 1));
            background: white;
        }}
        
        /* Loading indicator */
        #loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #999;
            font-size: 12px;
            text-align: center;
            padding: 10px;
            z-index: 1000;
        }}
        .show-loading {{
            display: block !important;
        }}
        .hide-loading {{
            display: none !important;
        }}
    </style>
</head>
<body>
<div id="wrapper">
    <div id="ad-container">
        <div id="loading">⏳ Loading ad...<br><small>(Cache: {cache_bust})</small></div>
        {adcode}
    </div>
</div>
<script>
    console.log('Creative container loaded at: {cache_bust}');
    console.log('Creative size: {width}x{height}');
    
    console.log('Scaling: Using transform scale with container queries (cqw)');
    console.log('Scale formula: calc(100cqw / {width}px)');
    
    // Track if content was ever detected
    var contentDetected = false;
    var contentRemoved = false;
    
    // Hide loading once ad content is detected
    var checkInterval = setInterval(function() {{
        var adContainer = document.getElementById('ad-container');
        var loadingDiv = document.getElementById('loading');
        
        // Check if there's content besides the loading div
        var hasAdContent = false;
        for (var i = 0; i < adContainer.children.length; i++) {{
            if (adContainer.children[i].id !== 'loading') {{
                hasAdContent = true;
                break;
            }}
        }}
        
        // Also check for dynamically inserted content
        if (adContainer.querySelector('iframe') || 
            adContainer.querySelector('ins') ||
            adContainer.querySelector('div[id^="pfm"]') ||
            adContainer.querySelector('div[id^="mn"]') ||
            document.body.children.length > 1) {{
            hasAdContent = true;
        }}
        
        // Check document height/scrollHeight for content
        if (document.body.scrollHeight > 300 || document.documentElement.scrollHeight > 300) {{
            hasAdContent = true;
        }}
        
        if (hasAdContent) {{
            if (!contentDetected) {{
                contentDetected = true;
                console.log('Ad content detected');
            }}
            loadingDiv.className = 'hide-loading';
        }} else if (contentDetected && !hasAdContent) {{
            // Content was detected before but now it's gone
            if (!contentRemoved) {{
                contentRemoved = true;
                console.warn('Ad content was removed (fraud detection or viewability check)');
                loadingDiv.innerHTML = '⚠️ Ad loaded then removed<br><small>Network validation check failed</small>';
                loadingDiv.style.color = '#ff8800';
                loadingDiv.style.fontSize = '11px';
                loadingDiv.className = 'show-loading';
            }}
        }}
    }}, 500);
    
    // Show loading indicator after 1.5 seconds if still nothing
    setTimeout(function() {{
        var loadingDiv = document.getElementById('loading');
        if (!loadingDiv.className.includes('hide-loading')) {{
            loadingDiv.innerHTML = '⏳ Loading ad...<br><small>Waiting for network response...</small>';
            loadingDiv.className = 'show-loading';
            console.log('No ad content after 1.5s, showing loading indicator');
        }}
    }}, 1500);
    
    // Timeout after 6 seconds
    setTimeout(function() {{
        var loadingDiv = document.getElementById('loading');
        if (!loadingDiv.className.includes('hide-loading')) {{
            loadingDiv.innerHTML = '⚠️ No ad content<br><small>Network returned no fill or blocked by iframe restrictions</small>';
            loadingDiv.style.color = '#ff8800';
            loadingDiv.style.fontSize = '12px';
            loadingDiv.style.lineHeight = '1.5';
            loadingDiv.style.fontWeight = '600';
            console.warn('Ad network did not return content (no fill or blocked)');
        }}
        clearInterval(checkInterval);
    }}, 6000);
    
    // Error handling for failed script loads
    window.addEventListener('error', function(e) {{
        if (e.target.tagName === 'SCRIPT') {{
            console.error('Script failed to load:', e.target.src);
            var loadingDiv = document.getElementById('loading');
            loadingDiv.innerHTML = '❌ Script failed to load<br><small>' + e.target.src + '</small>';
            loadingDiv.style.color = '#f44';
            loadingDiv.className = 'show-loading';
        }}
    }}, true);
</script>
</body>
</html>"""
            
            return (rendered_html, None)
    
    # Creative not found in File D
    return None, "Creative data not found"
