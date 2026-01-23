# -*- coding: utf-8 -*-
"""
Screenshot capture and processing functions
"""

import streamlit as st
import requests
import pandas as pd
from urllib.parse import quote, unquote

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False


@st.cache_data(ttl=604800, show_spinner=False)
def get_screenshot_url(url, device='mobile', full_page=False):
    """Generate ScreenshotOne API URL (cached for 7 days)"""
    try:
        # Try to get API key
        try:
            SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()
        except Exception:
            return None
        
        # Check if API key is configured
        if not SCREENSHOT_API_KEY:
            return None
        
        # Ensure URL is properly formatted
        if not url or pd.isna(url):
            return None
        
        url = str(url).strip()
        
        # Ensure URL starts with http/https
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Device viewport sizes - proper dimensions for each device type
        viewports = {
            'mobile': {'width': 390, 'height': 844},      # iPhone-like portrait
            'tablet': {'width': 1024, 'height': 768},     # iPad landscape
            'laptop': {'width': 1920, 'height': 1080}     # Full HD desktop
        }
        vp = viewports.get(device, viewports['mobile'])
        
        # Build ScreenshotOne API URL
        # Format: https://api.screenshotone.com/take?url=<url>&access_key=<key>&viewport_width=<w>&viewport_height=<h>
        encoded_url = quote(url, safe='')
        screenshot_url = f"https://api.screenshotone.com/take?url={encoded_url}&access_key={SCREENSHOT_API_KEY}&viewport_width={vp['width']}&viewport_height={vp['height']}&format=png&device_scale_factor=1"
        
        if full_page:
            screenshot_url += "&full_page=true"
        
        return screenshot_url
    except Exception:
        return None


def capture_page_with_fallback(url, device='mobile'):
    """
    Capture page - try Playwright first, fallback to screenshot API on 403
    
    Returns: (content, render_type)
    - content: HTML string (if Playwright works) or screenshot URL (if fallback)
    - render_type: 'html', 'screenshot', or 'error'
    
    Usage Example:
        content, render_type = capture_page_with_fallback(url, device='mobile')
        if render_type == 'html':
            # Render HTML directly
            preview_html, height, _ = render_mini_device_preview(content, is_url=False, device=device)
            st.components.v1.html(preview_html, height=height)
        elif render_type == 'screenshot':
            # Render screenshot URL
            screenshot_html = create_screenshot_html(content, device=device)
            preview_html, height, _ = render_mini_device_preview(screenshot_html, is_url=False, device=device, use_srcdoc=True)
            st.components.v1.html(preview_html, height=height)
        else:
            st.error("Failed to load")
    """
    # Try Playwright first
    html_content, error_code = capture_with_playwright(url, device)
    
    if html_content:
        return (html_content, 'html')
    
    # On 403 or error, use screenshot API as fallback
    if error_code in [403, 'error', 'no_playwright']:
        screenshot_url = get_screenshot_url(url, device=device, full_page=False)
        if screenshot_url:
            return (screenshot_url, 'screenshot')
    
    return (None, 'error')


def capture_with_playwright(url, device='mobile'):
    """
    Capture page using Playwright
    Returns HTML string if success, None if failed (or screenshot fallback HTML)
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        viewports = {
            'mobile': {'width': 390, 'height': 844},      # iPhone-like portrait
            'tablet': {'width': 1024, 'height': 768},     # iPad landscape
            'laptop': {'width': 1920, 'height': 1080}     # Full HD desktop
        }
        
        import random
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        user_agent = random.choice(user_agents)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-web-security']
            )
            
            context = browser.new_context(
                viewport=viewports[device],
                user_agent=user_agent
            )
            
            page = context.new_page()
            
            # Use 'domcontentloaded' instead of 'networkidle' - much faster and more reliable
            # networkidle often times out on sites with many background requests
            response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
            
            # Wait a bit for critical content to render
            page.wait_for_timeout(2000)
            
            # Check for 403 error - use screenshot API as fallback
            if response and response.status == 403:
                browser.close()
                screenshot_url = get_screenshot_url(url, device=device)
                if screenshot_url:
                    return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
                return None
            
            html_content = page.content()
            browser.close()
            
            # Verify we got actual content
            if html_content and len(html_content) > 100:
                return html_content
            return None
            
    except Exception as e:
        # ONLY use screenshot API on 403 errors - not for other errors!
        error_str = str(e).lower()
        if '403' in error_str or 'forbidden' in error_str:
            screenshot_url = get_screenshot_url(url, device=device)
            if screenshot_url:
                return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
        # Log error for debugging (will be caught by caller)
        import traceback
        print(f"Playwright error for {url}: {traceback.format_exc()}")
        return None
