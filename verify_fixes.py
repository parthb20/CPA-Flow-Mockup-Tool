#!/usr/bin/env python3
"""
Verification script to check all fixes are applied correctly
Run this to verify your codebase is ready
"""

import os
import re

print("=" * 60)
print("VERIFYING ALL FIXES ARE APPLIED")
print("=" * 60)

issues_found = []
files_checked = []

# Check for unsafe st.secrets patterns
def check_secrets_access(filepath):
    """Check if file uses safe st.secrets access"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for unsafe patterns
        unsafe_patterns = [
            r'if\s+["\'][^"\']+["\']\s+in\s+st\.secrets',
            r'st\.secrets\.get\(',
        ]
        
        for pattern in unsafe_patterns:
            if re.search(pattern, content):
                return False, f"Unsafe pattern found: {pattern}"
        
        # Check for safe patterns
        safe_patterns = [
            r'st\.secrets\[["\'][^"\']+["\']\]',
            r'except\s+\(KeyError|AttributeError|TypeError\)',
        ]
        
        has_safe = any(re.search(pattern, content) for pattern in safe_patterns)
        has_unsafe = any(re.search(pattern, content) for pattern in unsafe_patterns)
        
        if has_unsafe and not has_safe:
            return False, "Contains unsafe patterns without safe fallback"
        
        return True, "OK"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

# Files to check
files_to_check = [
    'cpa_flow_mockup.py',
    'src/similarity.py',
    'src/screenshot.py',
    'src/renderers.py',
]

print("\n1. Checking st.secrets access patterns...")
for filepath in files_to_check:
    if os.path.exists(filepath):
        is_safe, message = check_secrets_access(filepath)
        status = "[OK]" if is_safe else "[FAIL]"
        print(f"   {status} {filepath}: {message}")
        files_checked.append(filepath)
        if not is_safe:
            issues_found.append(f"{filepath}: {message}")
    else:
        print(f"   [WARN] {filepath}: File not found")

# Check page config order
print("\n2. Checking st.set_page_config() order...")
try:
    with open('cpa_flow_mockup.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    page_config_line = None
    st_calls_before = []
    
    for i, line in enumerate(lines, 1):
        if 'st.set_page_config' in line:
            page_config_line = i
        elif page_config_line is None and re.search(r'st\.(warning|error|info|write|markdown)', line):
            st_calls_before.append((i, line.strip()[:50]))
    
    if page_config_line:
        if st_calls_before:
            print(f"   [FAIL] st.set_page_config() at line {page_config_line}, but Streamlit calls found before:")
            for line_num, line_content in st_calls_before[:3]:
                print(f"      Line {line_num}: {line_content}...")
            issues_found.append("st.set_page_config() not first Streamlit command")
        else:
            print(f"   [OK] st.set_page_config() at line {page_config_line} (first Streamlit command)")
    else:
        print("   [FAIL] st.set_page_config() not found!")
        issues_found.append("st.set_page_config() missing")
except Exception as e:
    print(f"   ❌ Error checking: {str(e)}")
    issues_found.append(f"Error checking page config: {str(e)}")

# Check imports
print("\n3. Checking critical imports...")
critical_imports = [
    'import streamlit as st',
    'from src.config import',
    'from src.data_loader import',
    'from src.utils import',
]

try:
    with open('cpa_flow_mockup.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    for imp in critical_imports:
        if imp in content:
            print(f"   [OK] {imp}")
        else:
            print(f"   [FAIL] Missing: {imp}")
            issues_found.append(f"Missing import: {imp}")
except Exception as e:
    print(f"   [FAIL] Error checking imports: {str(e)}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if issues_found:
    print(f"\n[FAIL] Found {len(issues_found)} issue(s):")
    for issue in issues_found:
        print(f"   - {issue}")
    print("\n[WARN] Please fix these issues before running the app.")
else:
    print("\n[OK] All checks passed! Your codebase looks good.")
    print("\nYou can now run:")
    print("   streamlit run cpa_flow_mockup.py")

print("\n" + "=" * 60)
