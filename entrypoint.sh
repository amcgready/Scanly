#!/bin/bash
set -e

# Create .env file if it doesn't exist
if [ ! -f /app/.env ]; then
    echo "Creating default .env file..."
    cp /app/.env.example /app/.env
    
    # Set ORIGIN_DIRECTORY and DESTINATION_DIRECTORY to Docker volume mounts
    sed -i 's|ORIGIN_DIRECTORY=.*|ORIGIN_DIRECTORY=/media/source|g' /app/.env
    sed -i 's|DESTINATION_DIRECTORY=.*|DESTINATION_DIRECTORY=/media/library|g' /app/.env
    
    echo "Please set your TMDB_API_KEY in the .env file"
fi

# Check if TMDB_API_KEY is set
if grep -q "TMDB_API_KEY=your_tmdb_api_key_here" /app/.env; then
    echo "WARNING: TMDB_API_KEY is not set. Please set it in the .env file or provide it as an environment variable."
fi

# Override environment variables from Docker if provided
if [ ! -z "$TMDB_API_KEY" ]; then
    sed -i "s|TMDB_API_KEY=.*|TMDB_API_KEY=$TMDB_API_KEY|g" /app/.env
fi

if [ ! -z "$ORIGIN_DIRECTORY" ]; then
    sed -i "s|ORIGIN_DIRECTORY=.*|ORIGIN_DIRECTORY=$ORIGIN_DIRECTORY|g" /app/.env
fi

if [ ! -z "$DESTINATION_DIRECTORY" ]; then
    sed -i "s|DESTINATION_DIRECTORY=.*|DESTINATION_DIRECTORY=$DESTINATION_DIRECTORY|g" /app/.env
fi

if [ ! -z "$LOG_LEVEL" ]; then
    sed -i "s|LOG_LEVEL=.*|LOG_LEVEL=$LOG_LEVEL|g" /app/.env
fi

if [ ! -z "$AUTO_EXTRACT_EPISODES" ]; then
    sed -i "s|AUTO_EXTRACT_EPISODES=.*|AUTO_EXTRACT_EPISODES=$AUTO_EXTRACT_EPISODES|g" /app/.env
fi

if [ ! -z "$LINK_TYPE" ]; then
    sed -i "s|LINK_TYPE=.*|LINK_TYPE=$LINK_TYPE|g" /app/.env
fi

# Run the provided command
exec "$@"