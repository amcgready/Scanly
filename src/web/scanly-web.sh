#!/bin/bash
# Start the Scanly web interface

# Change to the project directory
cd "$(dirname "$0")"

# Check if Python is available
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check for required packages
echo "Checking for required packages..."
$PYTHON_CMD -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing Flask..."
    pip install flask
fi

# Start the web server
echo "Starting Scanly Web Interface..."
$PYTHON_CMD src/web/app.py

# If the server stops, wait for user input before closing
echo "Web server has stopped."
echo "Press Enter to exit..."
read