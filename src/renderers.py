# -*- coding: utf-8 -*-
"""
Rendering functions for UI components
"""

import streamlit as st
import pandas as pd
import html
import hashlib
import time
from src.similarity import get_score_class

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    PLAYWRIGHT_AVAILABLE = False


def render_mini_device_preview(content, is_url=False, device='mobile', use_srcdoc=False, display_url=None):
    """Render device preview with realistic chrome for mobile/tablet/laptop"""
    # Device dimensions and styling
    if device == 'mobile':
        device_w = 390
        container_height = 844
        scale = 0.5
        frame_style = "border-radius: 30px; border: 5px solid #000000;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:40] + "..." if len(url_display) > 40 else url_display
        device_chrome = f"""
        <div style="background: #000; color: white; padding: 6px 20px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 500;">
            <div>9:41</div>
            <div style="display: flex; gap: 4px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style="background: #f7f7f7; border-bottom: 1px solid #d1d1d1; padding: 8px 12px; display: flex; align-items: center; gap: 8px;">
            <div style="flex: 1; background: white; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid #e0e0e0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #666; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{url_display_short}</span>
                <span style="font-size: 16px;">🔄</span>
            </div>
        </div>
        """
        
        bottom_nav = """
        <div style="position: fixed; bottom: 0; left: 0; right: 0; background: white; border-top: 1px solid #e0e0e0; padding: 8px 0; display: flex; justify-content: space-around; align-items: center; z-index: 1000;">
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 20px;">🏠</div>
                <div style="font-size: 10px; color: #666;">Home</div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 20px;">⬅️</div>
                <div style="font-size: 10px; color: #666;">Back</div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 20px;">📱</div>
                <div style="font-size: 10px; color: #666;">Apps</div>
            </div>
        </div>
        """
        chrome_height = "90px"
        
    elif device == 'tablet':
        device_w = 1024
        container_height = 768
        scale = 0.4
        frame_style = "border-radius: 16px; border: 12px solid #1f2937;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:50] + "..." if len(url_display) > 50 else url_display
        device_chrome = f"""
        <div style="background: #000; color: white; padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500;">
            <div style="display: flex; gap: 12px;">
                <span>9:41 AM</span>
                <span>Wed Jan 13</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style="background: #f0f0f0; border-bottom: 1px solid #d0d0d0; padding: 12px 16px; display: flex; align-items: center; gap: 12px;">
            <div style="flex: 1; background: white; border-radius: 10px; padding: 10px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;">
                <span style="font-size: 18px;">🔒</span>
                <span style="color: #666; font-size: 15px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{url_display_short}</span>
            </div>
        </div>
        """
        bottom_nav = ""
        chrome_height = "60px"
        
    else:  # laptop
        device_w = 1920
        container_height = 1080
        scale = 0.35
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:60] + "..." if len(url_display) > 60 else url_display
        device_chrome = f"""
        <div style="background: #e8e8e8; padding: 12px 16px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #d0d0d0;">
            <div style="display: flex; gap: 8px;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f57;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #28c840;"></div>
            </div>
            <div style="flex: 1; background: white; border-radius: 6px; padding: 8px 16px; display: flex; align-items: center; gap: 12px; border: 1px solid #d0d0d0;">
                <span style="font-size: 16px;">🔒</span>
                <span style="color: #333; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{url_display_short}</span>
            </div>
        </div>
        """
        bottom_nav = ""
        chrome_height = "52px"
    
    display_w = int(device_w * scale)
    display_h = int(container_height * scale)
    
    if is_url and not use_srcdoc:
        # For URL-based iframes, wrap in device chrome
        iframe_content = f'<iframe src="{content}" style="width: 100%; height: 100%; border: none;"></iframe>'
    else:
        iframe_content = content
    
    full_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width={device_w}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta charset="utf-8">
        <style>
            body {{ 
                margin: 0; 
                padding: 0; 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                width: {device_w}px;
                max-width: {device_w}px;
                overflow-x: hidden;
            }}
            .device-chrome {{ 
                width: 100%; 
                max-width: {device_w}px;
                background: white; 
            }}
            .content-area {{ 
                width: {device_w}px;
                max-width: {device_w}px;
                height: calc(100vh - {chrome_height}); 
                overflow-y: auto; 
                overflow-x: hidden;
                -webkit-overflow-scrolling: touch;
            }}
            .content-area * {{
                max-width: {device_w}px !important;
                box-sizing: border-box !important;
            }}
            html, body {{
                overflow-x: hidden !important;
                width: {device_w}px !important;
                max-width: {device_w}px !important;
            }}
        </style>
    </head>
    <body>
        <div class="device-chrome">{device_chrome}</div>
        <div class="content-area">{iframe_content}</div>
        {bottom_nav if device == 'mobile' else ''}
    </body>
    </html>
    """
    
    escaped = full_content.replace("'", "&apos;").replace('"', '&quot;')
    
    html_output = f"""
    <div style="display: flex; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 8px;">
        <div style="width: {display_w}px; height: {display_h}px; {frame_style} overflow: hidden; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
            <iframe srcdoc='{escaped}' style="width: {device_w}px; height: {container_height}px; border: none; transform: scale({scale}); transform-origin: 0 0; display: block; background: white;"></iframe>
        </div>
    </div>
    """
    
    return html_output, display_h + 30, is_url


def render_similarity_score(score_type, similarities_data, show_explanation=False, custom_title=None, tooltip_text=None):
    """Render a single similarity score card"""
    if not similarities_data:
        return
    
    data = similarities_data.get(score_type, {})
    
    if not data or data.get('error', False):
        if data and data.get('status_code') == 'no_api_key':
            # Only show message if API key is actually missing
            try:
                api_key = st.secrets.get('FASTROUTER_API_KEY') or st.secrets.get('OPENAI_API_KEY')
                if not api_key:
                    st.info("🔑 Add API key to calculate")
            except:
                # If secrets not available, don't show message (assume configured)
                pass
        else:
            st.info("⏳ Will calculate after data loads")
        return
    
    score = data.get('final_score', 0)
    reason = data.get('reason', 'N/A')
    css_class, label, color = get_score_class(score)
    
    if custom_title:
        title_text = custom_title
    else:
        if score_type == 'kwd_to_ad':
            title_text = "Keyword → Ad Similarity"
            default_tooltip = "Measures how well the ad creative matches the search keyword."
        elif score_type == 'ad_to_page':
            title_text = "Ad Copy → Landing Page Similarity"
            default_tooltip = "Measures how well the landing page fulfills the promises made in the ad copy."
        elif score_type == 'kwd_to_page':
            title_text = "Keyword → Landing Page Similarity"
            default_tooltip = "Measures overall flow consistency from keyword to landing page."
        else:
            title_text = f"{label} Match"
            default_tooltip = "Similarity score measuring alignment between different parts of your ad flow."
    
    tooltip = tooltip_text or default_tooltip
    
    st.markdown(f"""
    <div style="margin-bottom: 8px;">
        <span style="font-weight: 600; color: #0f172a; font-size: 14px;">
            {title_text}
            <span title="{tooltip}" style="cursor: help; color: #3b82f6; font-size: 12px; margin-left: 4px;">ℹ️</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}15 0%, {color}08 100%); border: 2px solid {color}; border-radius: 12px; padding: 16px; margin: 8px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
            <div style="background: white; border-radius: 12px; padding: 12px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 40px; font-weight: 900; color: {color}; line-height: 1;">{score:.0%}</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="font-weight: 700; color: {color}; font-size: 15px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;">{label} Match</div>
                <div style="font-size: 12px; color: #475569; line-height: 1.4;">{reason}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Detailed Breakdown", expanded=False):
        # Define which components belong to which score type
        component_mapping = {
            'kwd_to_ad': ['keyword_match', 'topic_match', 'intent_match'],
            'ad_to_page': ['topic_match', 'brand_match', 'promise_match'],
            'kwd_to_page': ['topic_match', 'utility_match', 'intent_match']
        }
        
        component_labels = {
            'keyword_match': '🔑 Keyword Match',
            'topic_match': '🎯 Topic Match',
            'intent_match': '💡 Intent Match',
            'brand_match': '🏷️ Brand Match',
            'promise_match': '✅ Promise Match',
            'utility_match': '⚙️ Utility Match'
        }
        
        # Get relevant components for this score type
        relevant_components = component_mapping.get(score_type, [])
        score_components = [(component_labels[key], data.get(key, 0)) for key in relevant_components if key in data]
        
        if score_components:
            # Display each component on its own line
            for name, val in score_components:
                score_val = val * 100
                score_color = "#22c55e" if val >= 0.7 else "#f59e0b" if val >= 0.4 else "#ef4444"
                st.markdown(f'<div style="margin: 4px 0;"><span style="color: {score_color}; font-weight: 700; font-size: 14px;">{name}: {score_val:.0f}%</span></div>', unsafe_allow_html=True)
        
        # Show intent and band below
        extra_info = []
        if 'intent' in data and data['intent']:
            extra_info.append(f"🎯 **Intent:** {data['intent']}")
        if 'band' in data and data['band']:
            extra_info.append(f"📈 **Band:** {data['band'].title()}")
        
        if extra_info:
            st.markdown(" &nbsp;|&nbsp; ".join(extra_info))


