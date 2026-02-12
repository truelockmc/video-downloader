#!/bin/bash
# Set up environment for PyQt6
export LD_LIBRARY_PATH=/app/lib:/app/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
export QT_QPA_PLATFORM_PLUGIN_PATH=/app/lib/python3.11/site-packages/PyQt6/Qt6/plugins
export QT_PLUGIN_PATH=/app/lib/python3.11/site-packages/PyQt6/Qt6/plugins
export PYTHONPATH=/app/lib/python3.11/site-packages:/app/bin:$PYTHONPATH

exec python3 /app/bin/main.py "$@"
