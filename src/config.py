# -*- coding: utf-8 -*-
"""
OCR utilities for extracting text from screenshots
Uses EasyOCR which doesn't require system dependencies
"""

import streamlit as st
from PIL import Image
import requests
from io import BytesIO

# Global reader instance (cached)
_ocr_reader = None

def get_ocr_reader():
    """Get or create EasyOCR reader instance (cached)"""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            st.warning(f"OCR initialization failed: {e}")
            _ocr_reader = False
    return _ocr_reader if _ocr_reader is not False else None


@st.cache_data(ttl=604800, show_spinner=False)
def extract_text_from_screenshot_url(screenshot_url):
    """
    Extract text from a screenshot URL using OCR
    
    Args:
        screenshot_url: URL of the screenshot image
        
    Returns:
        str: Extracted text, or empty string if OCR fails
    """
    if not screenshot_url:
        return ""
    
    try:
        # Get OCR reader
        reader = get_ocr_reader()
        if not reader:
            return ""
        
        # Download image
        response = requests.get(screenshot_url, timeout=10)
        if response.status_code != 200:
            return ""
        
        # Convert to PIL Image
        image = Image.open(BytesIO(response.content))
        
        # Run OCR
        results = reader.readtext(image)
        
        # Extract text from results
        extracted_text = " ".join([text for (bbox, text, prob) in results if prob > 0.5])
        
        return extracted_text
        
    except Exception as e:
        # Silent fail - OCR is optional
        return ""


def get_page_text_with_ocr_fallback(page_url, screenshot_url):
    """
    Get page text, using OCR on screenshot as fallback
    
    Args:
        page_url: URL of the page
        screenshot_url: URL of the screenshot (fallback)
        
    Returns:
        str: Page text or OCR text from screenshot
    """
    # Try to fetch page content first
    try:
        from src.similarity import fetch_page_content
        page_text = fetch_page_content(page_url)
        if page_text and len(page_text) > 100:
            return page_text
    except:
        pass
    
    # Fallback to OCR if page fetch failed
    if screenshot_url:
        return extract_text_from_screenshot_url(screenshot_url)
    
    return ""
