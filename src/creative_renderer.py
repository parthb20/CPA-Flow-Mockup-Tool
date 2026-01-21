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
    Load File C - Creative requests CSV from Google Drive
    Expected columns: creative_id, Creative_Size_Final, request
    """
    from src.data_loader import load_csv_from_gdrive
    
    if not file_id or file_id.strip() == "":
        return None
    
    try:
        # Load as CSV (File C is always CSV)
        df = load_csv_from_gdrive(file_id)
        if df is not None and len(df) > 0:
            # Verify required columns exist
            required_cols = ['creative_id', 'Creative_Size_Final', 'request']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                import streamlit as st
                st.warning(f"⚠️ File C missing columns: {', '.join(missing_cols)}")
                return None
            
            return df
    except Exception as e:
        import streamlit as st
        st.error(f"❌ Failed to load File C: {str(e)}")
    
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
            # Debug: log the error
            import streamlit as st
            st.warning(f"Failed to parse Creative_Keywords: {str(e)[:100]}")
    
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


def render_creative_via_weaver(creative_id, creative_size, keyword_array, creative_requests_df, cipher_key=None):
    """
    Render creative using Weaver API
    
    Args:
        creative_id: Creative ID from flow
        creative_size: Creative size from flow (e.g., "300x250")
        keyword_array: List of keywords in format [{"t":"kw1"},{"t":"kw2"}]
        creative_requests_df: DataFrame from File C with columns: creative_id, creative_size, request
        cipher_key: Cipher key for encryption (optional, uses default if None)
    
    Returns:
        (rendered_html, error_message) tuple
    """
    if creative_requests_df is None or len(creative_requests_df) == 0:
        return None, "File C not loaded"
    
    # Use default cipher key if not provided
    if not cipher_key:
        cipher_key = DEFAULT_CIPHER_KEY
    
    # Find matching creative request
    creative_key = f"{creative_id}_{creative_size}"
    
    # Try to find exact match using Creative_Size_Final column
    matching_rows = creative_requests_df[
        (creative_requests_df['creative_id'].astype(str) == str(creative_id)) &
        (creative_requests_df['Creative_Size_Final'].astype(str) == str(creative_size))
    ]
    
    if len(matching_rows) == 0:
        return None, f"No request found for {creative_key}"
    
    # Get request data
    request_data_str = matching_rows.iloc[0]['request']
    
    try:
        # Parse request JSON
        if isinstance(request_data_str, str):
            request_data = json.loads(request_data_str)
        else:
            request_data = request_data_str
    except Exception as e:
        return None, f"Invalid request JSON: {str(e)}"
    
    # Encrypt and encode keywords
    encrypted_kd = encrypt_and_encode_keywords(keyword_array, cipher_key)
    
    # Call Weaver API
    api_url = "http://weaver.21master.srv.media.net/v3/adcode"
    headers = {
        'Content-Type': 'application/json',
        'FMTP-MAP': 't6BpxluW_T9uP75dd18ex-9QuWHm5mx7X9n0HmHrwPo%3D',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(
            api_url,
            json=request_data,
            headers=headers,
            timeout=30,
            verify=False
        )
        
        if response.status_code != 200:
            return None, f"API returned status {response.status_code}"
        
        response_data = response.json()
        
        if 'adcode' not in response_data:
            return None, "No 'adcode' in API response"
        
        # Get adcode and unescape it
        adcode = response_data['adcode']
        adcode = unescape_adcode(adcode)
        
        # Replace kd= parameter with encrypted keywords
        adcode = replace_kd_in_adcode(adcode, encrypted_kd)
        
        # Extract width and height from creative_size (e.g., "300x250")
        try:
            width, height = map(int, creative_size.split('x'))
        except:
            width, height = 300, 250
        
        # Wrap in HTML container with scroll support
        rendered_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    width: {width}px;
                    height: {height}px;
                    overflow: auto;
                    /* If creative is bigger than container, allow scrolling */
                }}
                body > * {{
                    max-width: {width}px;
                    /* Don't extend beyond container width */
                }}
            </style>
        </head>
        <body>
            {adcode}
        </body>
        </html>
        """
        
        return rendered_html, None
        
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error: {str(e)[:100]}"
    except requests.exceptions.Timeout:
        return None, "API timeout after 30 seconds"
    except Exception as e:
        return None, f"Error: {str(e)[:100]}"
