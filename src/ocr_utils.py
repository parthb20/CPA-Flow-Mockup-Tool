"""
OCR utilities for extracting text from screenshots
"""
import streamlit as st
from PIL import Image
import requests
from io import BytesIO

def extract_text_from_screenshot(screenshot_url):
    """
    Extract text from screenshot using OCR
    
    Args:
        screenshot_url: URL of the screenshot image
        
    Returns:
        str: Extracted text from the image, or empty string if OCR fails
    """
    try:
        import pytesseract
        
        # Download the screenshot
        response = requests.get(screenshot_url, timeout=10)
        if response.status_code != 200:
            return ""
        
        # Open image
        image = Image.open(BytesIO(response.content))
        
        # Perform OCR
        text = pytesseract.image_to_string(image)
        
        return text.strip()
        
    except ImportError:
        # pytesseract not installed, return empty
        return ""
    except Exception as e:
        # OCR failed, return empty
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_ocr_text(screenshot_url):
    """Cached version of OCR extraction to avoid redundant processing"""
    return extract_text_from_screenshot(screenshot_url)
