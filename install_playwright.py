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
    
    browsers_exist = False
    for browser_path in browser_paths:
        if browser_path.exists() and list(browser_path.glob("chromium*")):
            print(f"✅ Playwright browsers already installed at: {browser_path}")
            browsers_exist = True
            break
    
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