def inject_unique_id(html_content, prefix, url, device, flow_data=None):
    """Inject a unique identifier comment into HTML to force re-rendering"""
    key_parts = [prefix, str(url), str(device), str(time.time())]
    if flow_data:
        key_parts.append(str(flow_data.get('publisher_url', '')))
        key_parts.append(str(flow_data.get('serp_template_key', '')))
    key_string = '_'.join(key_parts)
    unique_id = hashlib.md5(key_string.encode()).hexdigest()[:12]
    stripped = html_content.lstrip()
    leading_ws = html_content[:len(html_content) - len(stripped)]
    
    if stripped.startswith('<!DOCTYPE'):
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    elif stripped.startswith('<html'):
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    else:
        html_content = leading_ws + f'<!-- unique_id:{unique_id} -->\n' + stripped
    return html_content


def create_screenshot_html(screenshot_url, device='mobile', referer_domain=None):
    """Create HTML for screenshot with proper referer handling"""
    vw = 390 if device == 'mobile' else 820 if device == 'tablet' else 1440
    
    # Ensure URL is properly formatted - don't double-encode
    if screenshot_url and '%' in screenshot_url:
        # Already encoded, use as-is but escape for HTML
        screenshot_url_escaped = screenshot_url.replace("'", "\\'").replace('"', '\\"')
    else:
        # Not encoded, escape for HTML
        screenshot_url_escaped = screenshot_url.replace("'", "\\'").replace('"', '\\"') if screenshot_url else ""
    screenshot_html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width={vw}">
