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
    - Remove ALL query parameters (everything after ?)
    - Keep only: domain + path
    
    Examples:
        https://www.forbes.com/advisor/m/sports-streaming/?utm_campaign=streaming-services&campaign_id=218804&mcid={clickId}
        → forbes.com/advisor/m/sports-streaming/
    """
    if not url or pd.isna(url):
        return None
    
    url = str(url).strip()
    
    # Remove protocol
    url = re.sub(r'^https?://', '', url)
    
    # Remove www.
    url = re.sub(r'^www\.', '', url)
    
    # Store if URL originally had trailing slash before query params
    has_trailing_slash = False
    if '?' in url:
        path_before_query = url.split('?')[0]
        has_trailing_slash = path_before_query.endswith('/')
        url = path_before_query
    
    # Remove any {macros} that might be in the path
    url = re.sub(r'\{[^}]+\}', '', url)
    
    # Keep trailing slash if original URL had it (important for some sites!)
    if has_trailing_slash and not url.endswith('/'):
        url = url + '/'
    
    return url


@st.cache_data(ttl=604800, show_spinner=False)
def get_screenshot_url(url, device='mobile', full_page=False, try_cleaned=False):
    """
    Generate ScreenshotOne API URL (cached for 7 days)
    
    Args:
        url: URL to capture
        device: Device type
        full_page: Capture full page or viewport
        try_cleaned: If True, remove all tracking params (fallback for 403 errors)
    """
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
        
        # Only clean URL if explicitly requested (fallback for 403 errors)
        if try_cleaned:
            cleaned_url = clean_url_for_capture(url)
            if cleaned_url:
                url = cleaned_url
        
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
def capture_with_playwright(url, device='mobile', retry_count=1, use_firefox=False, try_cleaned_url=False):
    """
    Enhanced Playwright capture with anti-detection, light theme, and retry logic.
    Cached for 1 hour. Uses techniques from advanced screenshotter to bypass 403/bot detection.
    
    Args:
        url: URL to capture
        device: Device type (mobile, tablet, laptop)
        retry_count: Current retry attempt
        use_firefox: Use Firefox instead of Chromium
        try_cleaned_url: If True, remove all tracking params (fallback for 403 errors)
    
    Returns: HTML string if success, screenshot fallback HTML if 403, None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    # Only clean URL if explicitly requested (fallback for 403 errors)
    if try_cleaned_url:
        cleaned_url = clean_url_for_capture(url)
        if cleaned_url:
            # Reconstruct full URL
            if not cleaned_url.startswith(('http://', 'https://')):
                url = f"https://{cleaned_url}"
    
    import random
    
    # MASSIVELY EXPANDED user agents rotation (12+ different agents)
    user_agents = [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Chrome Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        # Firefox Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        # Firefox Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        # Safari Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        # Edge Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
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
            # Add random referer to appear more like real traffic
            referers = [
                'https://www.google.com/',
                'https://www.bing.com/',
                'https://www.yahoo.com/',
                'https://www.duckduckgo.com/',
            ]
            referer = random.choice(referers)
            
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
                    'Sec-Fetch-Site': 'cross-site',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1',
                    'Referer': referer  # Random referer makes traffic look organic
                }
            )
            
            page = context.new_page()
            
            # ULTRA-ENHANCED anti-detection scripts (stealth mode)
            page.add_init_script("""
                // 1. Hide webdriver property (critical)
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
                
                // 2. Override automation property
                Object.defineProperty(navigator, 'automation', {
                    get: () => undefined,
                    configurable: true
                });
                
                // 3. Chrome object (make it look real)
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                }
                
                // 4. Override permissions API
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // 5. Mock plugins (more realistic)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: ""},
                            description: "",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        }
                    ]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Mock platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // Mock hardwareConcurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                // Mock deviceMemory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
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
                
                // Override toString to hide that properties are modified
                const originalToString = Function.prototype.toString;
                Function.prototype.toString = function() {
                    if (this === navigator.webdriver) {
                        return 'function webdriver() { [native code] }';
                    }
                    return originalToString.call(this);
                };
                
                // Mock connection
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false
                    })
                });
                
                // 6. Canvas fingerprint noise (makes each session unique)
                const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function() {
                    const imageData = originalGetImageData.apply(this, arguments);
                    // Add tiny random noise (invisible to eye, defeats fingerprinting)
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        if (Math.random() < 0.001) { // Only 0.1% of pixels
                            imageData.data[i] = imageData.data[i] ^ 1; // Flip one bit
                        }
                    }
                    return imageData;
                };
                
                // 7. WebGL fingerprint randomization
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.'; // Fake vendor
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine'; // Fake renderer
                    }
                    return getParameter.call(this, parameter);
                };
                
                // 8. Battery API (make it look like not charging)
                if (navigator.getBattery) {
                    const originalGetBattery = navigator.getBattery;
                    navigator.getBattery = function() {
                        return Promise.resolve({
                            charging: false,
                            chargingTime: Infinity,
                            dischargingTime: 5400,
                            level: 0.75
                        });
                    };
                }
            """)
            
            page.set_default_navigation_timeout(timeout)
            
            # Handle dialogs automatically
            page.on("dialog", lambda dialog: dialog.dismiss())
            
            # SESSION WARMING: Visit homepage first to get cookies (helps bypass SOME 403s)
            if retry_count == 1 and not try_cleaned_url:
                try:
                    # Extract domain from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    homepage = f"{parsed.scheme}://{parsed.netloc}"
                    
                    # Visit homepage briefly to establish session
                    home_response = page.goto(homepage, wait_until='domcontentloaded', timeout=10000)
                    import time
                    time.sleep(random.uniform(0.5, 1.5))  # Human-like delay
                    
                    # Scroll a bit (human behavior)
                    page.evaluate("window.scrollTo(0, 100);")
                    time.sleep(random.uniform(0.3, 0.7))
                except:
                    pass  # If homepage fails, continue anyway
            
            # Try navigation with fallback strategies
            navigation_success = False
            response = None
            try:
                response = page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                if response and response.status < 400:
                    navigation_success = True
            except PlaywrightTimeoutError:
                try:
                    # Fallback to 'commit' if domcontentloaded times out
                    response = page.goto(url, wait_until='commit', timeout=timeout // 2)
                    navigation_success = True
                except:
                    pass
            
            if not navigation_success:
                browser.close()
                return None
            
            # Check for 403 - try with cleaned URL first, then screenshot API
            if response and response.status == 403:
                browser.close()
                # If not already trying cleaned URL, retry with cleaned URL
                if not try_cleaned_url:
                    import time
                    time.sleep(random.uniform(1, 2))
                    return capture_with_playwright(url, device, retry_count, use_firefox, try_cleaned_url=True)
                # If cleaned URL also failed, use screenshot API
                screenshot_url = get_screenshot_url(url, device=device, try_cleaned=True)
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
        
        # On 403 error, try with cleaned URL first (remove tracking params)
        if ('403' in error_str or 'forbidden' in error_str) and not try_cleaned_url:
            import time
            time.sleep(random.uniform(1, 2))
            # Retry with cleaned URL (remove all tracking params)
            return capture_with_playwright(url, device, retry_count, use_firefox, try_cleaned_url=True)
        
        # If cleaned URL also failed, fallback to screenshot API
        if '403' in error_str or 'forbidden' in error_str:
            screenshot_url = get_screenshot_url(url, device=device, try_cleaned=True)
            if screenshot_url:
                return f'<!-- SCREENSHOT_FALLBACK --><img src="{screenshot_url}" style="width:100%;height:auto;" />'
        
        # Retry with Firefox if first attempt failed (and not already using Firefox or cleaned URL)
        if retry_count < 2 and not use_firefox and not try_cleaned_url:
            import time
            time.sleep(random.uniform(2, 4))  # Random delay before retry
            return capture_with_playwright(url, device, retry_count + 1, use_firefox=True, try_cleaned_url=False)
        
        return None
