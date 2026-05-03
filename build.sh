#!/bin/bash
set -e
cd "$(dirname "$0")"
.venv/bin/pyinstaller PluginCleaner.spec --noconfirm
rm -rf "dist/Plugin Cleaner"
echo "Built: dist/Plugin Cleaner.app"
