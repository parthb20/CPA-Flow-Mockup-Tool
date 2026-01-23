"""
SERP template generation and processing
"""

import re
from src.config import SERP_BASE_URL


def generate_serp_mockup(flow_data, serp_templates):
    """Generate SERP HTML using actual template with CSS fixes
    
    This function processes SERP templates and fixes CSS issues that cause
    vertical text rendering problems.
    
    Args:
        flow_data: Dict containing flow information including 'serp_template_key'
        serp_templates: Dict mapping template keys to HTML strings, e.g., {"T8F75KL": "<html>..."}
    """
    keyword = flow_data.get('keyword_term', 'N/A')
    ad_title = flow_data.get('ad_title', 'N/A')
    ad_desc = flow_data.get('ad_description', 'N/A')
    ad_url = flow_data.get('ad_display_url', 'N/A')
    serp_template_key = flow_data.get('serp_template_key', '')
    
    if serp_templates:
        try:
            # New format: dict with template_key -> HTML string
            if isinstance(serp_templates, dict):
                # Look up template by key
                if serp_template_key and str(serp_template_key) in serp_templates:
                    html = serp_templates[str(serp_template_key)]
                elif len(serp_templates) > 0:
                    # Fallback: use first available template
                    html = list(serp_templates.values())[0]
                else:
                    return ""
            # Old format: list of dicts with 'code' key (backward compatibility)
            elif isinstance(serp_templates, list) and len(serp_templates) > 0:
                html = serp_templates[0].get('code', '')
            else:
                return ""
            
            # Only fix deprecated media queries - don't modify layout CSS
            # These replacements help with older CSS but don't affect responsive design
            html = html.replace('min-device-width', 'min-width')
            html = html.replace('max-device-width', 'max-width')
            html = html.replace('min-device-height', 'min-height')
            html = html.replace('max-device-height', 'max-height')
            
            # Replace keyword in the header text
            html = re.sub(
                r'Sponsored results for:\s*"[^"]*"', 
                f'Sponsored results for: "{keyword}"', 
                html
            )
            
            # Replace URL - handles nested elements inside URL container
            # Use DOTALL mode to match across lines and nested tags
            html = re.sub(
                r'(<div[^>]*class="[^"]*url[^"]*"[^>]*>)(?:(?!<div).)*?(</div>)', 
                f'\\1{ad_url}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*url[^"]*"[^>]*>)(?:(?!<p).)*?(</p>)', 
                f'\\1{ad_url}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            # Also try inside <a> tags with url class
            html = re.sub(
                r'(<a[^>]*class="[^"]*url[^"]*"[^>]*>)(?:(?!<a).)*?(</a>)', 
                f'\\1{ad_url}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            # Replace title - handles nested elements inside title container
            html = re.sub(
                r'(<div[^>]*class="[^"]*title[^"]*"[^>]*>)(?:(?!<div).)*?(</div>)', 
                f'\\1{ad_title}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*title[^"]*"[^>]*>)(?:(?!<p).)*?(</p>)', 
                f'\\1{ad_title}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<a[^>]*class="[^"]*title[^"]*"[^>]*>)(?:(?!<a).)*?(</a>)', 
                f'\\1{ad_title}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<h[1-6][^>]*class="[^"]*title[^"]*"[^>]*>)(?:(?!<h).)*?(</h[1-6]>)', 
                f'\\1{ad_title}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            # Replace description - handles nested elements inside desc container
            html = re.sub(
                r'(<div[^>]*class="[^"]*desc[^"]*"[^>]*>)(?:(?!<div).)*?(</div>)', 
                f'\\1{ad_desc}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*desc[^"]*"[^>]*>)(?:(?!<p).)*?(</p>)', 
                f'\\1{ad_desc}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<span[^>]*class="[^"]*desc[^"]*"[^>]*>)(?:(?!<span).)*?(</span>)', 
                f'\\1{ad_desc}\\2', 
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            return html
        except Exception as e:
            return ""
    
    return ""
