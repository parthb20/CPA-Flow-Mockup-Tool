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
            
            # Add responsive font scaling CSS - CRITICAL for proportional text
            # Use vw units which scale with viewport width (more reliable than cqw)
            responsive_font_css = """
            <style>
            /* Remove any fixed viewport meta tags that prevent scaling */
            
            /* Make root font size scale with viewport width */
            html {
                font-size: clamp(8px, 2vw, 14px) !important;
            }
            
            body {
                font-size: 1rem !important;
                line-height: 1.4 !important;
            }
            
            /* Scale headings proportionally */
            h1 { font-size: clamp(14px, 3vw, 24px) !important; }
            h2 { font-size: clamp(12px, 2.5vw, 20px) !important; }
            h3 { font-size: clamp(11px, 2.2vw, 18px) !important; }
            h4, h5, h6 { font-size: clamp(10px, 2vw, 16px) !important; }
            
            /* Scale all text elements */
            p, div, span, a, li, td, th, label, input, button, textarea {
                font-size: inherit !important;
            }
            
            /* Specific SERP elements - use em for relative scaling */
            .title, [class*="title"], [id*="title"] {
                font-size: clamp(11px, 2.3vw, 18px) !important;
                font-weight: 600 !important;
            }
            
            .desc, [class*="desc"], [id*="desc"] {
                font-size: clamp(9px, 1.8vw, 14px) !important;
                line-height: 1.3 !important;
            }
            
            .url, [class*="url"], [id*="url"] {
                font-size: clamp(8px, 1.6vw, 12px) !important;
            }
            
            /* Scale list items in SERP suggestions */
            ul li, ol li {
                font-size: clamp(9px, 1.9vw, 14px) !important;
            }
            
            /* Ensure everything inherits responsive sizing */
            * {
                box-sizing: border-box;
            }
            </style>
            """
            
            # Remove or replace fixed viewport meta tags that prevent scaling
            # Replace width=device-width with width=390 (or appropriate size) for consistent rendering
            html = re.sub(
                r'<meta[^>]*name=["\']viewport["\'][^>]*>',
                '<meta name="viewport" content="width=390, initial-scale=1.0">',
                html,
                flags=re.IGNORECASE
            )
            
            # If no viewport tag exists, add one
            if 'viewport' not in html.lower():
                viewport_tag = '<meta name="viewport" content="width=390, initial-scale=1.0">'
                if '<head>' in html.lower():
                    html = re.sub(r'(<head[^>]*>)', f'\\1\n{viewport_tag}', html, flags=re.IGNORECASE)
                else:
                    html = viewport_tag + html
            
            # Inject the responsive CSS before </head> or at start of <body>
            if '</head>' in html:
                html = html.replace('</head>', f'{responsive_font_css}</head>')
            elif '<body' in html:
                html = re.sub(r'(<body[^>]*>)', f'\\1{responsive_font_css}', html)
            else:
                # If no head or body, prepend it
                html = responsive_font_css + html
            
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
