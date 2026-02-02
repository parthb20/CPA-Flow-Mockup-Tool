# -*- coding: utf-8 -*-
"""
Screenshot capture and processing functions with enhanced anti-detection
"""

import streamlit as st
import requests
import pandas as pd
import re
from urllib.parse import quote, unquote, urlparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False


def clean_url_for_capture(url):
    """
    Clean URL for screenshot capture:
    - Remove https://, http://, www.
    - Trim everything after macros ({clickId}, {click}, etc.)
    - Keep domain + path + first query param before macros
    
    Examples:
        https://www.forbes.com/advisor/m/sports-streaming/?utm_campaign=streaming-services&campaign_id=218804&mcid={clickId}
        → forbes.com/advisor/m/sports-streaming/?utm_campaign=streaming-services&campaign_id=218804
    """
    if not url or pd.isna(url):
        return None
    
    url = str(url).strip()
    
    # Remove protocol
    url = re.sub(r'^https?://', '', url)
    
    # Remove www.
    url = re.sub(r'^www\.', '', url)
    
    # Trim after macro parameters (anything with {})
    # Find first occurrence of parameter with {macro}
    macro_match = re.search(r'[&?][\w_]+=\{[^}]+\}', url)
    if macro_match:
        url = url[:macro_match.start()]
    
    # Also remove any remaining {macros} in the URL
    url = re.sub(r'\{[^}]+\}', '', url)
    
    # Clean up trailing & or ?
    url = url.rstrip('?&')
    
    return url


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
        
        # Build ScreenshotOne API URL with caching enabled
        # Format: https://api.screenshotone.com/take?url=<url>&access_key=<key>&viewport_width=<w>&viewport_height=<h>
        # cache=true: Use ScreenshotOne's cache (saves API requests & costs)
        # cache_ttl=2592000: Cache for 30 days (2592000 seconds)
        encoded_url = quote(url, safe='')
        screenshot_url = f"https://api.screenshotone.com/take?url={encoded_url}&access_key={SCREENSHOT_API_KEY}&viewport_width={vp['width']}&viewport_height={vp['height']}&format=png&device_scale_factor=1&cache=true&cache_ttl=2592000"
        
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


@st.cache_data(ttl=3600, show_spinner=False)
def capture_with_playwright(url, device='mobile', retry_count=1, use_firefox=False):
    """
    Enhanced Playwright capture with anti-detection, light theme, and retry logic.
    Cached for 1 hour. Uses techniques from advanced screenshotter to bypass 403/bot detection.
    
    Returns: HTML string if success, screenshot fallback HTML if 403, None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    # Clean URL before capture
    cleaned_url = clean_url_for_capture(url)
    if cleaned_url:
        # Reconstruct full URL
        if not cleaned_url.startswith(('http://', 'https://')):
            url = f"https://{cleaned_url}"
    
    import random
    
    # Enhanced user agents rotation
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
    ]
    user_agent = random.choice(user_agents)
    
    viewports = {
        'mobile': {'width': 390, 'height': 844},
        'tablet': {'width': 1024, 'height': 768},
        'laptop': {'width': 1920, 'height': 1080}
    }
    viewport = viewports.get(device, viewports['mobile'])
    
    # Adaptive timeout (increase on retries)
    timeout = min(30000 * retry_count, 90000)
    
    try:
        with sync_playwright() as p:
            # Use Firefox on retries (less detected)
            browser_type = p.firefox if (use_firefox or retry_count > 1) else p.chromium
            
            # Enhanced browser config with anti-detection
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                f'--window-size={viewport["width"]},{viewport["height"]}',
                '--disable-infobars',
                '--disable-extensions'
            ] if browser_type == p.chromium else []
            
            browser = browser_type.launch(headless=True, args=browser_args if browser_args else None)
            
            # Enhanced context with realistic fingerprint + FORCE LIGHT THEME
            context = browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                color_scheme="light",  # FORCE LIGHT MODE
                locale='en-US',
                timezone_id='America/New_York',
                device_scale_factor=1,
                has_touch=False,
                java_script_enabled=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1'
                }
            )
            
            page = context.new_page()
            
            # Inject anti-detection scripts
            page.add_init_script("""
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override the permissions API
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Add chrome object for Chromium
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                }
            """)
            
            page.set_default_navigation_timeout(timeout)
            
            # Handle dialogs automatically
            page.on("dialog", lambda dialog: dialog.dismiss())
            
            # Try navigation with fallback strategies
            navigation_success = False
            try:
                response = page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                if response and response.status < 400:
                    navigation_success = True
            except PlaywrightTimeoutError:
                try:
                    # Fallback to 'commit' if domcontentloaded times out
                    page.goto(url, wait_until='commit', timeout=timeout // 2)
                    navigation_success = True
                except:
                    pass
            
            if not navigation_success:
                browser.close()
                return None
            
            # Check for 403 - fallback to screenshot API
            if response and response.status == 403:
                browser.close()
                screenshot_url = get_screenshot_url(url, device=device)
                if screenshot_url:
                    return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
                return None
            
            # Add human-like delay
            page.wait_for_timeout(random.randint(1500, 3000))
            
            # Wait for network idle (with timeout)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except PlaywrightTimeoutError:
                pass  # Continue anyway
            
            # Scroll to trigger lazy loading
            try:
                page.evaluate("""
                    async () => {
                        await new Promise((resolve) => {
                            let totalHeight = 0;
                            const distance = 100;
                            const timer = setInterval(() => {
                                const scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if(totalHeight >= scrollHeight){
                                    window.scrollTo(0, 0);
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """)
            except:
                pass
            
            # Small delay after scroll
            page.wait_for_timeout(500)
            
            # Get HTML content
            html_content = page.content()
            browser.close()
            
            # Verify we got actual content
            if html_content and len(html_content) > 100:
                return html_content
            
            return None
            
    except Exception as e:
        error_str = str(e).lower()
        
        # Fallback to screenshot API on 403
        if '403' in error_str or 'forbidden' in error_str:
            screenshot_url = get_screenshot_url(url, device=device)
            if screenshot_url:
                return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
        
        # Retry with Firefox if first attempt failed (and not already using Firefox)
        if retry_count < 2 and not use_firefox:
            import time
            time.sleep(random.uniform(2, 4))  # Random delay before retry
            return capture_with_playwright(url, device, retry_count + 1, use_firefox=True)
        
        return None
