"""
Data loading functions for Google Drive files
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
                
                # Read as CSV - Try different parsing strategies silently
                df = None
                error_msgs = []
                
                # Strategy 1: QUOTE_ALL (assume all fields quoted)
                try:
                    df = pd.read_csv(
                        BytesIO(decompressed), 
                        dtype=str, 
                        encoding='utf-8',
                        engine='python',
                        quoting=csv.QUOTE_ALL,
                        escapechar='\\',
                        on_bad_lines='warn'
                    )
                except Exception as e:
                    error_msgs.append(f"QUOTE_ALL: {str(e)[:100]}")
                
                # Strategy 2: QUOTE_MINIMAL (default quoting)
                if df is None or len(df) == 0:
                    try:
                        df = pd.read_csv(
                            BytesIO(decompressed), 
                            dtype=str, 
                            encoding='utf-8',
                            engine='python',
                            quoting=csv.QUOTE_MINIMAL,
                            on_bad_lines='warn'
                        )
                    except Exception as e:
                        error_msgs.append(f"QUOTE_MINIMAL: {str(e)[:100]}")
                
                # Strategy 3: No quoting (raw parsing)
                if df is None or len(df) == 0:
                    try:
                        df = pd.read_csv(
                            BytesIO(decompressed), 
                            dtype=str, 
                            encoding='utf-8',
                            engine='python',
                            quoting=csv.QUOTE_NONE,
                            on_bad_lines='warn'
                        )
                    except Exception as e:
                        error_msgs.append(f"QUOTE_NONE: {str(e)[:100]}")
                
                if df is None or len(df) == 0:
                    st.error(f"❌ All parsing strategies failed: {'; '.join(error_msgs)}")
                    return None
                
                return df
            except Exception as e:
                st.error(f"❌ Error decompressing GZIP: {str(e)}")
                import traceback
                st.error(f"Traceback: {traceback.format_exc()[:500]}")
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
            # Try as CSV
            try:
                df = pd.read_csv(
                    StringIO(content.decode('utf-8')), 
                    dtype=str, 
                    on_bad_lines='skip',
                    encoding='utf-8',
                    engine='python'
                )
                return df
            except Exception as e:
                st.error(f"❌ CSV parse error: {str(e)}")
                import traceback
                st.error(f"Traceback: {traceback.format_exc()[:500]}")
                return None
                
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        return None


def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive - handles CSV, ZIP, GZIP, and large file virus scan"""
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


def load_json_from_gdrive(file_id):
    """Load JSON file from Google Drive - returns dict of SERP templates {template_key: html_string}"""
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
