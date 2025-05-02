#!/bin/bash
set -e

echo "Starting Scanly container..."
echo "============================"

# Configure environment if needed
if [ ! -f /app/.env ] && [ -f /app/.env.template ]; then
    echo "Creating default .env file from template..."
    cp /app/.env.template /app/.env
fi

# Make sure permissions are properly set
chmod +x /app/src/main.py
chmod +x /app/src/create_data_dirs.py

# Ensure the script runs in the foreground and with immediate output
cd /app
echo "Starting Scanly interactive console..."
exec python -u src/main.py