#!/bin/bash
# Streamlit Cloud setup script - installs Playwright browsers

echo "Installing Playwright chromium browser..."
playwright install chromium --with-deps

echo "Playwright installation complete!"
