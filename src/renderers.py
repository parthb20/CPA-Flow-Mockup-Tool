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
    """Render device preview with realistic chrome for mobile/tablet/laptop - RESPONSIVE
    
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
        target_width_vw = DEVICE_DIMENSIONS[device]['target_width_landscape']
        min_width = DEVICE_DIMENSIONS[device]['min_width_landscape']
        max_width = DEVICE_DIMENSIONS[device]['max_width_landscape']
    else:
        # Keep portrait
        base_width = portrait_width
        base_height = portrait_height
        target_width_vw = DEVICE_DIMENSIONS[device]['target_width_portrait']
        min_width = DEVICE_DIMENSIONS[device]['min_width_portrait']
        max_width = DEVICE_DIMENSIONS[device]['max_width_portrait']
    
    # Calculate scale based on average of min/max for initial rendering
    # The CSS will handle responsive scaling via viewport units
    avg_target_width = (min_width + max_width) / 2
    scale = avg_target_width / base_width
    
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
    
    # Calculate display dimensions - using responsive approach
    # These are for the iframe container aspect ratio calculation
    display_width_px = int(base_width * scale)
    display_height_px = int(base_height * scale)
    content_area_height = base_height - chrome_height_px
    
    # Calculate responsive width using clamp() for fluid scaling
    responsive_width = f"clamp({min_width}px, {target_width_vw}, {max_width}px)"
    # Height MUST scale proportionally with width to maintain aspect ratio
    aspect_ratio = base_height / base_width
    # Use calc() to compute height based on responsive width
    responsive_height = f"calc(({responsive_width}) * {aspect_ratio})"
    
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
            
            /* Ensure fixed elements stay within content area */
            .content-area [style*="fixed"],
            .content-area [style*="sticky"] {{
                position: absolute !important;
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
    
    # Final wrapper HTML - TRULY RESPONSIVE with proper scaling
    # Use CSS to calculate scale dynamically based on container width
    html_output = f"""
    <div class="device-preview-container" style="display: flex; justify-content: center; padding: clamp(0.5rem, 0.4rem + 0.5vw, 0.625rem); background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); overflow: hidden;">
        <div style="
            width: {responsive_width}; 
            aspect-ratio: {base_width} / {base_height}; 
            {frame_style} 
            overflow: hidden; 
            background: white; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.2); 
            position: relative;
            container-type: size;
            clip-path: inset(0);
        ">
            <iframe srcdoc='{escaped}' style="
                position: absolute; 
                top: 0; 
                left: 0; 
                width: {base_width}px; 
                height: {base_height}px; 
                border: none; 
                transform-origin: 0 0; 
                display: block; 
                background: white; 
                transform: scale(calc(100cqw / {base_width}px));
                overflow: hidden;
                clip-path: inset(0);
            "></iframe>
        </div>
    </div>
    """
    
    # Return estimated height (will be truly responsive)
    return html_output, display_height_px + 30, is_url


def render_similarity_score(score_type, similarities_data, show_explanation=False, custom_title=None, tooltip_text=None, max_height=None):
    """Render a single similarity score card with optional max height
    
    Args:
        max_height: Maximum height in pixels for the similarity box (enables scrolling if content exceeds)
    """
    if not similarities_data:
        return
    
    data = similarities_data.get(score_type, {})
    
    # Show title first (left-aligned), then handle missing/error data
    title_text = custom_title or f"{score_type} Similarity"
    
    # Determine default tooltip if not provided
    if not tooltip_text:
        if score_type == 'kwd_to_ad':
            tooltip_text = "Measures keyword-ad alignment. 70%+ = Good Match (keywords appear in ad), 40-69% = Fair Match (topic relevance), <40% = Poor Match (weak connection)"
        elif score_type == 'ad_to_page':
            tooltip_text = "Measures ad-to-page consistency. 70%+ = Good Match (landing page delivers on ad promises), 40-69% = Fair Match (partial alignment), <40% = Poor Match (misleading ad)"
        elif score_type == 'kwd_to_page':
            tooltip_text = "Measures end-to-end flow quality. 70%+ = Good Match (keyword intent matches landing page), 40-69% = Fair Match (some relevance), <40% = Poor Match (poor user experience)"
        else:
            tooltip_text = "Similarity score measuring alignment. 70%+ = Good, 40-69% = Fair, <40% = Poor"
    
    # Determine formula text based on score type
    formula_text = ""
    if score_type == 'kwd_to_ad':
        formula_text = "Formula: 15% Keyword Match + 35% Topic Match + 50% Intent Match"
    elif score_type == 'ad_to_page':
        formula_text = "Formula: 30% Topic Match + 20% Brand Match + 50% Promise Match"
    elif score_type == 'kwd_to_page':
        formula_text = "Formula: 40% Topic Match + 60% Utility Match"
    
    st.markdown(f"""
    <div style="margin-bottom: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); display: flex; align-items: center; justify-content: flex-start;">
        <span style="font-weight: 900; color: #0f172a; font-size: clamp(1rem, 0.9rem + 0.5vw, 1.125rem);">
            <strong>{title_text}</strong>
        </span>
        <span title="{tooltip_text}" style="cursor: help; color: #3b82f6; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); margin-left: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem);">ℹ️</span>
    </div>
    {f'<div style="margin-bottom: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); font-size: clamp(0.625rem, 0.6rem + 0.2vw, 0.6875rem); color: #64748b; font-style: italic;">{formula_text}</div>' if formula_text else ''}
    """, unsafe_allow_html=True)
    
    # If this specific score is missing, show wait message
    if not data:
        st.markdown("""
            <div style="padding: 16px; background: #f0f9ff; border: 2px solid #bfdbfe; border-radius: 8px; text-align: center;">
                <div style="font-size: 32px; margin-bottom: 6px;">⏳</div>
                <div style="font-size: 14px; font-weight: 600; color: #075985;">Wait for data to load</div>
            </div>
        """, unsafe_allow_html=True)
        return
    
    # If there's an error, show it briefly
    if data.get('error', False):
        error_status = data.get('status_code', '')
        if error_status == 'no_api_key':
            st.markdown("""
                <div style="padding: 16px; background: #eff6ff; border: 2px solid #bfdbfe; border-radius: 8px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 6px;">🔑</div>
                    <div style="font-size: 14px; font-weight: 600; color: #1e40af;">API key required</div>
                </div>
            """, unsafe_allow_html=True)
        elif error_status in ['missing_data', 'page_fetch_failed']:
            st.markdown("""
                <div style="padding: 16px; background: #f0f9ff; border: 2px solid #bfdbfe; border-radius: 8px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 6px;">⏳</div>
                    <div style="font-size: 14px; font-weight: 600; color: #075985;">Wait for data to load</div>
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
    
    # Main score card (title already shown above) - RESPONSIVE
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}15 0%, {color}08 100%); border: 2px solid {color}; border-radius: clamp(0.5rem, 0.4rem + 0.6vw, 0.75rem); padding: clamp(0.75rem, 0.6rem + 0.8vw, 1rem); margin: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem) 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
        <div style="display: flex; align-items: center; gap: clamp(0.75rem, 0.6rem + 0.8vw, 1rem); flex-wrap: wrap;">
            <div style="background: white; border-radius: clamp(0.5rem, 0.4rem + 0.6vw, 0.75rem); padding: clamp(0.625rem, 0.5rem + 0.6vw, 0.75rem) clamp(1rem, 0.8rem + 1vw, 1.25rem); box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
                <div style="font-size: clamp(2.25rem, 2rem + 1.3vw, 2.75rem); font-weight: 900; color: {color}; line-height: 1;">{score:.0%}</div>
            </div>
            <div style="flex: 1; min-width: clamp(12.5rem, 11rem + 7.5vw, 15rem);">
                <div style="font-weight: 700; color: {color}; font-size: clamp(0.875rem, 0.8rem + 0.4vw, 1rem); margin-bottom: clamp(0.25rem, 0.2rem + 0.3vw, 0.375rem); text-transform: uppercase; letter-spacing: 0.5px;">{label} Match</div>
                <div style="font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem); color: #475569; line-height: 1.4;">{reason}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show component scores inline - one per line
    component_mapping = {
        'kwd_to_ad': ['keyword_match', 'topic_match', 'intent_match'],
        'ad_to_page': ['topic_match', 'brand_match', 'promise_match'],
        'kwd_to_page': ['topic_match', 'utility_match']
    }
    
    component_labels = {
        'keyword_match': 'Keyword Match',
        'topic_match': 'Topic Match',
        'intent_match': 'Intent Match',
        'brand_match': 'Brand Match',
        'promise_match': 'Promise Match',
        'utility_match': 'Utility Match'
    }
    
    relevant_components = component_mapping.get(score_type, [])
    if relevant_components:
        scores_html = ""
        for key in relevant_components:
            if key in data:
                val = data.get(key, 0)
                score_val = val * 100
                score_color = "#22c55e" if val >= 0.7 else "#f59e0b" if val >= 0.4 else "#ef4444"
                label = component_labels.get(key, key.replace('_', ' ').title())
                scores_html += f'<div style="margin: clamp(0.125rem, 0.1rem + 0.15vw, 0.1875rem) 0; padding: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem) clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); background: #f8fafc; border-left: 3px solid {score_color}; font-size: clamp(0.75rem, 0.7rem + 0.25vw, 0.8125rem);"><span style="color: #0f172a; font-weight: 600;">{label}:</span> <span style="color: {score_color}; font-weight: 700;">{score_val:.0f}%</span></div>'
        
        if scores_html:
            # Wrap in a container with optional max height and scrolling - RESPONSIVE
            if max_height:
                container_style = f'max-height: {max_height}px; overflow-y: auto; margin-top: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem); padding-right: clamp(0.25rem, 0.2rem + 0.2vw, 0.25rem);'
            else:
                container_style = 'margin-top: clamp(0.375rem, 0.3rem + 0.4vw, 0.5rem);'
            st.markdown(f'<div style="{container_style}">{scores_html}</div>', unsafe_allow_html=True)


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
