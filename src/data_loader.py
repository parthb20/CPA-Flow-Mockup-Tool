"""
Data loading functions for Google Drive files
All functions are cached to prevent Google Drive rate limits during development
"""

import streamlit as st
import requests
import pandas as pd
import json
import gzip
import zipfile
import tempfile
import os
import re
from io import StringIO, BytesIO

try:
    import gdown
    GDOWN_AVAILABLE = True
except:
    GDOWN_AVAILABLE = False


def process_file_content(content):
    """Process file content - detect type and decompress if needed"""
    import csv
    
    try:
        st.write(f"🔍 Processing file: {len(content)} bytes")
        if len(content) > 0:
            st.write(f"🔍 First 50 bytes: {content[:50]}")
        else:
            st.error("❌ File content is EMPTY (0 bytes)!")
            return None
        # Check if Google Drive returned HTML error page
        if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html') or b'<title>Google Drive' in content[:1000]:
            st.error("❌ Could not download file - check sharing settings")
            return None
        
        # Check file type by magic bytes
        # GZIP: 1f 8b
        if len(content) >= 2 and content[:2] == b'\x1f\x8b':
            try:
                # Decompress GZIP
                with gzip.open(BytesIO(content), 'rb') as gz_file:
                    decompressed = gz_file.read()
                
                # Read CSV with maximum field size to prevent truncation
                csv.field_size_limit(100000000)  # 100MB per field
                
                # Parse CSV (use default quoting, handles most cases)
                df = pd.read_csv(
                    BytesIO(decompressed), 
                    dtype=str, 
                    encoding='utf-8',
                    engine='python',
                    on_bad_lines='warn'
                )
                
                return df
            except Exception as e:
                st.error(f"❌ Error decompressing GZIP: {str(e)}")
                return None
        
        # ZIP: 50 4b (PK)
        elif len(content) >= 2 and content[:2] == b'PK':
            try:
                with zipfile.ZipFile(BytesIO(content)) as zip_file:
                    # Find CSV file
                    csv_file = None
                    for filename in zip_file.namelist():
                        if filename.lower().endswith('.csv'):
                            csv_file = filename
                            break
                    
                    if csv_file:
                        csv_content = zip_file.read(csv_file)
                        df = pd.read_csv(
                            BytesIO(csv_content), 
                            dtype=str, 
                            on_bad_lines='skip',
                            encoding='utf-8',
                            engine='python'
                        )
                        return df
                    else:
                        st.error("❌ No CSV file found in ZIP")
                        return None
            except Exception as e:
                st.error(f"❌ Error extracting ZIP: {str(e)}")
                return None
        else:
            # Try as plain CSV
            st.write("📄 Treating as plain CSV file")
            try:
                decoded = content.decode('utf-8')
                st.write(f"✅ Decoded to UTF-8: {len(decoded)} characters")
                st.write(f"🔍 First 200 characters:\n{decoded[:200]}")
                
                # Try with different CSV parsing options for files with complex quoting
                # First try: Standard parser with QUOTE_ALL
                try:
                    df = pd.read_csv(
                        StringIO(decoded), 
                        dtype=str,
                        encoding='utf-8',
                        engine='python',
                        quotechar='"',
                        escapechar='\\',
                        on_bad_lines='skip'
                    )
                    st.write(f"✅ Parsed CSV (standard): {len(df)} rows, {len(df.columns)} columns")
                except Exception as e1:
                    st.write(f"⚠️ Standard parser failed: {str(e1)}")
                    # Second try: C engine with different options
                    try:
                        df = pd.read_csv(
                            StringIO(decoded),
                            dtype=str,
                            encoding='utf-8',
                            engine='c',
                            quotechar='"',
                            doublequote=True,
                            on_bad_lines='skip'
                        )
                        st.write(f"✅ Parsed CSV (C engine): {len(df)} rows, {len(df.columns)} columns")
                    except Exception as e2:
                        st.write(f"⚠️ C engine failed: {str(e2)}")
                        # Third try: Read line by line manually
                        import csv as csv_module
                        try:
                            reader = csv_module.reader(StringIO(decoded), quotechar='"', escapechar='\\')
                            rows = list(reader)
                            if len(rows) > 1:
                                df = pd.DataFrame(rows[1:], columns=rows[0])
                                st.write(f"✅ Parsed CSV (manual): {len(df)} rows, {len(df.columns)} columns")
                            else:
                                raise ValueError("No data rows found")
                        except Exception as e3:
                            st.error(f"❌ All CSV parsing methods failed!")
                            st.error(f"Method 1: {str(e1)}")
                            st.error(f"Method 2: {str(e2)}")
                            st.error(f"Method 3: {str(e3)}")
                            return None
                
                if len(df) > 0:
                    st.write(f"📋 Columns: {df.columns.tolist()}")
                    st.write(f"📊 First row sample: {dict(list(df.iloc[0].items())[:2])}")
                else:
                    st.warning("⚠️ Parsed 0 rows - possible data format issue")
                return df
            except Exception as e:
                st.error(f"❌ CSV parse error: {str(e)}")
                import traceback
                st.error(f"Full error: {traceback.format_exc()}")
                return None
                
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        return None


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour (3600 seconds)
def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive - handles CSV, ZIP, GZIP, and large file virus scan
    Cached for 1 hour to prevent rate limits
    
    During development: If you hit rate limits, download files manually to 'data/' folder:
    - FILE_A: data/file_a.csv.gz
    - FILE_D: data/file_d.csv
    """
    # Method 0: Try local file first (for development when rate limited)
    import os
    local_file_path = None
    if file_id == "1DXR77Tges9kkH3x7pYin2yo9De7cxqpc":  # FILE_A
        local_file_path = "data/file_a.csv.gz"
    elif file_id == "1Uz29aIA1YtrnqmJaROgiiG4q1CvJ6arK":  # OLD FILE_D
        local_file_path = "data/file_d.csv"
    elif file_id == "1VjgRBBJJS3zJ9jKciiQzTpTmF0Y2oXgL":  # NEW FILE_D
        local_file_path = "data/file_d_new.csv"
    
    if local_file_path and os.path.exists(local_file_path):
        try:
            with open(local_file_path, 'rb') as f:
                content = f.read()
            result = process_file_content(content)
            if result is not None:
                st.info(f"✅ Loaded from local file: {local_file_path}")
                return result
        except Exception as e:
            pass  # Continue to cloud download
    
    # Method 1: Try gdown if available (best for large files)
    if GDOWN_AVAILABLE:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                url = f"https://drive.google.com/uc?id={file_id}"
                output = tmp_file.name
                
                gdown.download(url, output, quiet=True, fuzzy=True)
                
                # Read the downloaded file
                with open(output, 'rb') as f:
                    content = f.read()
                
                # Clean up
                try:
                    os.unlink(output)
                except:
                    pass
                
                # Process the content (detect type and decompress if needed)
                result = process_file_content(content)
                if result is not None:
                    return result
                
        except Exception as e:
            # Check if it's a rate limit error
            error_msg = str(e).lower()
            if 'too many users' in error_msg or 'quota' in error_msg:
                # Silent fail on rate limit - will try alternative method
                pass
            # Otherwise silently try fallback
    
    # Method 2: Manual download (fallback)
    try:
        session = requests.Session()
        
        # Initial request
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = session.get(url, timeout=30, stream=False)
        
        content = response.content
        
        # Check for virus scan warning or download confirmation (handle silently)
        if b'virus scan warning' in content.lower() or b'download anyway' in content.lower() or content.startswith(b'<!DOCTYPE'):
            text = content.decode('utf-8', errors='ignore')
            
            # Check for rate limit message
            if 'too many users' in text.lower() or 'quota' in text.lower():
                return None  # Silent fail - rate limit
            
            # Try to find confirmation token
            confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', text)
            if confirm_match:
                confirm = confirm_match.group(1)
                url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm}"
                response = session.get(url, timeout=60, stream=False)
                content = response.content
            else:
                download_match = re.search(r'href="(/uc\?[^"]*export=download[^"]*)"', text)
                if download_match:
                    download_path = download_match.group(1).replace('&amp;', '&')
                    url = f"https://drive.google.com{download_path}"
                    response = session.get(url, timeout=60, stream=False)
                    content = response.content
                else:
                    return None  # Silent fail
        
        if response.status_code != 200:
            return None
        
        # Process the content
        return process_file_content(content)
            
    except Exception as e:
        return None  # Silent fail


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour (3600 seconds)
def load_json_from_gdrive(file_id):
    """Load JSON file from Google Drive - returns dict of SERP templates {template_key: html_string}
    Cached for 1 hour to prevent rate limits
    
    During development: If you hit rate limits, download file manually to 'data/file_b.json'
    """
    # Method 0: Try local file first (for development when rate limited)
    import os
    if file_id == "1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9":  # FILE_B
        local_file_path = "data/file_b.json"
        if os.path.exists(local_file_path):
            try:
                with open(local_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                st.info(f"✅ Loaded from local file: {local_file_path}")
                if isinstance(data, dict):
                    return data
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception as e:
                pass  # Continue to cloud download
    
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        # Return dict as-is: { "T8F75KL": "<html>...", ... }
        if isinstance(data, dict):
            return data
        
        # If it's a list, convert to dict (fallback for old format)
        if isinstance(data, list) and len(data) > 0:
            return data
        
        return None
    except Exception as e:
        # Silent fail - JSON templates are optional
        return None
