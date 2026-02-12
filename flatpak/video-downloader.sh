#!/bin/bash

export PYTHONPATH=/app/lib/python3.13/site-packages:/app/lib/python3.12/site-packages:/app/lib/python3.11/site-packages:$PYTHONPATH

# System Qt6 Libraries
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/app/lib:$LD_LIBRARY_PATH

export QT_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt6/plugins:/app/lib/qt6/plugins:$QT_PLUGIN_PATH

export QML2_IMPORT_PATH=/usr/lib/x86_64-linux-gnu/qt6/qml:$QML2_IMPORT_PATH

exec python3 /app/bin/main.py "$@"
