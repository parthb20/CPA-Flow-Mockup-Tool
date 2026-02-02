#!/bin/bash
# Streamlit Cloud setup script - installs Playwright browsers

echo "Installing Playwright chromium browser..."
python -m playwright install chromium --with-deps

echo "Playwright installation complete!"
echo "Browser installed to: $(python -m playwright install chromium --dry-run 2>&1 | grep -o '/.*' || echo 'default location')"
