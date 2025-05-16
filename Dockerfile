# Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    python3-dev \
    musl-dev \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy app code
COPY . /app/

# Expose the port Gunicorn listens on
EXPOSE 8000

# Start Gunicorn with Uvicorn workers
CMD ["gunicorn", "--config", "gunicorn_config.py", "com.mhire.app.main:app"]