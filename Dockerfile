FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including net-tools for health checks and tzdata for timezone support
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    curl \
    wget \
    nano \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install required packages from the root requirements file
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Create necessary directories
# Log files are now stored in database only
RUN mkdir -p /config && chmod -R 755 /config

# Set environment variables
ENV PYTHONPATH=/app
ENV TZ=UTC
ENV LOG_LEVEL=INFO
# ENV APP_TYPE=sonarr # APP_TYPE is likely managed via config now, remove if not needed

# Expose port
EXPOSE 9705

# Add health check for Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9705/health || exit 1

# Run the main application using the new entry point
CMD ["python3", "main.py"]