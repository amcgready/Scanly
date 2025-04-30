#!/bin/bash
set -e

# Print startup message
echo "Starting Scanly container..."
echo "============================"

# Configure environment if needed
if [ ! -f /app/.env ] && [ -f /app/.env.template ]; then
    echo "Creating default .env file from template..."
    cp /app/.env.template /app/.env
fi

# Always run main.py directly
echo "Starting Scanly..."
cd /app
exec python -u src/main.py