<style>* {{margin:0;padding:0;box-sizing:border-box}} body {{background:#f5f5f5}} img {{width:100%;height:auto;display:block;max-width:100%;}} .error {{padding: 20px; text-align: center; color: #dc2626; background: #fef2f2; border: 2px solid #fca5a5; border-radius: 8px; margin: 10px; font-family: system-ui, -apple-system, sans-serif;}} .loading {{padding: 20px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 8px; margin: 10px;}}</style>
</head><body>
<div class="loading">⏳ Loading screenshot...</div>
<script>
(function() {{
    let retryCount = 0;
    const maxRetries = 3;
    const screenshotUrl = '{screenshot_url_escaped}';
    
    function showError(message) {{
        document.body.innerHTML = '<div class="error">' + message + '</div>';
    }}
    
    function loadImage() {{
        const img = new Image();
        img.style.width = '100%';
        img.style.height = 'auto';
        img.style.display = 'block';
        
        const timeout = setTimeout(function() {{
            img.onerror = null;
            img.onload = null;
            retryCount++;
            if (retryCount <= maxRetries) {{
                const separator = screenshotUrl.includes('?') ? '&' : '?';
                img.src = screenshotUrl + separator + 't=' + Date.now() + '&retry=' + retryCount;
            }} else {{
                showError('⚠️ Screenshot failed to load<br><small>Timeout after multiple retries</small><br><small style="font-size: 10px;">URL: ' + screenshotUrl.substring(0, 60) + '...</small><br><br><small>💡 Check VPN/network connection<br>Some URLs require VPN to access</small>');
            }}
        }}, 10000);
        
        img.onload = function() {{
            clearTimeout(timeout);
            document.body.innerHTML = '';
            document.body.appendChild(img);
        }};
        
        img.onerror = function() {{
            clearTimeout(timeout);
            retryCount++;
            if (retryCount <= maxRetries) {{
                setTimeout(function() {{
                    const separator = screenshotUrl.includes('?') ? '&' : '?';
                    img.src = screenshotUrl + separator + 't=' + Date.now() + '&retry=' + retryCount;
                }}, 1000 * retryCount);
            }} else {{
                const urlShort = screenshotUrl.substring(0, 60);
                showError('⚠️ Failed to load preview<br><small>Network error or site blocking</small><br><small style="font-size: 10px;">URL: ' + urlShort + '...</small><br><br><small>💡 This site may block automated access<br>Try opening the link directly</small>');
            }}
        }};
        
        img.crossOrigin = 'anonymous';
        img.src = screenshotUrl;
    }}
    
    setTimeout(loadImage, 100);
}})();
</script>
</body></html>'''
    
    return screenshot_html


def unescape_adcode(adcode):
    """Unescape adcode using Flask app logic"""
    import json
    import re
    
    try:
        # Handle double-stringified JSON
        if isinstance(adcode, str) and adcode.startswith('"'):
            adcode = json.loads(adcode)
        
        # Replace unicode escapes
        adcode = adcode.encode().decode('unicode_escape')
        
        # Handle HTML entities
        adcode = adcode.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        return adcode
    except:
        return adcode


def parse_creative_html(response_str):
    """Parse response JSON and extract HTML with proper unescaping"""
    import json
    import re
    
    try:
        if not response_str or pd.isna(response_str):
            return None, None
        
        if str(response_str).startswith('{\\'):
            try:
                response_str = json.loads('"' + response_str + '"')
            except:
                pass
        
        response_data = json.loads(response_str)
        raw_adcode = response_data.get('adcode', '')
        
        if not raw_adcode:
            return None, None
        
        # Unescape adcode
        adcode = unescape_adcode(raw_adcode)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ margin: 0; padding: 0; background: white; font-family: Arial, sans-serif; }}
            </style>
        </head>
        <body>
            {adcode}
        </body>
        </html>
        """
        
        return html_content, raw_adcode
        
    except Exception as e:
        st.error(f"Error parsing creative: {str(e)}")
        return None, None
