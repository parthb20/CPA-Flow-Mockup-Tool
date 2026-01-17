# -*- coding: utf-8 -*-
"""
Data loading functions for Google Drive files
"""

import requests
import pandas as pd
import json
import csv
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

# Check pandas version for on_bad_lines compatibility
try:
    pd_version = pd.__version__
    pd_major, pd_minor = map(int, pd_version.split('.')[:2])
    HAS_ON_BAD_LINES = (pd_major > 1) or (pd_major == 1 and pd_minor >= 3)
except:
    HAS_ON_BAD_LINES = False


def process_file_content(content):
    """Process file content - detect type and decompress if needed"""
    import streamlit as st
    
    def safe_st_error(msg):
        """Safely call st.error, catching thread-related issues"""
        try:
            st.error(msg)
        except:
            pass  # Ignore errors when called from thread
    
    def safe_st_info(msg):
        """Safely call st.info, catching thread-related issues"""
        try:
            st.info(msg)
        except:
            pass  # Ignore errors when called from thread
    
    try:
        # Check if Google Drive returned HTML error page
        if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html') or b'<title>Google Drive' in content[:1000]:
            safe_st_error("❌ Could not download file - check sharing settings")
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
                
                # Read as CSV with comprehensive options - try multiple strategies
                df = None
                read_csv_kwargs = {
                    'dtype': str,
                    'encoding': 'utf-8',
                    'engine': 'python',
                    'quoting': csv.QUOTE_MINIMAL,
                    'skipinitialspace': True,
                    'low_memory': False
                }
                if HAS_ON_BAD_LINES:
                    read_csv_kwargs['on_bad_lines'] = 'skip'
                else:
                    read_csv_kwargs['error_bad_lines'] = False
                    read_csv_kwargs['warn_bad_lines'] = False
                
                try:
                    # Strategy 1: Python engine with error handling
                    df = pd.read_csv(BytesIO(decompressed), **read_csv_kwargs)
                except Exception as e1:
                    try:
                        # Strategy 2: Try with different quote handling
                        read_csv_kwargs['quoting'] = csv.QUOTE_ALL
                        df = pd.read_csv(BytesIO(decompressed), **read_csv_kwargs)
                    except Exception as e2:
                        # Strategy 3: Manual CSV parsing
                        try:
                            decoded = decompressed.decode('utf-8', errors='replace')
                            csv_reader = csv.DictReader(StringIO(decoded))
                            rows = []
                            for row in csv_reader:
                                rows.append(row)
                            if rows:
                                df = pd.DataFrame(rows, dtype=str)
                        except Exception as e3:
                            raise e1  # Raise original error
                
                return df
            except Exception as e:
                safe_st_error(f"❌ Error decompressing GZIP: {str(e)}")
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
                        # Try multiple parsing strategies
                        df = None
                        read_csv_kwargs = {
                            'dtype': str,
                            'encoding': 'utf-8',
                            'engine': 'python',
                            'quoting': csv.QUOTE_MINIMAL,
                            'skipinitialspace': True,
                            'low_memory': False
                        }
                        if HAS_ON_BAD_LINES:
                            read_csv_kwargs['on_bad_lines'] = 'skip'
                        else:
                            read_csv_kwargs['error_bad_lines'] = False
                            read_csv_kwargs['warn_bad_lines'] = False
                        
                        try:
                            df = pd.read_csv(BytesIO(csv_content), **read_csv_kwargs)
                        except Exception:
                            try:
                                read_csv_kwargs['quoting'] = csv.QUOTE_ALL
                                df = pd.read_csv(BytesIO(csv_content), **read_csv_kwargs)
                            except Exception:
                                # Manual CSV parsing
                                decoded = csv_content.decode('utf-8', errors='replace')
                                csv_reader = csv.DictReader(StringIO(decoded))
                                rows = []
                                for row in csv_reader:
                                    rows.append(row)
                                if rows:
                                    df = pd.DataFrame(rows, dtype=str)
                        return df
                    else:
                        safe_st_error("❌ No CSV file found in ZIP")
                        return None
            except Exception as e:
                safe_st_error(f"❌ Error extracting ZIP: {str(e)}")
                return None
        else:
            # Try as CSV with robust parsing options
            try:
                # Increase field size limit for large fields
                csv.field_size_limit(100000000)  # 100MB per field
                
                # Try multiple encoding options
                encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                df = None
                last_error = None
                
                for encoding in encodings:
                    try:
                        # Decode content with current encoding
                        try:
                            decoded_content = content.decode(encoding)
                        except UnicodeDecodeError:
                            # Try with error handling
                            decoded_content = content.decode(encoding, errors='replace')
                        
                        # Try reading CSV with multiple strategies
                        # Build read_csv kwargs based on pandas version
                        read_csv_kwargs = {
                            'dtype': str,
                            'encoding': encoding,
                            'engine': 'python',
                            'quoting': csv.QUOTE_MINIMAL,
                            'skipinitialspace': True,
                            'low_memory': False
                        }
                        if HAS_ON_BAD_LINES:
                            read_csv_kwargs['on_bad_lines'] = 'skip'
                        else:
                            read_csv_kwargs['error_bad_lines'] = False
                            read_csv_kwargs['warn_bad_lines'] = False
                        
                        # Strategy 1: Standard pandas with error handling
                        try:
                            df = pd.read_csv(StringIO(decoded_content), **read_csv_kwargs)
                            if df is not None and len(df) > 0:
                                break
                        except Exception as e1:
                            last_error = e1
                            # Strategy 2: Try with different quote handling
                            try:
                                read_csv_kwargs['quoting'] = csv.QUOTE_ALL
                                df = pd.read_csv(StringIO(decoded_content), **read_csv_kwargs)
                                if df is not None and len(df) > 0:
                                    break
                            except Exception as e2:
                                # Strategy 3: Try with C engine (faster but less forgiving)
                                try:
                                    read_csv_kwargs['quoting'] = csv.QUOTE_MINIMAL
                                    read_csv_kwargs['engine'] = 'c'
                                    df = pd.read_csv(StringIO(decoded_content), **read_csv_kwargs)
                                    if df is not None and len(df) > 0:
                                        break
                                except Exception as e3:
                                    # Strategy 4: Manual CSV parsing with csv module (most robust)
                                    try:
                                        csv_reader = csv.DictReader(StringIO(decoded_content))
                                        rows = []
                                        for row in csv_reader:
                                            rows.append(row)
                                        if rows:
                                            df = pd.DataFrame(rows, dtype=str)
                                            break
                                    except Exception as e4:
                                        last_error = e4
                                        continue
                        
                    except Exception as e:
                        last_error = e
                        continue
                
                if df is not None and len(df) > 0:
                    return df
                else:
                    safe_st_error(f"❌ CSV parse error: {str(last_error) if last_error else 'Could not parse CSV with any method'}")
                    safe_st_info("💡 Tip: Check if CSV has proper quoting for fields containing commas")
                    return None
                    
            except Exception as e:
                safe_st_error(f"❌ CSV parse error: {str(e)}")
                safe_st_info("💡 Tip: The CSV file may have formatting issues. Try opening it in Excel and re-saving as CSV.")
                return None
                
    except Exception as e:
        safe_st_error(f"❌ Error processing file: {str(e)}")
        return None


def load_csv_from_gdrive(file_id):
    """Load CSV from Google Drive - handles CSV, ZIP, GZIP, and large file virus scan"""
    try:
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
    except Exception as e:
        # Catch any unexpected errors to prevent thread crashes
        return None


def load_json_from_gdrive(file_id):
    """Load JSON file from Google Drive - returns dict of SERP templates {template_key: html_string}"""
    import streamlit as st
    
    def safe_st_error(msg):
        """Safely call st.error, catching thread-related issues"""
        try:
            st.error(msg)
        except:
            pass  # Ignore errors when called from thread
    
    try:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Return dict as-is: { "T8F75KL": "<html>...", ... }
        if isinstance(data, dict):
            return data
        
        # If it's a list, convert to dict (fallback for old format)
        if isinstance(data, list) and len(data) > 0:
            return data
        
        return None
    except Exception as e:
        safe_st_error(f"Error loading SERP templates: {str(e)}")
        return None
