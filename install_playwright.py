#!/usr/bin/env python3
"""
Playwright installation script for Streamlit Cloud
This runs automatically when the app starts
"""
import subprocess
import sys
import os
from pathlib import Path

def install_playwright_browsers():
    """Install Playwright chromium browser if not already installed"""
    
    # Check if browsers are already installed
    browser_paths = [
        Path.home() / ".cache" / "ms-playwright",
        Path("/home/appuser/.cache/ms-playwright"),
    ]
    
    print(f"🔍 Checking for existing Playwright browsers...")
    print(f"   Home directory: {Path.home()}")
    print(f"   User: {os.environ.get('USER', 'unknown')}")
    
    browsers_exist = False
    for browser_path in browser_paths:
        print(f"   Checking: {browser_path}")
        if browser_path.exists():
            print(f"     ✅ Path exists")
            chromium_dirs = list(browser_path.glob("chromium*"))
            if chromium_dirs:
                print(f"     ✅ Playwright browsers already installed at: {browser_path}")
                browsers_exist = True
                break
            else:
                print(f"     ⚠️ Path exists but no chromium found")
        else:
            print(f"     ❌ Path doesn't exist")
    
    if not browsers_exist:
        print("=" * 50)
        print("Installing Playwright Browsers")
        print("=" * 50)
        
        try:
            # Ensure playwright is installed
            print("Ensuring playwright package is installed...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "playwright"])
            
            # Install chromium browser
            print("Installing chromium browser...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print("✅ Playwright installation completed successfully!")
                print(result.stdout)
                
                # Verify installation
                for browser_path in browser_paths:
                    if browser_path.exists() and list(browser_path.glob("chromium*")):
                        print(f"✅ Browsers found at: {browser_path}")
                        return True
            else:
                print(f"❌ Installation failed with return code: {result.returncode}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Installation timed out after 5 minutes")
            return False
        except Exception as e:
            print(f"❌ Installation error: {str(e)}")
            return False
    
    return True

if __name__ == "__main__":
    success = install_playwright_browsers()
    sys.exit(0 if success else 1)
