#!/bin/bash

# Optional: Add any setup or pre-start commands here
echo "Started DoHome Addon"
# Start your addon's main service or script as the main process
exec python3 /src/__init__.py
