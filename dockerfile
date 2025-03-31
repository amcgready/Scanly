FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create a non-root user to run the application
RUN groupadd -r scanly && \
    useradd -r -g scanly scanly && \
    mkdir -p /app/logs /media/source /media/library && \
    chown -R scanly:scanly /app /media/source /media/library

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Change ownership of all files to the scanly user
RUN chown -R scanly:scanly /app

# Switch to non-root user
USER scanly

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["python", "src/main.py"]