# 🚀 Quick Deployment Guide

## Problem: Large File Downloads from Google Drive

Google Drive blocks automated downloads of large files (>100MB) with virus scan warnings.

## ✅ Solution: Use Smaller File or Alternative Hosting

### **Option 1: Reduce File Size (Recommended)**

1. **Filter your data** to essential rows only:
   - Last 30 days of data
   - Top performing campaigns only
   - Remove test data

2. **Compress efficiently**:
   ```bash
   gzip -9 filtered_data.csv
   ```

3. **Upload to Google Drive** and update FILE_A_ID

### **Option 2: Use GitHub for Data (Best for Streamlit Cloud)**

1. **Add data to your repo** (if < 100MB):
   ```bash
   git add data.csv.gz
   git commit -m "Add data file"
   git push
   ```

2. **Update code** to load from GitHub:
   ```python
   # Instead of Google Drive
   DATA_URL = "https://raw.githubusercontent.com/your-username/your-repo/main/data.csv.gz"
   
   def load_data():
       response = requests.get(DATA_URL)
       content = response.content
       # Then decompress and read...
   ```

### **Option 3: Use Streamlit File Uploader**

Add to your app:
```python
uploaded_file = st.file_uploader("Upload your data file (.csv, .gz, .zip)", type=['csv', 'gz', 'zip'])

if uploaded_file:
    content = uploaded_file.read()
    # Process content...
```

### **Option 4: Use Google Sheets (For smaller datasets)**

If your data fits in Google Sheets (< 5 million cells):
1. Import CSV to Google Sheets
2. Use Sheets export URL (already in code)
3. Works reliably without virus scan issues

## 📦 Current Status

Your file triggers Google Drive's virus scan warning, which requires:
- Manual browser confirmation
- Or special handling that's unreliable

## 🎯 Recommended Next Steps

1. **Test with smaller file** (< 10MB) to verify app works
2. **Then optimize** your data pipeline
3. **Or use GitHub** for data hosting (works great with Streamlit Cloud)

## 💡 For Streamlit Cloud

If deploying to Streamlit Cloud, **GitHub-hosted data** is the most reliable:
- No download limits
- Fast CDN delivery
- Version controlled
- No virus scan warnings
