"""
Data Filtering Script - Run this LOCALLY before uploading to Streamlit
Reduces 1.7GB to < 200MB while keeping all meaningful data
"""

import pandas as pd
import os

# ========================================
# CONFIGURE YOUR FILE PATH HERE:
# ========================================
input_file = "Main_File.gz"  # ← CHANGE THIS to your file name or full path
# Example: "C:\\Users\\bhatt.p\\Downloads\\data.csv.gz"
# Or just: "data.csv.gz" if in same folder
# ========================================

print("="*60)
print("CPA Flow Data Optimizer")
print("="*60)

# Check if file exists
if not os.path.exists(input_file):
    print(f"❌ File not found: {input_file}")
    print(f"💡 Make sure the file path is correct!")
    print(f"   Current directory: {os.getcwd()}")
    exit(1)

print(f"\n📂 Loading {input_file}...")
print("⏳ This may take a few minutes for large files...")

try:
    # Try with error handling for malformed lines
    df = pd.read_csv(
        input_file, 
        compression='gzip' if input_file.endswith('.gz') else None,
        dtype=str,  # Read all as strings
        on_bad_lines='skip',  # Skip malformed lines
        encoding='utf-8',
        low_memory=False
    )
    print(f"✅ Loaded: {len(df):,} rows, {len(df.columns)} columns")
except Exception as e:
    print(f"❌ Error loading with skip mode: {str(e)}")
    print("\n🔄 Trying alternative method with quoted fields...")
    
    # Try with different quoting
    df = pd.read_csv(
        input_file,
        compression='gzip' if input_file.endswith('.gz') else None,
        dtype=str,
        quoting=1,  # QUOTE_ALL
        encoding='utf-8',
        low_memory=False,
        on_bad_lines='warn'
    )
    print(f"✅ Loaded: {len(df):,} rows, {len(df.columns)} columns")

print(f"📊 Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")

# Show unique flows
if 'keyword_term' in df.columns and 'publisher_url' in df.columns:
    unique_flows = df.groupby(['keyword_term', 'publisher_url', 'serp_template_name'], dropna=False).ngroups
    print(f"🔄 Unique flows: {unique_flows:,}")

# Step 2: Analyze data
print("\n" + "="*60)
print("Data Analysis")
print("="*60)

# Check clicks distribution
if 'clicks' in df.columns:
    df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce').fillna(0)
    zero_clicks = len(df[df['clicks'] == 0])
    print(f"Rows with 0 clicks: {zero_clicks:,} ({zero_clicks/len(df)*100:.1f}%)")

# Check column sizes
print("\n📦 Column sizes:")
col_sizes = []
for col in df.columns:
    size_mb = df[col].memory_usage(deep=True) / 1024**2
    col_sizes.append((col, size_mb))
col_sizes.sort(key=lambda x: x[1], reverse=True)

for col, size_mb in col_sizes[:10]:
    print(f"  {col}: {size_mb:.1f} MB")

# Step 3: Filtering
print("\n" + "="*60)
print("Filtering Strategy")
print("="*60)
print("\nApplying filters:")

original_rows = len(df)

# Filter 1: Remove rows with 0 clicks
print("1️⃣ Removing rows with 0 clicks...")
df = df[df['clicks'] > 0]
print(f"   Kept: {len(df):,} rows ({len(df)/original_rows*100:.1f}%)")

# Filter 2: Keep top N recent views per unique flow
print("2️⃣ Keeping 5 most recent views per unique flow...")
df = df.groupby([
    'keyword_term', 'publisher_url', 'serp_template_name'
], dropna=False).apply(lambda x: x.nlargest(min(5, len(x)), 'ts')).reset_index(drop=True)
print(f"   Kept: {len(df):,} rows ({len(df)/original_rows*100:.1f}%)")

# Filter 3: Drop unused ID columns
print("3️⃣ Dropping unused ID columns...")
cols_to_drop = ['advertiser_id', 'campaign_id', 'ad_id', 
                'creative_id', 'creative_template_key', 
                'serp_template_id', 'serp_template_key']
existing_to_drop = [col for col in cols_to_drop if col in df.columns]
if existing_to_drop:
    df = df.drop(columns=existing_to_drop)
    print(f"   Dropped: {', '.join(existing_to_drop)}")

# Step 4: Save
print("\n" + "="*60)
print("Saving Optimized Data")
print("="*60)

# Auto-generate output filename
base_name = os.path.splitext(input_file)[0]  # Remove .gz
if base_name.endswith('.csv'):
    base_name = os.path.splitext(base_name)[0]  # Remove .csv
output_file = f"{base_name}_optimized.csv.gz"

print(f"💾 Saving to {output_file}...")
df.to_csv(output_file, compression='gzip', index=False)

# Show results
input_size = os.path.getsize(input_file) / 1024**2
output_size = os.path.getsize(output_file) / 1024**2

print("\n" + "="*60)
print("✅ SUCCESS!")
print("="*60)
print(f"Original file: {input_size:.1f} MB, {original_rows:,} rows")
print(f"Optimized file: {output_size:.1f} MB, {len(df):,} rows")
print(f"Reduction: {input_size/output_size:.1f}x smaller")
print(f"Rows kept: {len(df)/original_rows*100:.1f}%")
print(f"\n{'✅ Under 200MB! Ready for Streamlit!' if output_size < 200 else '⚠️ Still over 200MB - need more filtering'}")
print(f"\n📂 Upload this file: {output_file}")
print("="*60)
