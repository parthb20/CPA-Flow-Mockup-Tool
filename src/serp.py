"""
SERP template generation and processing
"""

import re
from src.config import SERP_BASE_URL


def replace_text_preserve_structure(match, replacement_text):
    """Replace only text content inside matched element, preserve HTML structure"""
    opening_tag = match.group(1)
    content = match.group(2)
    closing_tag = match.group(3)
    
    # Replace text nodes only (text between > and <), preserve tags
    # This keeps all nested HTML structure intact
    def replace_text_nodes(html):
        # Replace text that appears after > and before <
        return re.sub(r'>([^<]+)<', lambda m: f'>{replacement_text}<' if m.group(1).strip() else m.group(0), html, count=1)
    
    # If content has no nested tags, just replace it
    if '<' not in content:
        return opening_tag + replacement_text + closing_tag
    
    # Otherwise, preserve structure and replace only text nodes
    new_content = replace_text_nodes(content)
    return opening_tag + new_content + closing_tag


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
            
            # Replace URL - preserve HTML structure, replace only text
            html = re.sub(
                r'(<div[^>]*class="[^"]*url[^"]*"[^>]*>)(.*?)(</div>)', 
                lambda m: replace_text_preserve_structure(m, ad_url),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*url[^"]*"[^>]*>)(.*?)(</p>)', 
                lambda m: replace_text_preserve_structure(m, ad_url),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<a[^>]*class="[^"]*url[^"]*"[^>]*>)(.*?)(</a>)', 
                lambda m: replace_text_preserve_structure(m, ad_url),
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            # Replace title - preserve HTML structure, replace only text
            html = re.sub(
                r'(<div[^>]*class="[^"]*title[^"]*"[^>]*>)(.*?)(</div>)', 
                lambda m: replace_text_preserve_structure(m, ad_title),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*title[^"]*"[^>]*>)(.*?)(</p>)', 
                lambda m: replace_text_preserve_structure(m, ad_title),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<a[^>]*class="[^"]*title[^"]*"[^>]*>)(.*?)(</a>)', 
                lambda m: replace_text_preserve_structure(m, ad_title),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<h[1-6][^>]*class="[^"]*title[^"]*"[^>]*>)(.*?)(</h[1-6]>)', 
                lambda m: replace_text_preserve_structure(m, ad_title),
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            # Replace description - preserve HTML structure, replace only text
            html = re.sub(
                r'(<div[^>]*class="[^"]*desc[^"]*"[^>]*>)(.*?)(</div>)', 
                lambda m: replace_text_preserve_structure(m, ad_desc),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<p[^>]*class="[^"]*desc[^"]*"[^>]*>)(.*?)(</p>)', 
                lambda m: replace_text_preserve_structure(m, ad_desc),
                html, 
                count=1,
                flags=re.DOTALL
            )
            html = re.sub(
                r'(<span[^>]*class="[^"]*desc[^"]*"[^>]*>)(.*?)(</span>)', 
                lambda m: replace_text_preserve_structure(m, ad_desc),
                html, 
                count=1,
                flags=re.DOTALL
            )
            
            return html
        except Exception as e:
            return ""
    
    return ""
