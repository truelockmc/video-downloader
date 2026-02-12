#!/bin/bash
# Ensure Python can find the BaseApp packages
export PYTHONPATH=/app/lib/python3.11/site-packages:$PYTHONPATH

exec python3 /app/bin/main.py "$@"
