#!/bin/bash
export LD_LIBRARY_PATH=/app/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/app/lib/python3.11/site-packages:$PYTHONPATH
exec python3 /app/bin/main.py "$@"
