# -*- coding: utf-8 -*-
"""
Screenshot capture with Playwright (SIMPLIFIED VERSION)
Removed: Firefox fallback, session warming, excessive stealth JS, debug prints
Kept: Core functionality, 403 handling, Screenshot API fallback
"""

import streamlit as st
import requests
import pandas as pd
import re
import random
from urllib.parse import quote, unquote, urlparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False


def clean_url_for_capture(url):
    """Clean URL: remove protocol, www, query params. Keep only domain + path"""
    if not url or pd.isna(url):
        return None
    
    url = str(url).strip()
    url = re.sub(r'^https?://', '', url)  # Remove protocol
    url = re.sub(r'^www\.', '', url)  # Remove www
    
    # Keep trailing slash if present
    if '?' in url:
        path_before_query = url.split('?')[0]
        url = path_before_query
    
    url = re.sub(r'\{[^}]+\}', '', url)  # Remove {macros}
    
    return url


@st.cache_data(ttl=604800, show_spinner=False)
def get_screenshot_url(url, device='mobile', full_page=False, try_cleaned=False):
    """
    Generate ScreenshotOne API URL (cached for 7 days)
    Simple and reliable - works when Playwright fails
    """
    try:
        # Get API key
        try:
            SCREENSHOT_API_KEY = st.secrets.get("SCREENSHOT_API_KEY", "").strip()
        except:
            return None
        
        if not SCREENSHOT_API_KEY or not url or pd.isna(url):
            return None
        
        url = str(url).strip()
        
        # Clean URL if requested (for 403 fallback)
        if try_cleaned:
            cleaned = clean_url_for_capture(url)
            if cleaned:
                url = cleaned
        
        # Ensure proper format
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Device viewports
        viewports = {
            'mobile': {'width': 390, 'height': 844},
            'tablet': {'width': 1024, 'height': 768},
            'laptop': {'width': 1920, 'height': 1080}
        }
        viewport = viewports.get(device, viewports['mobile'])
        
        # Build API URL
        params = {
            'url': url,
            'access_key': SCREENSHOT_API_KEY,
            'viewport_width': viewport['width'],
            'viewport_height': viewport['height'],
            'device_scale_factor': 1,
            'format': 'png',
            'block_ads': 'true',
            'block_cookie_banners': 'true',
            'block_trackers': 'true',
            'dark_mode': 'false',
            'full_page': 'true' if full_page else 'false',
            'delay': 1
        }
        
        query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"https://api.screenshotone.com/take?{query_string}"
        
    except Exception:
        return None


def _handle_403_fallback(url, device):
    """
    Unified 403 handler - returns Screenshot API HTML or None
    Used by all 403 code paths for consistency
    """
    screenshot_url = get_screenshot_url(url, device=device, try_cleaned=True)
    if screenshot_url:
        return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
    return None


def capture_with_playwright(url, device='mobile', retry_count=1, use_firefox=False, try_cleaned_url=False):
    """
    Capture page with Playwright (SIMPLIFIED)
    
    What was removed:
    - Firefox fallback (doesn't help with Forbes)
    - Session warming (doesn't bypass Forbes)
    - 150+ lines of unnecessary stealth JS
    - Debug print statements
    
    What remains:
    - Core stealth techniques that work
    - 403 detection and fallback
    - Screenshot API integration
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    # Clean URL if requested
    if try_cleaned_url:
        cleaned = clean_url_for_capture(url)
        if cleaned and not cleaned.startswith(('http://', 'https://')):
            url = f"https://{cleaned}"
    
    # Random user agent
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    user_agent = random.choice(user_agents)
    
    viewports = {
        'mobile': {'width': 390, 'height': 844},
        'tablet': {'width': 1024, 'height': 768},
        'laptop': {'width': 1920, 'height': 1080}
    }
    viewport = viewports.get(device, viewports['mobile'])
    
    timeout = 30000  # 30 seconds
    
    try:
        with sync_playwright() as p:
            # Use Chromium only (Firefox doesn't help)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            
            # Create context with realistic settings
            context = browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                color_scheme="light",
                locale='en-US',
                timezone_id='America/New_York',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'DNT': '1',
                }
            )
            
            page = context.new_page()
            
            # Essential stealth JS (only what works)
            page.add_init_script("""
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                
                // Add chrome object
                if (!window.chrome) {
                    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
                }
                
                // Hide chat widgets and AI assistants
                const hideSelectors = [
                    '[class*="chat" i]', '[class*="assistant" i]', '[id*="chat" i]', 
                    '[id*="assistant" i]', '[class*="intercom" i]', '[class*="drift" i]',
                    '[class*="zendesk" i]', '[class*="livechat" i]', '[class*="tawk" i]',
                    '[class*="tidio" i]', '[class*="freshchat" i]', '[class*="crisp" i]',
                    'iframe[src*="chat" i]', 'iframe[title*="chat" i]'
                ].join(',');
                
                // Add CSS to hide widgets immediately
                const style = document.createElement('style');
                style.textContent = `
                    ${hideSelectors} {
                        display: none !important;
                        visibility: hidden !important;
                        opacity: 0 !important;
                        position: absolute !important;
                        left: -9999px !important;
                    }
                `;
                if (document.head) {
                    document.head.appendChild(style);
                } else {
                    document.addEventListener('DOMContentLoaded', () => {
                        document.head.appendChild(style);
                    });
                }
                
                // Remove widgets after page load
                window.addEventListener('load', () => {
                    document.querySelectorAll(hideSelectors).forEach(el => {
                        if (el) el.remove();
                    });
                });
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (params) => (
                    params.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(params)
                );
            """)
            
            page.set_default_navigation_timeout(timeout)
            page.on("dialog", lambda dialog: dialog.dismiss())
            
            # Try navigation
            response = None
            error = None
            
            try:
                response = page.goto(url, wait_until='domcontentloaded', timeout=timeout)
            except PlaywrightTimeoutError:
                try:
                    response = page.goto(url, wait_until='commit', timeout=timeout // 2)
                except Exception as e:
                    error = e
            except Exception as e:
                error = e
            
            # Handle no response
            if not response:
                browser.close()
                # Check if 403 in error
                if error and ('403' in str(error).lower() or 'forbidden' in str(error).lower()):
                    if not try_cleaned_url:
                        import time
                        time.sleep(random.uniform(1, 2))
                        return capture_with_playwright(url, device, retry_count, False, try_cleaned_url=True)
                    return _handle_403_fallback(url, device)
                return None
            
            # Handle error status codes
            if response.status >= 400:
                browser.close()
                if response.status == 403:
                    # Try cleaned URL once, then fallback to Screenshot API
                    if not try_cleaned_url:
                        import time
                        time.sleep(random.uniform(1, 2))
                        return capture_with_playwright(url, device, retry_count, False, try_cleaned_url=True)
                    return _handle_403_fallback(url, device)
                # Other errors - use Screenshot API
                return _handle_403_fallback(url, device)
            
            # Success - get content
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except:
                pass
            
            html_content = page.content()
            browser.close()
            
            if html_content and len(html_content) > 100:
                return html_content
            
            return None
            
    except Exception as e:
        error_str = str(e).lower()
        
        # Handle 403 in exception
        if '403' in error_str or 'forbidden' in error_str:
            if not try_cleaned_url:
                import time
                time.sleep(random.uniform(1, 2))
                return capture_with_playwright(url, device, retry_count, False, try_cleaned_url=True)
            return _handle_403_fallback(url, device)
        
        return None
