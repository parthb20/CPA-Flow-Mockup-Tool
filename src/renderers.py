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


def render_mini_device_preview(content, is_url=False, device='mobile', use_srcdoc=False, display_url=None, orientation='vertical'):
    """Render device preview with realistic chrome for mobile/tablet/laptop
    
    Args:
        orientation: 'vertical' (portrait) or 'horizontal' (landscape)
    """
    
    from src.config import DEVICE_DIMENSIONS
    
    # Get base dimensions from config (these are portrait dimensions)
    portrait_width = DEVICE_DIMENSIONS[device]['width']
    portrait_height = DEVICE_DIMENSIONS[device]['height']
    chrome_height_px = DEVICE_DIMENSIONS[device]['chrome_height']
    
    # Determine actual dimensions based on orientation
    if orientation == 'horizontal':
        # Swap for landscape
        base_width = portrait_height
        base_height = portrait_width
        target_width = DEVICE_DIMENSIONS[device]['target_width_landscape']
    else:
        # Keep portrait
        base_width = portrait_width
        base_height = portrait_height
        target_width = DEVICE_DIMENSIONS[device]['target_width_portrait']
    
    # Calculate scale to achieve target width
    scale = target_width / base_width
    
    # Device-specific styling
    if device == 'mobile':
        frame_style = "border-radius: 30px; border: 5px solid #000000;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:40] + "..." if len(url_display) > 40 else url_display
        device_chrome = f"""
        <div style="background: #000; color: white; padding: 4px 16px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: 500; height: 22px; box-sizing: border-box;">
            <div>9:41</div>
            <div style="display: flex; gap: 3px; align-items: center; font-size: 11px;">
                <span>📶</span>
                <span>📡</span>
                <span>🔋</span>
            </div>
        </div>
        <div style="background: #f7f7f7; border-bottom: 1px solid #d1d1d1; padding: 8px 12px; display: flex; align-items: center; gap: 8px; height: 46px; box-sizing: border-box;">
            <div style="flex: 1; background: white; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid #e0e0e0;">
                <span style="font-size: 16px; flex-shrink: 0;">🔒</span>
                <span style="color: #666; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;">{url_display_short}</span>
                <span style="font-size: 16px; flex-shrink: 0;">🔄</span>
            </div>
        </div>
        """
        
        bottom_nav = """
        <div style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-top: 1px solid #e0e0e0; padding: 8px 0; display: flex; justify-content: space-around; align-items: center; height: 70px;">
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
        
    elif device == 'tablet':
        frame_style = "border-radius: 16px; border: 8px solid #1f2937;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:60] + "..." if len(url_display) > 60 else url_display
        device_chrome = f"""
        <div style="background: #000; color: white; padding: 8px 24px; display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 500; height: 48px; box-sizing: border-box;">
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
        <div style="background: #f0f0f0; border-bottom: 1px solid #d0d0d0; padding: 6px 16px; display: flex; align-items: center; gap: 12px; height: 40px; box-sizing: border-box;">
            <div style="flex: 1; background: white; border-radius: 10px; padding: 6px 16px; display: flex; align-items: center; gap: 10px; border: 1px solid #e0e0e0;">
                <span style="font-size: 18px; flex-shrink: 0;">🔒</span>
                <span style="color: #666; font-size: 15px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;">{url_display_short}</span>
            </div>
        </div>
        """
        bottom_nav = ""
        
    else:  # laptop
        frame_style = "border-radius: 8px; border: 6px solid #374151;"
        
        url_display = display_url if display_url else (content if is_url else "URL")
        url_display_short = url_display[:80] + "..." if len(url_display) > 80 else url_display
        device_chrome = f"""
        <div style="background: #e8e8e8; padding: 8px 16px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #d0d0d0; height: 48px; box-sizing: border-box;">
            <div style="display: flex; gap: 8px; flex-shrink: 0;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ff5f57;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #ffbd2e;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #28c840;"></div>
            </div>
            <div style="flex: 1; background: white; border-radius: 6px; padding: 6px 16px; display: flex; align-items: center; gap: 12px; border: 1px solid #d0d0d0; min-width: 0;">
                <span style="font-size: 16px; flex-shrink: 0;">🔒</span>
                <span style="color: #333; font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;">{url_display_short}</span>
            </div>
        </div>
        """
        bottom_nav = ""
    
    # Calculate display dimensions
    display_width = int(base_width * scale)
    display_height = int(base_height * scale)
    content_area_height = base_height - chrome_height_px
    
    # Prepare iframe content
    if is_url and not use_srcdoc:
        iframe_content = f'<iframe src="{content}" style="width: 100%; height: 100%; border: none;"></iframe>'
    else:
        iframe_content = content
    
    full_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width={base_width}, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta charset="utf-8">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            html, body {{ 
                width: {base_width}px;
                height: {base_height}px;
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: white;
            }}
            body {{
                display: flex;
                flex-direction: column;
            }}
            .device-chrome {{ 
                width: 100%;
                height: {chrome_height_px}px;
                flex-shrink: 0;
            }}
            .content-area {{ 
                flex: 1;
                width: {base_width}px;
                height: {content_area_height}px;
                overflow-y: auto; 
                overflow-x: hidden;
                -webkit-overflow-scrolling: touch;
                background: white;
            }}
            .content-area * {{
                max-width: 100% !important;
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                box-sizing: border-box !important;
            }}
            .content-area img {{
                max-width: 100% !important;
                height: auto !important;
            }}
            .content-area table {{
                width: 100% !important;
                table-layout: auto !important;
            }}
            .content-area td, .content-area th {{
                word-break: break-word !important;
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
    
    # Final wrapper HTML
    html_output = f"""
    <div style="display: flex; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 8px;">
        <div style="width: {display_width}px; height: {display_height}px; {frame_style} overflow: hidden; background: white; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
            <iframe srcdoc='{escaped}' style="width: {base_width}px; height: {base_height}px; border: none; transform: scale({scale}); transform-origin: 0 0; display: block; background: white;"></iframe>
        </div>
    </div>
    """
    
    return html_output, display_height + 30, is_url


def render_similarity_score(score_type, similarities_data, show_explanation=False, custom_title=None, tooltip_text=None):
    """Render a single similarity score card"""
    if not similarities_data:
        return
    
    data = similarities_data.get(score_type, {})
    
    if not data or data.get('error', False):
        # Show informative message as proper UI card
        if data and data.get('status_code') == 'no_api_key':
            st.markdown("""
                <div style="padding: 20px; background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 8px;">🔑</div>
                    <div style="font-size: 16px; font-weight: 600; color: #1e40af; margin-bottom: 4px;">API Key Required</div>
                    <div style="font-size: 13px; color: #3b82f6;">Add FASTROUTER_API_KEY or OPENAI_API_KEY to secrets</div>
                </div>
            """, unsafe_allow_html=True)
        elif data and data.get('status_code') == 'missing_data':
            missing_reason = data.get('body', 'Missing required data')
            st.markdown(f"""
                <div style="padding: 20px; background: #fef3c7; border: 2px solid #f59e0b; border-radius: 12px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 8px;">⚠️</div>
                    <div style="font-size: 16px; font-weight: 600; color: #92400e; margin-bottom: 4px;">Cannot Calculate</div>
                    <div style="font-size: 13px; color: #b45309;">{html.escape(missing_reason)}</div>
                </div>
            """, unsafe_allow_html=True)
        elif data and data.get('error'):
            error_msg = data.get('message', data.get('body', 'Unknown error'))
            st.markdown(f"""
                <div style="padding: 20px; background: #fee2e2; border: 2px solid #ef4444; border-radius: 12px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 8px;">❌</div>
                    <div style="font-size: 16px; font-weight: 600; color: #991b1b; margin-bottom: 4px;">Calculation Failed</div>
                    <div style="font-size: 13px; color: #dc2626;">{html.escape(str(error_msg)[:100])}</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="padding: 20px; background: #f0f9ff; border: 2px solid #0ea5e9; border-radius: 12px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 8px;">⏳</div>
                    <div style="font-size: 16px; font-weight: 600; color: #075985; margin-bottom: 4px;">Loading...</div>
                    <div style="font-size: 13px; color: #0284c7;">Similarity scores will calculate after flow data loads</div>
                </div>
            """, unsafe_allow_html=True)
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
        <span style="font-weight: 900; color: #0f172a; font-size: 18px;">
            <strong>{title_text}</strong>
            <span title="{tooltip}" style="cursor: help; color: #3b82f6; font-size: 13px; margin-left: 4px;"><strong>ℹ️</strong></span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}15 0%, {color}08 100%); border: 2px solid {color}; border-radius: 12px; padding: 16px; margin: 8px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
            <div style="background: white; border-radius: 12px; padding: 12px 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 44px; font-weight: 900; color: {color}; line-height: 1;">{score:.0%}</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="font-weight: 700; color: {color}; font-size: 16px; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;">{label} Match</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.4;">{reason}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📊 View Detailed Breakdown", expanded=False):
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
        
        relevant_components = component_mapping.get(score_type, [])
        score_components = [(component_labels[key], data.get(key, 0)) for key in relevant_components if key in data]
        
        if score_components:
            for name, val in score_components:
                score_val = val * 100
                score_color = "#22c55e" if val >= 0.7 else "#f59e0b" if val >= 0.4 else "#ef4444"
                st.markdown(f'<div style="margin: 4px 0;"><span style="color: {score_color}; font-weight: 700; font-size: 14px;">{name}: {score_val:.0f}%</span></div>', unsafe_allow_html=True)
        
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
    
    if screenshot_url and '%' in screenshot_url:
        screenshot_url_escaped = screenshot_url.replace("'", "\\'").replace('"', '\\"')
    else:
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
        if isinstance(adcode, str) and adcode.startswith('"'):
            adcode = json.loads(adcode)
        
        adcode = adcode.encode().decode('unicode_escape')
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
