#!/bin/bash
set -e  # Exit on error

echo "=================================="
echo "Installing Playwright Browsers"
echo "=================================="

# Ensure pip is up to date
echo "Updating pip..."
python -m pip install --upgrade pip

# Install playwright if not already installed
echo "Ensuring playwright is installed..."
python -m pip install playwright

# Install chromium browser with dependencies
echo "Installing chromium browser..."
python -m playwright install chromium --with-deps

# Verify installation
echo ""
echo "=================================="
echo "Verifying Installation"
echo "=================================="
if python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print('✅ Playwright module loaded'); p.stop()"; then
    echo "✅ Playwright is ready!"
else
    echo "❌ Playwright verification failed"
    exit 1
fi

# Show browser location
echo ""
echo "Browser location:"
ls -la ~/.cache/ms-playwright/ || echo "Browser location not found in ~/.cache/ms-playwright/"
ls -la /home/appuser/.cache/ms-playwright/ 2>/dev/null || echo "(Streamlit Cloud location not checked)"

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
