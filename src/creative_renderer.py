# -*- coding: utf-8 -*-
"""
Creative rendering functions using Weaver API
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
    Load File D - Pre-rendered creative responses from batch_render_creatives.py
    Expected format: CSV with columns: creative_id, size, status, error, adcode
    
    Returns:
        DataFrame with pre-rendered creatives, or None if loading fails
    """
    from src.data_loader import load_csv_from_gdrive
    import streamlit as st
    
    if not file_id or file_id.strip() == "":
        return None
    
    try:
        # Load CSV from Google Drive silently
        df = load_csv_from_gdrive(file_id)
        
        if df is None or len(df) == 0:
            return None
        
        # Clean column names (strip whitespace, lowercase for comparison)
        df.columns = df.columns.str.strip()
        
        # Create case-insensitive column mapping
        col_mapping = {col.lower(): col for col in df.columns}
        
        # Verify required columns (case-insensitive)
        required_cols = ['creative_id', 'size', 'adcode']
        missing = []
        for req_col in required_cols:
            if req_col.lower() not in col_mapping:
                missing.append(req_col)
        
        if missing:
            # Silent fail - errors will be shown in the UI later if needed
            return None
        
        # Rename columns to standardized names if needed
        rename_map = {}
        for req_col in required_cols:
            actual_col = col_mapping.get(req_col.lower())
            if actual_col and actual_col != req_col:
                rename_map[actual_col] = req_col
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        # Filter to only successful creatives with adcode (if status column exists)
        if 'status' in df.columns:
            df = df[df['status'] == 'success'].copy()
        df = df[df['adcode'].notna()].copy()
        
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
    """Get pre-rendered creative from File D"""
    import streamlit as st
    
    if prerendered_df is None or len(prerendered_df) == 0:
        return None
    
    # Debug: Show what we're looking for
    st.write(f"🔍 Looking for: creative_id={creative_id}, size={creative_size}")
    st.write(f"📊 File D has {len(prerendered_df)} rows")
    
    # Match creative_id and size
    matches = prerendered_df[
        (prerendered_df['creative_id'].astype(str) == str(creative_id)) &
        (prerendered_df['size'].astype(str) == str(creative_size))
    ]
    
    if len(matches) == 0:
        # Debug: Show why no match
        st.warning(f"❌ No match in File D for {creative_id} x {creative_size}")
        matching_ids = prerendered_df[prerendered_df['creative_id'].astype(str) == str(creative_id)]
        if len(matching_ids) > 0:
            st.write(f"Found creative_id {creative_id} but with sizes: {matching_ids['size'].unique().tolist()}")
        return None
    
    adcode = matches.iloc[0]['adcode']
    if pd.notna(adcode) and str(adcode).strip():
        # Debug: Show success
        st.success(f"✅ Found adcode for {creative_id} x {creative_size} ({len(str(adcode))} chars)")
        return str(adcode)
    
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
            # Wrap in HTML container
            try:
                width, height = map(int, creative_size.split('x'))
            except:
                width, height = 300, 250
            
            rendered_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width={width}, initial-scale=1">
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    html, body {{ width: {width}px; height: {height}px; overflow: auto; }}
                </style>
            </head>
            <body>
                {adcode}
            </body>
            </html>
            """
            return (rendered_html, None)
    
    # Creative not found in File D
    return None, "Creative data not found"
