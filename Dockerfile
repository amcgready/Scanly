FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install any needed packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /media/source /media/library && \
    chmod -R 777 /app/logs

# Copy the docker-entrypoint.sh script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create the actual entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Create .env file if it does not exist\n\
if [ ! -f /app/.env ]; then\n\
    echo "Creating default .env file..."\n\
    cp /app/.env.template /app/.env\n\
    \n\
    # Set ORIGIN_DIRECTORY and DESTINATION_DIRECTORY to Docker volume mounts\n\
    sed -i "s|DESTINATION_DIRECTORY=.*|DESTINATION_DIRECTORY=/media/library|g" /app/.env\n\
    \n\
    echo "Please set your TMDB_API_KEY in the .env file"\n\
fi\n\
\n\
# Override environment variables from Docker if provided\n\
if [ ! -z "$TMDB_API_KEY" ]; then\n\
    sed -i "s|TMDB_API_KEY=.*|TMDB_API_KEY=$TMDB_API_KEY|g" /app/.env\n\
fi\n\
\n\
if [ ! -z "$DESTINATION_DIRECTORY" ]; then\n\
    sed -i "s|DESTINATION_DIRECTORY=.*|DESTINATION_DIRECTORY=$DESTINATION_DIRECTORY|g" /app/.env\n\
fi\n\
\n\
# Run the provided command\n\
exec "$@"\n\
' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Set the wrapper script as the entry point
ENTRYPOINT ["/app/docker-entrypoint.sh"]