"""
Screenshot capture and processing functions
"""

import streamlit as st
import requests
from urllib.parse import quote

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False


def get_screenshot_url(url, device='mobile', full_page=False):
    """Generate thum.io screenshot URL"""
    try:
        SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()
        THUMIO_REFERER_DOMAIN = st.secrets.get("THUMIO_REFERER_DOMAIN", "").strip()
        
        # Ensure URL is properly formatted
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Device viewport sizes
        viewports = {
            'mobile': {'width': 390, 'height': 844},
            'tablet': {'width': 820, 'height': 1180},
            'laptop': {'width': 1440, 'height': 900}
        }
        vp = viewports.get(device, viewports['mobile'])
        
        # For referer-based keys, use simple format
        if THUMIO_REFERER_DOMAIN:
            screenshot_url = f"https://image.thum.io/get/{url}"
            return screenshot_url
        
        # For auth token keys, add options with auth
        if SCREENSHOT_API_KEY:
            options = [f"width/{vp['width']}"]
            if full_page:
                options.append("fullpage")
            else:
                options.append(f"height/{vp['height']}")
            options.append(f"auth/{SCREENSHOT_API_KEY}")
            screenshot_url = f"https://image.thum.io/get/{'/'.join(options)}/{url}"
            return screenshot_url
        
        # FREE TIER (default): Simple format
        encoded_url = quote(url, safe='')
        screenshot_url = f"https://image.thum.io/get/{encoded_url}"
        return screenshot_url
    except Exception as e:
        return None


def capture_with_playwright(url, device='mobile'):
    """Capture page using Playwright"""
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        clean_url = url.split('?')[0] if '?' in url else url
        clean_url = clean_url.split('#')[0] if '#' in clean_url else clean_url
        
        viewports = {
            'mobile': {'width': 390, 'height': 844},
            'tablet': {'width': 820, 'height': 1180},
            'laptop': {'width': 1440, 'height': 900}
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
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            
            context = browser.new_context(
                viewport=viewports[device],
                user_agent=user_agent
            )
            
            page = context.new_page()
            page.goto(clean_url, wait_until='networkidle', timeout=30000)
            
            html_content = page.content()
            
            browser.close()
            return html_content
    except Exception as e:
        return None
