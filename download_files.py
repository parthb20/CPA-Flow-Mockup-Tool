"""
Quick script to download Google Drive files locally
Run this once to bypass rate limits during development
"""

import os
import sys

# Create data folder
os.makedirs('data', exist_ok=True)

# Check if gdown is available
try:
    import gdown
    GDOWN_AVAILABLE = True
except ImportError:
    print("⚠️ gdown not installed. Installing now...")
    os.system(f"{sys.executable} -m pip install gdown")
    import gdown
    GDOWN_AVAILABLE = True

print("=" * 60)
print("📥 DOWNLOADING FILES FROM GOOGLE DRIVE")
print("=" * 60)
print()

# File definitions
files = [
    {
        'name': 'FILE_A (Main CSV Data)',
        'id': '1DXR77Tges9kkH3x7pYin2yo9De7cxqpc',
        'output': 'data/file_a.csv.gz'
    },
    {
        'name': 'FILE_B (SERP Templates JSON)',
        'id': '1SXcLm1hhzQK23XY6Qt7E1YX5Fa-2Tlr9',
        'output': 'data/file_b.json'
    },
    {
        'name': 'FILE_D (Pre-rendered Creatives)',
        'id': '1Uz29aIA1YtrnqmJaROgiiG4q1CvJ6arK',
        'output': 'data/file_d.csv'
    }
]

# Download each file
for i, file_info in enumerate(files, 1):
    print(f"[{i}/3] Downloading {file_info['name']}...")
    print(f"      Saving to: {file_info['output']}")
    
    try:
        url = f"https://drive.google.com/uc?id={file_info['id']}"
        gdown.download(url, file_info['output'], quiet=False, fuzzy=True)
        
        # Check if file exists and has content
        if os.path.exists(file_info['output']):
            size = os.path.getsize(file_info['output'])
            if size > 0:
                print(f"      ✅ Success! ({size:,} bytes)")
            else:
                print(f"      ⚠️ Warning: File is empty")
        else:
            print(f"      ❌ Failed: File not created")
    except Exception as e:
        print(f"      ❌ Error: {str(e)}")
    
    print()

print("=" * 60)
print("✅ DOWNLOAD COMPLETE!")
print("=" * 60)
print()
print("Next steps:")
print("1. Check the 'data/' folder for downloaded files")
print("2. Restart Streamlit: streamlit run cpa_flow_mockup.py")
print("3. App will now load instantly from local files! ⚡")
print()
print("Note: You can delete 'data/' folder anytime to force cloud download")
