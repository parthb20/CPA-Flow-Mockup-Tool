from flask import Flask, request, render_template_string
import json
import html

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
            overflow: auto;
        }
        .ad-preview iframe,
        .ad-preview img {
            max-width: none !important;
            width: auto !important;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>Ad Code_Renderer</h1>
        
        <div class="input-section">
            <div class="info-box">
                <strong>📝 Instructions:</strong> Paste your JSON response containing "adcode" field below and click "Render Ad"
            </div>
            
            <form method="POST">
                <textarea name="json_data" placeholder='Paste your JSON here, e.g.:
{
  "adcode": "\\u003cscript...\\u003c/script\\u003e",
  "adomain": "example.com",
  ...
}'>{{ input_data }}</textarea>
                
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
            
            <h3 style="margin-top: 20px; margin-bottom: 15px; color: #333;">🎨 Ad Preview</h3>
            <div class="ad-preview">
                {{ adcode | safe }}
            </div>
        </div>
        {% endif %}
    </div>
    
    <script>
        function clearForm() {
            document.querySelector('textarea').value = '';
        }
    </script>
</body>
</html>
'''

def unescape_adcode(adcode):
    """
    Unescape the adcode string properly
    Handles both \\u003c (double-escaped) and \u003c (single-escaped)
    """
    # Check if this is double-escaped (contains literal \u sequences)
    # If json.loads already parsed it and we still see \u in the string,
    # it means it was double-escaped originally
    if '\\u' in adcode or '\\/' in adcode or '\\"' in adcode:
        try:
            # This is double-escaped - parse it again as JSON
            # Wrap it in quotes and parse as JSON string
            adcode = json.loads('"' + adcode + '"')
        except:
            # If that fails, try manual unicode escape decoding
            try:
                adcode = adcode.encode('utf-8').decode('unicode_escape')
            except:
                pass
    
    # Then unescape HTML entities if any
    adcode = html.unescape(adcode)
    
    return adcode

@app.route('/', methods=['GET', 'POST'])
def index():
    adcode = None
    metadata = None
    error = None
    input_data = ''
    
    if request.method == 'POST':
        json_data = request.form.get('json_data', '').strip()
        input_data = json_data
        
        if not json_data:
            error = "Please paste JSON data"
        else:
            try:
                # Check if JSON is double-stringified (starts with {\" instead of {")
                # This happens when JSON.stringify() is called twice
                if json_data.startswith('{\\'):
                    # It's double-stringified - parse it as a string literal first
                    try:
                        # Wrap in quotes and parse as JSON string to unescape once
                        json_data = json.loads('"' + json_data + '"')
                    except:
                        pass
                
                # Parse JSON
                data = json.loads(json_data)
                
                # Extract adcode
                if 'adcode' not in data:
                    error = "JSON must contain 'adcode' field"
                else:
                    raw_adcode = data['adcode']
                    
                    # Unescape the adcode
                    adcode = unescape_adcode(raw_adcode)
                    
                    # Extract metadata
                    metadata = {}
                    if 'adomain' in data:
                        metadata['Advertiser Domain'] = data['adomain']
                    if 'ecrid' in data:
                        metadata['External Creative ID'] = data['ecrid']
                    
                    # Try to extract vi (view ID) from adcode
                    if 'vi=' in adcode:
                        import re
                        vi_match = re.search(r'vi=(\d+)', adcode)
                        if vi_match:
                            metadata['View ID'] = vi_match.group(1)
                    
                    # Extract hvsid if present
                    if 'hvsid=' in adcode:
                        import re
                        hvsid_match = re.search(r'hvsid=([^&"]+)', adcode)
                        if hvsid_match:
                            metadata['Session ID'] = hvsid_match.group(1)
                    
            except json.JSONDecodeError as e:
                error = f"Invalid JSON: {str(e)}"
            except Exception as e:
                error = f"Error processing data: {str(e)}"
    
    return render_template_string(HTML_TEMPLATE, 
                                 adcode=adcode, 
                                 metadata=metadata,
                                 error=error,
                                 input_data=input_data)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Ad_Code_Renderer Server Starting...")
    print("="*60)
    print("Server running at: http://localhost:5555")
    print("Paste your JSON and click 'Render Ad'")
    print("Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5555)