import json
import html
import re
import warnings
from urllib.parse import quote

try:
    from flask import Flask, request, render_template_string
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    # Suppress SSL warnings
    warnings.simplefilter('ignore', InsecureRequestWarning)
except ImportError as e:
    print("Missing required packages. Install them with:")
    print("pip install flask requests")
    raise e

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ad_Code Renderer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .input-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            margin-bottom: 30px;
        }
        textarea {
            width: 100%;
            min-height: 200px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #11998e;
        }
        .keywords-input {
            min-height: 120px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            font-size: 14px;
        }
        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 20px;
        }
        button {
            flex: 1;
            padding: 15px 30px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .render-btn {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        .render-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(17, 153, 142, 0.4);
        }
        .clear-btn {
            background: #f44336;
            color: white;
        }
        .clear-btn:hover {
            background: #da190b;
        }
        .output-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .ad-preview {
            border: 2px dashed #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            background: #fafafa;
            min-height: 650px;
            overflow: visible;
            position: relative;
        }
        .ad-preview * {
            max-width: none !important;
        }
        .ad-iframe-container {
            border: 2px dashed #e0e0e0;
            border-radius: 8px;
            background: white;
            min-height: 650px;
            position: relative;
        }
        .ad-iframe-container iframe {
            width: 100%;
            min-height: 650px;
            border: none;
        }
        .info-box {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .error {
            background: #ffebee;
            border-left: 4px solid #f44336;
            color: #c62828;
            padding: 15px;
            margin-top: 20px;
            border-radius: 4px;
        }
        .success {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            color: #2e7d32;
            padding: 15px;
            margin-top: 20px;
            border-radius: 4px;
        }
        .metadata {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .metadata-item {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 6px;
        }
        .metadata-label {
            font-weight: bold;
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
        }
        .metadata-value {
            color: #333;
            font-size: 14px;
            margin-top: 5px;
            word-break: break-all;
        }
        .cipher-info {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
            font-size: 13px;
            line-height: 1.6;
        }
        .cipher-info code {
            background: #f5f5f5;
            padding: 8px;
            display: block;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            margin-top: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Ad Code Renderer</h1>
        
        <div class="input-section">
            <div class="info-box">
                <strong>📝 Instructions:</strong> Paste your request JSON and keywords, then click "Render Ad"
            </div>
            
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">Request JSON:</label>
                    <textarea name="json_data" placeholder='Paste your request JSON here'>{{ input_data }}</textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Keywords (one per line - any keywords work):</label>
                    <textarea name="keywords" class="keywords-input" placeholder='technology
health
finance'>{{ input_keywords }}</textarea>
                </div>
                
                <div class="form-group">
                    <label style="display: flex; align-items: center; font-size: 14px; cursor: pointer;">
                        <input type="checkbox" name="encrypt_keywords" value="1" {% if encrypt_keywords %}checked{% endif %} style="margin-right: 8px;">
                        <span>Encrypt keywords (Caesar cipher, shift 5)</span>
                    </label>
                    <div style="font-size: 12px; color: #666; margin-top: 5px; margin-left: 24px;">
                        Uncheck to test if ad server respects unencrypted keywords
                    </div>
                </div>
                
                <div class="button-group">
                    <button type="submit" class="render-btn">🚀 Render Ad</button>
                    <button type="button" class="clear-btn" onclick="clearForm()">🗑️ Clear</button>
                </div>
            </form>
            
            {% if error %}
            <div class="error">
                <strong>❌ Error:</strong> {{ error }}
            </div>
            {% endif %}
        </div>
        
        {% if adcode %}
        <div class="output-section">
            <div class="success">
                <strong>✅ Ad Rendered Successfully!</strong>
            </div>
            
            {% if cipher_debug %}
            <div class="cipher-info">
                {{ cipher_debug | safe }}
            </div>
            {% endif %}
            
            {% if metadata %}
            <h3 style="margin-top: 20px; margin-bottom: 15px; color: #333;">📊 Metadata</h3>
            <div class="metadata">
                {% for key, value in metadata.items() %}
                <div class="metadata-item">
                    <div class="metadata-label">{{ key }}</div>
                    <div class="metadata-value">{{ value }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <h3 style="margin-top: 20px; margin-bottom: 15px; color: #333;">🎨 Ad Preview (Direct Render)</h3>
            <div style="background: #fff9c4; border-left: 4px solid #fbc02d; padding: 12px; margin-bottom: 15px; border-radius: 4px; font-size: 13px;">
                <strong>⏳ Note:</strong> The ad script is loading... Please wait 10-15 seconds. 
                <span id="loadingStatus" style="color: #f57c00; font-weight: bold;">Loading...</span>
            </div>
            <div id="adStatusLog" style="background: #e3f2fd; border: 1px solid #2196F3; padding: 10px; margin-bottom: 15px; border-radius: 4px; font-size: 12px; font-family: monospace; max-height: 100px; overflow-y: auto;">
                <div style="color: #1976d2;">Initializing ad renderer...</div>
            </div>
            <div class="ad-preview" id="adContainer">
                {{ adcode | safe }}
            </div>
            
            <script>
                (function() {
                    const adContainer = document.getElementById('adContainer');
                    const statusLog = document.getElementById('adStatusLog');
                    const loadingStatus = document.getElementById('loadingStatus');
                    let checkCount = 0;
                    let mutationCount = 0;
                    const maxChecks = 30; // Check for 15 seconds (every 500ms)
                    const maxMutations = 50; // Stop logging after 50 mutations to prevent slowdown
                    let observerActive = true;
                    
                    function log(message, color = '#1976d2') {
                        const time = new Date().toLocaleTimeString();
                        const logEntry = document.createElement('div');
                        logEntry.style.color = color;
                        logEntry.textContent = `[${time}] ${message}`;
                        statusLog.appendChild(logEntry);
                        statusLog.scrollTop = statusLog.scrollHeight;
                        
                        // Limit log entries to prevent memory issues
                        if (statusLog.children.length > 100) {
                            statusLog.removeChild(statusLog.firstChild);
                        }
                    }
                    
                    log('Ad container initialized');
                    log('Scripts in container: ' + adContainer.querySelectorAll('script').length);
                    
                    // Monitor for changes - with throttling to prevent page freeze
                    const observer = new MutationObserver((mutations) => {
                        if (!observerActive) return;
                        
                        mutationCount += mutations.length;
                        
                        if (mutationCount > maxMutations) {
                            log('⚠ Too many mutations - stopping observer to prevent lag', '#f57c00');
                            observer.disconnect();
                            observerActive = false;
                            return;
                        }
                        
                        // Only log significant mutations
                        const addedElements = [];
                        mutations.forEach((mutation) => {
                            mutation.addedNodes.forEach(node => {
                                if (node.nodeType === 1) { // Element node
                                    addedElements.push(node.tagName + (node.id ? ' #' + node.id : ''));
                                }
                            });
                        });
                        
                        if (addedElements.length > 0 && mutationCount < maxMutations) {
                            log('✓ Added: ' + addedElements.join(', '), '#2e7d32');
                        }
                    });
                    
                    observer.observe(document.body, { childList: true, subtree: true });
                    
                    // Check periodically for ad content
                    const checkInterval = setInterval(() => {
                        checkCount++;
                        const hasIframe = document.querySelector('iframe') !== null;
                        const hasAdContent = document.querySelector('[id*="mn"]') !== null;
                        const hasScript = document.querySelector('script[src*="media.net"]') !== null;
                        
                        if (hasIframe || hasAdContent) {
                            log('✓ AD CONTENT DETECTED!', '#2e7d32');
                            loadingStatus.textContent = 'Ad Loaded!';
                            loadingStatus.style.color = '#2e7d32';
                            clearInterval(checkInterval);
                            if (observerActive) observer.disconnect();
                        } else if (checkCount >= maxChecks) {
                            log(`⚠ Timeout after 15s. Script loaded: ${hasScript}`, '#f57c00');
                            loadingStatus.textContent = 'No ad rendered';
                            loadingStatus.style.color = '#d32f2f';
                            clearInterval(checkInterval);
                            if (observerActive) observer.disconnect();
                        } else if (checkCount % 4 === 0) {
                            log(`Waiting... (${checkCount * 0.5}s)`, '#757575');
                        }
                    }, 500);
                    
                    // Force cleanup after 20 seconds regardless
                    setTimeout(() => {
                        if (observerActive) {
                            observer.disconnect();
                            observerActive = false;
                            log('Observer stopped after 20s', '#757575');
                        }
                    }, 20000);
                    
                    log('Monitoring started...');
                })();
            </script>
            
            <h3 style="margin-top: 20px; margin-bottom: 15px; color: #333;">📄 Raw Ad Code</h3>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; overflow-x: auto;">
                <pre style="margin: 0; font-size: 11px; white-space: pre-wrap; word-wrap: break-word;">{{ adcode }}</pre>
            </div>
        </div>
        {% endif %}
    </div>
    
    <script>
        function clearForm() {
            document.querySelectorAll('textarea').forEach(t => t.value = '');
        }
    </script>
</body>
</html>
'''

def get_cipher_key():
    """Return the Caesar cipher key - UPDATE THIS WITH YOUR ACTUAL KEY"""
    return """saflkfkeqflkewq"""

def caesar_encrypt(text, key, shift=5):
    """
    Caesar cipher with shift of  5 
    Encrypts text using the provided key and a shift value
    Each character is shifted by 5 positions in the ASCII table
    """
    if not text:
        return text
    
    encrypted = []
    
    for char in text:
        # Apply Caesar shift of 5
        shifted_val = ord(char) + shift
        encrypted.append(chr(shifted_val))
    
    return ''.join(encrypted)

def caesar_decrypt(text, key, shift=5):
    """
    Caesar cipher decrypt - reverse of encrypt
    Shifts each character back by the shift amount
    """
    if not text:
        return text
    
    decrypted = []
    
    for char in text:
        # Reverse the shift
        shifted_val = ord(char) - shift
        decrypted.append(chr(shifted_val))
    
    return ''.join(decrypted)

def process_keywords(keywords_text):
    """Convert keywords text to list"""
    if not keywords_text:
        return []
    
    lines = [line.strip() for line in keywords_text.split('\n') if line.strip()]
    return lines

def keywords_to_json_format(keywords_list):
    """Convert keywords to [{"t":"kw1"},{"t":"kw2"}] format"""
    if not keywords_list:
        return []
    
    return [{"t": kw} for kw in keywords_list]

def encrypt_and_encode_keywords(keywords_list, cipher_key):
    """
    Convert keywords to JSON format, encrypt with Caesar cipher (shift 5), then URL encode
    """
    if not keywords_list:
        return "", "", ""
    
    # Convert to [{"t":"kw1"},{"t":"kw2"}] format
    kw_json_list = keywords_to_json_format(keywords_list)
    
    # Convert to JSON string (compact, no spaces)
    json_string = json.dumps(kw_json_list, separators=(',', ':'))
    
    print(f"\n{'='*60}")
    print(f"ENCRYPTION PROCESS (Caesar Cipher - Shift 5)")
    print(f"{'='*60}")
    print(f"📋 Original JSON: {json_string}")
    print(f"📏 JSON Length: {len(json_string)}")
    print(f"🔑 Cipher Key: {cipher_key}")
    
    # Encrypt with Caesar cipher (shift 5)
    encrypted = caesar_encrypt(json_string, cipher_key, shift=5)
    
    print(f"\n🔐 Encrypted (Caesar +5): {encrypted}")
    print(f"📏 Encrypted Length: {len(encrypted)}")
    
    # URL encode
    url_encoded = quote(encrypted, safe='')
    
    print(f"\n🔗 URL Encoded: {url_encoded}")
    print(f"📏 URL Encoded Length: {len(url_encoded)}")
    
    # Verify by decrypting
    decrypted = caesar_decrypt(encrypted, cipher_key, shift=5)
    print(f"\n✅ VERIFICATION:")
    print(f"🔓 Decrypted back: {decrypted}")
    print(f"✓ Match: {'YES' if decrypted == json_string else 'NO'}")
    
    if decrypted != json_string:
        print(f"⚠️ WARNING: Decryption doesn't match original!")
        print(f"Expected: {json_string}")
        print(f"Got:      {decrypted}")
    
    print(f"{'='*60}\n")
    
    return url_encoded, encrypted, json_string

def unescape_adcode(adcode):
    """
    Unescape only unicode sequences like \u003c, but preserve JavaScript string escaping
    This ensures mn_misc and other JSON strings remain valid
    """
    if not adcode:
        return adcode
    
    original_len = len(adcode)
    
    # Only unescape unicode sequences (\u003c, \u003e, etc.) and backslash escapes (\/, \")
    # But do it carefully to preserve JavaScript JSON string literals
    if '\\u' in adcode or '\\/' in adcode:
        try:
            # Use json.loads to unescape unicode sequences
            # This handles \u003c -> <, \u003e -> >, \/ -> /, etc.
            adcode = json.loads('"' + adcode + '"')
            print(f"✓ JSON unescaped (unicode sequences): {original_len} → {len(adcode)} chars")
        except Exception as e:
            print(f"⚠ Could not JSON unescape: {e}")
            # Fallback: just replace common unicode escapes manually
            adcode = adcode.replace('\\u003c', '<')
            adcode = adcode.replace('\\u003e', '>')
            adcode = adcode.replace('\\u003d', '=')
            adcode = adcode.replace('\\/', '/')
            print(f"✓ Manual unicode unescape applied")
    
    # Handle HTML entities (shouldn't be many in adcode)
    if '&' in adcode:
        adcode = html.unescape(adcode)
        print(f"✓ HTML entities unescaped")
    
    return adcode

def replace_kd_in_adcode(adcode, url_encoded_kd):
    """
    Add or replace mn_kd variable in the script tag
    mn_kd should be added as a JavaScript variable like mn_width, mn_height, etc.
    """
    if not url_encoded_kd:
        return adcode
    
    # Pattern to find the script tag with mn_ variables
    # Look for the section between the last mn_ variable and </script>
    
    # Check if mn_kd already exists
    if 'mn_kd=' in adcode or 'mn_kd =' in adcode:
        # Replace existing mn_kd value
        # Pattern: mn_kd="anything" or mn_kd = "anything"
        adcode = re.sub(
            r'mn_kd\s*=\s*"[^"]*"',
            f'mn_kd="{url_encoded_kd}"',
            adcode
        )
        print(f"✓ Replaced existing mn_kd value")
    else:
        # Add mn_kd before the closing </script> of the first script tag
        # Find the position right before </script> in the first script tag
        match = re.search(r'(mn_csrsv2\s*=\s*"[^"]+";)(</script>)', adcode)
        if match:
            # Insert mn_kd after mn_csrsv2 (the last variable)
            adcode = adcode[:match.end(1)] + f'mn_kd="{url_encoded_kd}";' + adcode[match.end(1):]
            print(f"✓ Added mn_kd variable after mn_csrsv2")
        else:
            # Fallback: try to find any </script> tag in the adcode
            match = re.search(r'(;)(</script>)', adcode, re.IGNORECASE)
            if match:
                adcode = adcode[:match.end(1)] + f'mn_kd="{url_encoded_kd}";' + adcode[match.end(1):]
                print(f"✓ Added mn_kd variable before </script>")
            else:
                print(f"⚠ Could not find suitable location to add mn_kd")
    
    return adcode

@app.route('/', methods=['GET', 'POST'])
def index():
    adcode = None
    metadata = None
    error = None
    input_data = ''
    input_keywords = ''
    cipher_debug = None
    encrypt_keywords = True  # Default to encrypted
    
    if request.method == 'POST':
        json_data = request.form.get('json_data', '').strip()
        keywords_text = request.form.get('keywords', '').strip()
        encrypt_keywords = request.form.get('encrypt_keywords') == '1'
        input_data = json_data
        input_keywords = keywords_text
        
        if not json_data:
            error = "Please paste request JSON data"
        else:
            try:
                # Handle double-stringified JSON
                if json_data.startswith('{\\'):
                    json_data = json.loads('"' + json_data + '"')
                
                # Parse request
                request_data = json.loads(json_data)
                
                # Process keywords
                keywords_list = process_keywords(keywords_text)
                
                # Build debug info
                debug_lines = []
                debug_lines.append(f"<strong>🔐 Encryption:</strong> {'ENABLED (Caesar Shift 5)' if encrypt_keywords else 'DISABLED (Plain Text)'}")
                debug_lines.append(f"<br><strong>📝 Keywords:</strong> {len(keywords_list)} total → {keywords_list}")
                
                if keywords_list:
                    # Convert to JSON format
                    kw_json_list = keywords_to_json_format(keywords_list)
                    json_str = json.dumps(kw_json_list, separators=(',', ':'))
                    
                    debug_lines.append(f"<br><br><strong>📋 Original JSON String:</strong><br><code style='background:#f5f5f5;padding:5px;display:block;'>{json_str}</code>")
                    debug_lines.append(f"<br><strong>📏 JSON Length:</strong> {len(json_str)} characters")
                    
                    if encrypt_keywords:
                        # Get cipher key and encrypt
                        cipher_key = get_cipher_key()
                        url_encoded_kd, encrypted_str, _ = encrypt_and_encode_keywords(keywords_list, cipher_key)
                        
                        debug_lines.append(f"<br><br><strong>🔐 Encrypted KD Value (Caesar Shift 5):</strong><br><code style='background:#ffe0b2;padding:5px;display:block;word-break:break-all;'>{encrypted_str}</code>")
                        debug_lines.append(f"<br><strong>📏 Encrypted Length:</strong> {len(encrypted_str)} characters")
                        
                        # Verify decryption
                        decrypted_verification = caesar_decrypt(encrypted_str, cipher_key, shift=5)
                        matches = decrypted_verification == json_str
                        debug_lines.append(f"<br><br><strong>🔓 Decrypted Back (Verification):</strong><br><code style='background:#{'d4edda' if matches else 'f8d7da'};padding:5px;display:block;'>{decrypted_verification}</code>")
                        debug_lines.append(f"<br><strong>✓ Verification:</strong> {'PASS - Matches original' if matches else 'FAIL - Does not match!'}")
                    else:
                        # No encryption - just URL encode the plain JSON
                        url_encoded_kd = quote(json_str, safe='')
                        debug_lines.append(f"<br><br><strong>ℹ️ No Encryption Applied</strong>")
                        debug_lines.append(f"<br>Keywords will be sent as plain JSON")
                    
                    debug_lines.append(f"<br><br><strong>🔗 URL Encoded KD Value:</strong><br><code style='background:#c8e6c9;padding:5px;display:block;word-break:break-all;'>{url_encoded_kd}</code>")
                    debug_lines.append(f"<br><strong>📏 URL Encoded Length:</strong> {len(url_encoded_kd)} characters")
                else:
                    url_encoded_kd = ""
                
                cipher_debug = "".join(debug_lines)
                
                # Call Weaver API
                # Try different endpoints if one doesn't work:
                # - http://weaver.21master.srv.media.net/v3/adcode
                # - https://weaver.22master.srv.media.net/v3/adcode
                # - http://weaver.srv.media.net/v3/adcode
                api_url = "http://weaver.21master.srv.media.net/v3/adcode"
                headers = {
                    'Content-Type': 'application/json',
                    'FMTP-MAP': 't6BpxluW_T9uP75dd18ex-9QuWHm5mx7X9n0HmHrwPo%3D',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                
                print(f"\n{'='*80}")
                print(f"🌐 API Request to: {api_url}")
                print(f"📝 Keywords: {keywords_list}")
                print(f"📦 Request has {len(request_data)} fields")
                print(f"{'='*80}\n")
                
                try:
                    response = requests.post(
                        api_url,
                        json=request_data,
                        headers=headers,
                        timeout=30,
                        verify=False
                    )
                    
                    print(f"✓ Response Status: {response.status_code}")
                    print(f"📊 Response Headers: {dict(response.headers)}")
                    if response.status_code != 200:
                        print(f"❌ Response Body: {response.text[:500]}")
                    print()
                    
                except requests.exceptions.ConnectionError as e:
                    error = f"❌ Connection Error: Cannot reach API server at {api_url}<br>Error: {str(e)}<br><br>Please check:<br>1. Is the API endpoint correct?<br>2. Are you connected to the correct network/VPN?<br>3. Is the server running?"
                    print(f"❌ Connection Error: {str(e)}\n")
                except requests.exceptions.Timeout as e:
                    error = f"⏱️ Timeout Error: API request timed out after 30 seconds<br>Error: {str(e)}"
                    print(f"⏱️ Timeout Error: {str(e)}\n")
                except Exception as e:
                    error = f"❌ Request Error: {str(e)}"
                    print(f"❌ Request Error: {str(e)}\n")
                
                if error:
                    pass  # Error already set above, skip further processing
                elif response.status_code != 200:
                    error_details = response.text if response.text else "No error details provided"
                    if response.status_code == 503:
                        error = f"⚠️ API Server Unavailable (503): The Weaver API server is temporarily unavailable. Please check:<br>1. Is the API endpoint correct? ({api_url})<br>2. Is the server running?<br>3. Try again in a few moments.<br><br>Server response: {error_details}"
                    else:
                        error = f"API returned status {response.status_code}: {error_details}"
                else:
                    response_data = response.json()
                    
                    if 'adcode' not in response_data:
                        error = "No 'adcode' in response"
                        print(f"Response keys: {list(response_data.keys())}")
                    else:
                        raw_adcode = response_data['adcode']
                        print(f"\n--- Processing adcode ---")
                        print(f"Raw adcode length: {len(raw_adcode)}")
                        
                        # Step 1: Unescape the adcode
                        print("\nStep 1: Unescaping...")
                        adcode = unescape_adcode(raw_adcode)
                        
                        # Step 2: Replace/add kd parameter
                        if url_encoded_kd:
                            print("\nStep 2: Adding/replacing mn_kd variable...")
                            adcode = replace_kd_in_adcode(adcode, url_encoded_kd)
                        
                        print(f"\nFinal adcode length: {len(adcode)}\n")
                        
                        # Extract metadata
                        metadata = {}
                        if 'adomain' in response_data:
                            metadata['Advertiser Domain'] = response_data['adomain']
                        if 'ecrid' in response_data:
                            metadata['External Creative ID'] = response_data['ecrid']
                        if keywords_list:
                            metadata['Keywords Count'] = str(len(keywords_list))
                        metadata['Adcode Length'] = f"{len(adcode)} characters"
                
            except json.JSONDecodeError as e:
                error = f"Invalid JSON: {str(e)}"
            except requests.exceptions.RequestException as e:
                error = f"API request failed: {str(e)}"
            except Exception as e:
                error = f"Error: {str(e)}"
                import traceback
                print(traceback.format_exc())
    
    return render_template_string(HTML_TEMPLATE, 
                                 adcode=adcode,
                                 metadata=metadata,
                                 error=error,
                                 input_data=input_data,
                                 input_keywords=input_keywords,
                                 cipher_debug=cipher_debug,
                                 encrypt_keywords=encrypt_keywords)

if __name__ == '__main__':
    print("\n" + "="*80)
    print("Ad Code Renderer Server Starting...")
    print("="*80)
    print("Server: http://localhost:5555")
    print("Press CTRL+C to stop")
    print("="*80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5555)