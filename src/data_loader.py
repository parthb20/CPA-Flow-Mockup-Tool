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
                return process_file_content(content)
                
        except Exception as e:
            pass  # Silently try alternative
    
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
                    return None
        
        if response.status_code != 200:
            return None
        
        # Process the content
        return process_file_content(content)
            
    except Exception as e:
        return None


def load_json_from_gdrive(file_id):
    """Load JSON file from Google Drive - returns dict of SERP templates {template_key: html_string}"""
    # Method 1: Try gdown if available (best for large files)
    if GDOWN_AVAILABLE:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_file:
                url = f"https://drive.google.com/uc?id={file_id}"
                output = tmp_file.name
                
                gdown.download(url, output, quiet=True, fuzzy=True)
                
                # Read the downloaded file
                with open(output, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Clean up
                try:
                    os.unlink(output)
                except:
                    pass
                
                # Return dict as-is: { "T8F75KL": "<html>...", ... }
                if isinstance(data, dict):
                    return data
                
                # If it's a list, convert to dict (fallback for old format)
                if isinstance(data, list) and len(data) > 0:
                    return data
                
                return None
                
        except Exception as e:
            pass  # Silently try alternative
    
    # Method 2: Manual download with virus scan handling (fallback)
    try:
        session = requests.Session()
        
        # Initial request
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = session.get(url, timeout=30, stream=False)
        
        content = response.content
        
        # Check if Google Drive returned HTML error page
        if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html') or b'<title>Google Drive' in content[:1000]:
            # Try to find confirmation token for large files
            text = content.decode('utf-8', errors='ignore')
            
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
                    st.error("❌ Could not download SERP templates - check sharing settings")
                    return None
        
        if response.status_code != 200:
            st.error(f"❌ HTTP {response.status_code} when downloading SERP templates")
            return None
        
        # Check again if we got HTML instead of JSON
        if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
            st.error("❌ Google Drive returned HTML instead of JSON - check file sharing settings")
            with st.expander("🔍 Debug Info - Click to expand"):
                st.code(f"File ID: {file_id}", language="text")
                st.code(f"URL: {url}", language="text")
                st.code(f"Response preview:\n{content[:800].decode('utf-8', errors='ignore')}", language="html")
            return None
        
        # Parse JSON
        try:
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            st.error(f"❌ Invalid JSON in SERP templates file: {str(e)}")
            with st.expander("🔍 Debug Info - Click to expand"):
                st.code(f"File ID: {file_id}", language="text")
                st.code(f"URL: {url}", language="text")
                preview = content[:800].decode('utf-8', errors='ignore')
                st.code(f"Response preview:\n{preview}", language="text")
                st.info("💡 **Possible fixes:**\n1. Check file is shared as 'Anyone with link can view'\n2. Verify FILE_B_ID in src/config.py is correct\n3. File must be a valid JSON file (not Google Doc)")
            return None
        
        # Return dict as-is: { "T8F75KL": "<html>...", ... }
        if isinstance(data, dict):
            return data
        
        # If it's a list, convert to dict (fallback for old format)
        if isinstance(data, list) and len(data) > 0:
            return data
        
        return None
        
    except Exception as e:
        st.error(f"❌ Error loading SERP templates: {str(e)}")
        return None
