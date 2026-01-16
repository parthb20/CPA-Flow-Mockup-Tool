from flask import Flask, render_template_string, request, jsonify
import json
import html
import re
from urllib.parse import urlparse, parse_qs, unquote

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1200, initial-scale=1.0">
    <title>Ad Code Cleaner & JSON Unescaper</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            min-width: 1240px;
            padding: 20px;
        }
        .container {
            width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 30px;
        }
        .section {
            margin-bottom: 25px;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
            font-size: 14px;
        }
        textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            flex: 1;
            min-width: 150px;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .output-box {
            background: #f8f9fa;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            min-height: 200px;
            max-height: 400px;
            overflow: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .error {
            background: #fee;
            border: 2px solid #fcc;
            color: #c00;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .success {
            background: #efe;
            border: 2px solid #cfc;
            color: #060;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .info {
            background: #e3f2fd;
            border: 2px solid #90caf9;
            color: #1565c0;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .info {
            background: #e3f2fd;
            border: 2px solid #90caf9;
            color: #1565c0;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 13px;
        }
        .preview-frame {
            width: auto;
            min-width: 300px;
            min-height: 250px;
            height: auto;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: #f8f9fa;
            display: block;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background: none;
            font-weight: 600;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .stat-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            flex: 1;
            min-width: 150px;
        }
        .stat-label {
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 20px;
            font-weight: 700;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧹 Ad Code Cleaner & JSON Unescaper</h1>
            <p>Clean ad code from JSON, unescape JSON strings, and preview your ads</p>
        </div>
        <div class="content">
            <div class="info">
                <strong>📋 How to use:</strong> 
                <ol style="margin: 5px 0 10px 20px; padding: 0;">
                    <li>Paste your escaped JSON ad code below (with backslash quotes like <code>\"</code>)</li>
                    <li>Click "Clean & Process"</li>
                    <li>Get two outputs:
                        <ul style="margin: 5px 0 0 20px;">
                            <li><strong>Cleaned HTML</strong> - Extract and decode the HTML from JSON</li>
                            <li><strong>Unescaped JSON</strong> - Convert <code>\"</code> to <code>"</code> for proper JSON parsing</li>
                        </ul>
                    </li>
                    <li>Copy either format and use in your website!</li>
                </ol>
                <strong>ℹ️ Note:</strong> Dynamic ads (Media.net, Google AdSense) won't show on localhost - they only work on real domains. Use the cleaned HTML on your actual website.
            </div>

            <div class="section">
                <label for="input">Input Ad Code (JSON Format):</label>
                <textarea id="input" rows="10" placeholder='Paste your ad code JSON here, e.g., {"adcode":"..."}'></textarea>
            </div>

            <div class="btn-group">
                <button class="btn-primary" onclick="processAdCode()">🔄 Clean & Process</button>
                <button class="btn-secondary" onclick="copyToClipboard()">📋 Copy HTML</button>
                <button class="btn-secondary" onclick="downloadHTML()">💾 Download HTML</button>
                <button class="btn-secondary" onclick="clearAll()">🗑️ Clear All</button>
            </div>

            <div id="message"></div>
            <div id="stats" style="display: none;"></div>

            <div class="tabs">
                <button class="tab active" onclick="switchTab(event, 'cleaned')">Cleaned HTML</button>
                <button class="tab" onclick="switchTab(event, 'converted')">Unescaped JSON</button>
                <button class="tab" onclick="switchTab(event, 'preview')">Live Preview</button>
                <button class="tab" onclick="switchTab(event, 'original')">Original Input</button>
            </div>

            <div id="cleaned-tab" class="tab-content active">
                <div class="section">
                    <label>Cleaned HTML Code (Original Format):</label>
                    <div id="output" class="output-box">Cleaned HTML will appear here...</div>
                </div>
            </div>

            <div id="converted-tab" class="tab-content">
                <div class="section">
                    <div class="info" style="margin-bottom: 15px;">
                        <strong>🔄 Unescaped JSON:</strong> This is your JSON with escaped quotes (`\"`) converted to regular quotes (`"`). Use this format when you need properly formatted JSON that can be parsed.
                    </div>
                    <label>Unescaped JSON (Ready to Parse):</label>
                    <div id="converted-output" class="output-box">Unescaped JSON will appear here...</div>
                    <div class="btn-group" style="margin-top: 10px;">
                        <button class="btn-secondary" onclick="copyConverted()">📋 Copy Unescaped JSON</button>
                        <button class="btn-secondary" onclick="downloadConverted()">💾 Download JSON</button>
                    </div>
                </div>
            </div>

            <div id="preview-tab" class="tab-content">
                <div class="section">
                    <label>Live Preview:</label>
                    <div class="btn-group" style="margin-bottom: 10px;">
                        <button class="btn-secondary" onclick="refreshPreview()">🔄 Refresh Preview</button>
                        <button class="btn-secondary" onclick="openInNewTab()">🪟 Open in New Tab</button>
                    </div>
                    <iframe id="preview" class="preview-frame" allowfullscreen></iframe>
                </div>
            </div>

            <div id="original-tab" class="tab-content">
                <div class="section">
                    <label>Original Formatted JSON:</label>
                    <div id="original" class="output-box">Original JSON will appear here...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentHTML = '';
        let currentConverted = '';

        function processAdCode() {
            const input = document.getElementById('input').value;
            const messageDiv = document.getElementById('message');
            
            if (!input.trim()) {
                showMessage('Please paste your ad code JSON', 'error');
                return;
            }

            showMessage('Processing...', 'info');
            
            fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ adcode: input })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Server error: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    currentHTML = data.cleaned_html;
                    currentConverted = data.unescaped_json || '';
                    
                    document.getElementById('output').textContent = currentHTML;
                    document.getElementById('original').textContent = data.formatted_json;
                    document.getElementById('converted-output').textContent = currentConverted;
                    
                    updatePreview(currentHTML);
                    showStats(data.stats);
                    
                    // Auto-switch to unescaped JSON tab
                    setTimeout(() => {
                        switchTabProgrammatic('converted');
                    }, 500);
                    
                    // Show success message
                    showMessage('Ad code processed successfully! ✓ Check the Unescaped JSON tab.', 'success');
                } else {
                    showMessage('Error: ' + data.error, 'error');
                    document.getElementById('stats').style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Processing error:', error);
                showMessage('Error: ' + error.message, 'error');
                document.getElementById('stats').style.display = 'none';
            });
        }

        function updatePreview(html) {
            const iframe = document.getElementById('preview');
            
            // Load preview from Flask route (no sandbox restrictions!)
            // Add timestamp to prevent caching
            iframe.src = '/preview?t=' + Date.now();
            
            console.log('✓ Preview updated successfully, HTML length:', html.length);
        }

        function showStats(stats) {
            const statsDiv = document.getElementById('stats');
            statsDiv.style.display = 'flex';
            statsDiv.className = 'stats';
            
            let dynamicWarning = '';
            if (stats.is_dynamic) {
                dynamicWarning = `
                    <div style="width: 100%; background: #d1ecf1; border: 1px solid #0dcaf0; color: #055160; padding: 12px; border-radius: 8px; margin-top: 10px; font-size: 13px;">
                        <strong>✅ ${stats.ad_network} Ad Processed!</strong><br>
                        Choose your format: <strong>Cleaned HTML</strong> (ready to deploy) or <strong>Unescaped JSON</strong> (for parsing).<br>
                        Deploy the HTML to your live website to see the actual ad.
                    </div>
                `;
            }
            
            statsDiv.innerHTML = `
                <div class="stat-box">
                    <div class="stat-label">Ad Network</div>
                    <div class="stat-value" style="font-size: 16px;">${stats.ad_network}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">HTML Length</div>
                    <div class="stat-value">${stats.html_length.toLocaleString()}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Script Tags</div>
                    <div class="stat-value">${stats.script_tags}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Other Tags</div>
                    <div class="stat-value">${stats.other_tags}</div>
                </div>
                ${dynamicWarning}
            `;
        }

        function copyToClipboard() {
            if (!currentHTML || currentHTML === '') {
                showMessage('No HTML to copy. Process ad code first.', 'error');
                return;
            }
            
            navigator.clipboard.writeText(currentHTML).then(() => {
                showMessage('HTML copied to clipboard! ✓', 'success');
            }).catch(err => {
                showMessage('Failed to copy: ' + err, 'error');
            });
        }

        function copyConverted() {
            if (!currentConverted || currentConverted === '') {
                showMessage('No unescaped JSON available. Process ad code first.', 'error');
                return;
            }
            
            navigator.clipboard.writeText(currentConverted).then(() => {
                showMessage('Unescaped JSON copied to clipboard! ✓', 'success');
            }).catch(err => {
                showMessage('Failed to copy: ' + err, 'error');
            });
        }

        function downloadHTML() {
            if (!currentHTML || currentHTML === '') {
                showMessage('No HTML to download. Process ad code first.', 'error');
                return;
            }
            
            const blob = new Blob([currentHTML], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'cleaned_adcode_' + Date.now() + '.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showMessage('HTML downloaded! ✓', 'success');
        }

        function downloadConverted() {
            if (!currentConverted || currentConverted === '') {
                showMessage('No unescaped JSON to download. Process ad code first.', 'error');
                return;
            }
            
            const blob = new Blob([currentConverted], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'unescaped_adcode_' + Date.now() + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showMessage('Unescaped JSON downloaded! ✓', 'success');
        }

        function clearAll() {
            document.getElementById('input').value = '';
            document.getElementById('output').textContent = 'Cleaned HTML will appear here...';
            document.getElementById('converted-output').textContent = 'Unescaped JSON will appear here...';
            document.getElementById('original').textContent = 'Original input will appear here...';
            const iframe = document.getElementById('preview');
            iframe.src = 'about:blank';
            document.getElementById('message').innerHTML = '';
            document.getElementById('stats').style.display = 'none';
            currentHTML = '';
            currentConverted = '';
            showMessage('All fields cleared! ✓', 'success');
        }

        function showMessage(msg, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.className = type;
            messageDiv.textContent = msg;
            setTimeout(() => {
                messageDiv.innerHTML = '';
            }, 5000);
        }

        function switchTab(event, tabName) {
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            if (event && event.target) {
                event.target.classList.add('active');
            }

            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(tabName + '-tab').classList.add('active');
        }

        function switchTabProgrammatic(tabName) {
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Add active class to the target tab button
            document.querySelectorAll('.tab').forEach(tab => {
                if (tab.textContent.toLowerCase().includes(tabName)) {
                    tab.classList.add('active');
                }
            });

            // Remove active class from all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Add active class to the target tab content
            document.getElementById(tabName + '-tab').classList.add('active');
        }

        function refreshPreview(){
            if (!currentHTML || currentHTML === '') {
                showMessage('No HTML to preview. Process ad code first.', 'error');
                return;
            }
            // Reload the iframe from the Flask route
            const iframe = document.getElementById('preview');
            iframe.src = '/preview?t=' + Date.now();
            showMessage('Preview refreshed! ✓', 'success');
        }

        function openInNewTab() {
            if (!currentHTML || currentHTML === '') {
                showMessage('No HTML to preview. Process ad code first.', 'error');
                return;
            }
            
            // Create a complete HTML document
            const timestamp = new Date().toLocaleString();
            const fullHtml = '<!DOCTYPE html>' +
                '<html lang="en">' +
                '<head>' +
                '<meta charset="UTF-8">' +
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
                '<title>Ad Preview - ' + timestamp + '</title>' +
                '<style>' +
                'body { margin: 0; padding: 20px; font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }' +
                '.container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }' +
                '.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; }' +
                '.ad-container { background: #f8f9fa; border: 2px solid #e0e0e0; border-radius: 8px; padding: 15px; min-height: 100px; }' +
                '.info { background: #e3f2fd; border: 1px solid #90caf9; color: #1565c0; padding: 12px; border-radius: 6px; margin-bottom: 15px; font-size: 13px; }' +
                '</style>' +
                '</head>' +
                '<body>' +
                '<div class="container">' +
                '<div class="header">' +
                '<h2>🎯 Live Ad Preview</h2>' +
                '<p style="margin: 5px 0 0 0; font-size: 13px; opacity: 0.9;">Generated on ' + timestamp + '</p>' +
                '</div>' +
                '<div class="info">' +
                'ℹ️ <strong>Note:</strong> This is a live preview of your ad code. Dynamic ads may take a few seconds to load. ' +
                'If nothing appears, the ad may require specific website context or server-side configuration.' +
                '</div>' +
                '<div class="ad-container">' +
                currentHTML +
                '</div>' +
                '</div>' +
                '</body>' +
                '</html>';
            
            // Open in new tab
            const newWindow = window.open();
            if (newWindow) {
                newWindow.document.open();
                newWindow.document.write(fullHtml);
                newWindow.document.close();
                showMessage('Preview opened in new tab! ✓', 'success');
            } else {
                showMessage('Popup blocked. Please allow popups for this site.', 'error');
            }
        }
    </script>
</body>
</html>
'''

def extract_from_url(html_content, param_name):
    """Extract a specific parameter value from URLs in HTML content"""
    # Find all URLs in the content
    url_pattern = r'https?://[^\s"\'\)>]+'
    urls = re.findall(url_pattern, html_content)
    
    for url in urls:
        try:
            # Remove any trailing backslashes or quotes
            url = url.rstrip('\\').rstrip('"').rstrip("'")
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if param_name in params:
                return unquote(params[param_name][0])
        except:
            continue
    return None

def parse_url_params(html_content):
    """Parse all URL parameters from the first URL found in HTML"""
    url_pattern = r'https?://[^\s"\'\)>]+'
    urls = re.findall(url_pattern, html_content)
    
    all_params = {}
    for url in urls:
        try:
            url = url.rstrip('\\').rstrip('"').rstrip("'")
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            # Convert single-item lists to strings
            for key, value in params.items():
                if key not in all_params:  # Don't overwrite
                    all_params[key] = unquote(value[0]) if len(value) == 1 else [unquote(v) for v in value]
        except:
            continue
    
    return all_params

def is_pfm_network(html_content):
    """Determine if this is a PFM network ad or Media.net"""
    # Check for specific indicators
    if 'pm-serv.co' in html_content or 'pubmatic' in html_content.lower():
        return True
    return False

def encode_bdata(bdata):
    """Encode bdata for script variable"""
    if not bdata:
        return ""
    # Escape special characters for JavaScript string
    bdata = bdata.replace('\\', '\\\\')
    bdata = bdata.replace('"', '\\"')
    bdata = bdata.replace('\n', '\\n')
    bdata = bdata.replace('\r', '\\r')
    return bdata

def convert_to_script_format(cleaned_html):
    """
    Convert Media.net/PFM ad code to script variable format
    
    Format 1 (Original): Full HTML with img tags and inline scripts
    Format 2 (Output): Simple script variables + external loader
    """
    try:
        # Extract bdata
        bdata = extract_from_url(cleaned_html, 'vgde_bdata')
        if not bdata:
            bdata = extract_from_url(cleaned_html, 'vgd_bdata')  # Try alternative
        
        # Extract all URL parameters
        params = parse_url_params(cleaned_html)
        
        # Determine network type
        is_pfm = is_pfm_network(cleaned_html)
        prefix = "pfm_" if is_pfm else "mn_"
        network_name = "PFM" if is_pfm else "MN"
        
        # Determine script source URL
        if is_pfm:
            script_src = "https://l.pm-serv.co"
        else:
            script_src = "https://contextual.media.net"
        
        # Build script tag
        script_lines = [f'<script id="{network_name}">']
        
        # Add bdata first
        if bdata:
            script_lines.append(f'window.{prefix}bdata = "{encode_bdata(bdata)}";')
        
        # Add important parameters as variables
        important_params = ['cid', 'prid', 'crid', 'hvsid', 'vi', 'sc', 'cc', 'vgd_asn', 
                          'vgd_bid', 'vgd_ydspr', 'ugd', 'lf', 'wsip', 'requrl']
        
        for param in important_params:
            if param in params:
                value = params[param]
                script_lines.append(f'window.{prefix}{param} = "{value}";')
        
        # Close script and add external loader
        script_lines.append('</script>')
        
        # Add external script loader with CID
        cid = params.get('cid', 'UNKNOWN')
        script_lines.append(f'<script src="{script_src}/loader.js?cid={cid}&type={network_name.lower()}"></script>')
        
        return '\n'.join(script_lines)
        
    except Exception as e:
        print(f"Error in convert_to_script_format: {str(e)}")
        return None

def unescape_json_string(escaped_json):
    """
    Convert escaped JSON string to normal JSON string
    Input:  {\"adcode\":\"\\u003cimg...
    Output: {"adcode":"\u003cimg...
    """
    try:
        # Unescape backslash-quote to regular quote
        unescaped = escaped_json.replace('\\"', '"')
        return unescaped
    except Exception as e:
        print(f"Error unescaping JSON: {str(e)}")
        return escaped_json

def clean_adcode(adcode_json_str):
    """
    Complete ad code cleaning process:
    1. Extract adcode value using regex (handles escaped JSON)
    2. Decode unicode escapes (\u003c etc)
    3. Unescape JSON string escapes (\\", \\n, etc)
    4. Unescape HTML entities
    """
    # Strip whitespace
    adcode_json_str = adcode_json_str.strip()
    
    # Extract the adcode value using regex
    # Look for "adcode":"..." or \"adcode\":\"...
    # The content goes until we hit ",\"adomain or ","adomain or end
    
    # Try multiple patterns to handle different escape levels
    patterns = [
        r'\\?"adcode\\?"\s*:\s*\\?"(.+?)\\?"\s*,\s*\\?"adomain',  # Standard with adomain
        r'\\?"adcode\\?"\s*:\s*\\?"(.+?)\\?"\s*,',                # With comma
        r'\\?"adcode\\?"\s*:\s*\\?"(.+?)\\?"(?:\s*\}|$)',         # With closing brace or end
    ]
    
    adcode = None
    for pattern in patterns:
        match = re.search(pattern, adcode_json_str, re.DOTALL)
        if match:
            adcode = match.group(1)
            break
    
    if not adcode:
        raise ValueError('Could not find "adcode" field in input. Please ensure your input contains {"adcode":"..."}')
    
    # Step 1: Decode unicode escapes (\u003c -> <, \u003e -> >, etc)
    def decode_unicode(match):
        return chr(int(match.group(1), 16))
    
    cleaned = re.sub(r'\\u([0-9a-fA-F]{4})', decode_unicode, adcode)
    
    # Step 2: Unescape JSON string escapes
    cleaned = cleaned.replace('\\"', '"')
    cleaned = cleaned.replace('\\\\', '\\')
    cleaned = cleaned.replace('\\/', '/')
    cleaned = cleaned.replace('\\n', '\n')
    cleaned = cleaned.replace('\\r', '\r')
    cleaned = cleaned.replace('\\t', '\t')
    cleaned = cleaned.replace('\\b', '\b')
    cleaned = cleaned.replace('\\f', '\f')
    
    # Step 3: Unescape HTML entities (if any)
    cleaned = html.unescape(cleaned)
    
    return cleaned, adcode_json_str, adcode

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/preview')
def preview():
    """Serve the ad HTML directly for preview"""
    global current_ad_html
    if not current_ad_html:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; text-align: center; background: #f8f9fa; }
                .message { background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 20px; border-radius: 8px; display: inline-block; }
            </style>
        </head>
        <body>
            <div class="message">
                <h3>⚠️ No Ad to Preview</h3>
                <p>Please process an ad code first, then come back to this preview.</p>
            </div>
        </body>
        </html>
        '''
    
    # Create a proper HTML document wrapper for the ad
    preview_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1200, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Ad Preview</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #f8f9fa;
            padding: 20px;
        }}
        .preview-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }}
        .ad-container {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            min-height: 100px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .loading {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 14px;
        }}
        .spinner {{
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="preview-header">
        <h2 style="margin: 0; font-size: 18px;">🎯 Live Ad Preview</h2>
        <p style="margin: 5px 0 0 0; font-size: 13px; opacity: 0.9;">Your ad code is rendering below with full JavaScript support</p>
    </div>
    <div style="background: #fff3cd; border: 1px solid #ffc107; color: #856404; padding: 15px; margin-bottom: 20px; border-radius: 8px; font-size: 13px;">
        <strong>⚠️ Why you might see a blank/broken image:</strong>
        <p style="margin: 8px 0 0 0;">Ad networks (Media.net, Google AdSense, etc.) verify the domain before serving ads. Since this is running on <strong>localhost</strong>, the ad network won't show actual ads - they only work on real registered domains like <code>yourwebsite.com</code>.</p>
        <p style="margin: 8px 0 0 0;"><strong>✅ Solution:</strong> Copy the HTML from the "Cleaned HTML" tab and paste it into your actual website. The ads will work there!</p>
    </div>
    <div class="ad-container">
        <div class="loading" id="loadingMsg">
            <div class="spinner"></div>
            <div>Loading ad content... (may take a few seconds)</div>
        </div>
        {current_ad_html}
    </div>
    <script>
        // Hide loading message after 3 seconds
        setTimeout(function() {{
            var loading = document.getElementById('loadingMsg');
            if (loading) loading.style.display = 'none';
        }}, 3000);
        
        // Log when page loads
        console.log('Ad preview loaded successfully at', new Date().toISOString());
        
        // Monitor for ad iframe creation
        var checkCount = 0;
        var checkInterval = setInterval(function() {{
            var iframes = document.querySelectorAll('iframe');
            checkCount++;
            if (iframes.length > 0) {{
                console.log('Ad iframe(s) detected:', iframes.length);
                var loading = document.getElementById('loadingMsg');
                if (loading) {{
                    loading.innerHTML = '<div style="color: #28a745;">✓ Ad is loading...</div>';
                }}
                setTimeout(function() {{
                    if (loading) loading.style.display = 'none';
                }}, 2000);
                clearInterval(checkInterval);
            }} else if (checkCount > 10) {{
                clearInterval(checkInterval);
            }}
        }}, 500);
    </script>
</body>
</html>'''
    
    return preview_html

# Store the current ad HTML in memory (simple cache)
current_ad_html = ""

@app.route('/process', methods=['POST'])
def process():
    global current_ad_html
    try:
        data = request.get_json()
        adcode_json = data.get('adcode', '')
        
        if not adcode_json.strip():
            return jsonify({'success': False, 'error': 'Empty input'})
        
        # Clean the ad code
        cleaned_html, original_input, adcode = clean_adcode(adcode_json)
        
        # Store the cleaned HTML for preview route
        current_ad_html = cleaned_html
        
        # Unescape the original JSON string
        unescaped_json = unescape_json_string(adcode_json)
        
        # Debug: Log first 200 chars of cleaned HTML
        print(f"Cleaned HTML preview: {cleaned_html[:200]}...")
        print(f"Unescaped JSON created")
        
        # Calculate statistics
        script_tags = cleaned_html.count('<script')
        other_tags = len(re.findall(r'<[^/!][^>]*>', cleaned_html)) - script_tags
        
        # Detect ad network type
        ad_network = 'Unknown'
        if 'media.net' in cleaned_html.lower():
            ad_network = 'Media.net'
        elif 'doubleclick' in cleaned_html.lower() or 'googlesyndication' in cleaned_html.lower():
            ad_network = 'Google AdSense/DFP'
        elif 'adnxs' in cleaned_html.lower():
            ad_network = 'AppNexus'
        
        # Check if it's a dynamic/programmatic ad
        is_dynamic = 'iframe' in cleaned_html.lower() and script_tags > 0
        
        stats = {
            'html_length': len(cleaned_html),
            'script_tags': script_tags,
            'other_tags': other_tags,
            'ad_network': ad_network,
            'is_dynamic': is_dynamic
        }
        
        # Format original for display (just show first 500 chars as preview)
        formatted_json = adcode_json[:500] + "..." if len(adcode_json) > 500 else adcode_json
        
        # Add raw extracted adcode to response for debugging
        return jsonify({
            'success': True,
            'cleaned_html': cleaned_html,
            'unescaped_json': unescaped_json,
            'formatted_json': formatted_json,
            'stats': stats,
            'preview_url': '/preview',
            'debug_info': {
                'extracted_length': len(adcode) if 'adcode' in locals() else 0,
                'cleaned_length': len(cleaned_html),
                'first_100_chars': cleaned_html[:100] if cleaned_html else 'Empty'
            }
        })
        
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'})

if __name__ == '__main__':
    print("=" * 60)
    print("Ad Code Cleaner & JSON Unescaper Server Started!")
    print("=" * 60)
    print("Features:")
    print("  - Clean HTML from JSON ad code")
    print("  - Unescape JSON strings (convert \\\" to \")")
    print("  - Live preview")
    print("  - Copy & download functionality")
    print("=" * 60)
    print("Open your browser and navigate to:")
    print("   http://localhost:5000")
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    app.run(debug=True, port=5000, host='0.0.0.0')