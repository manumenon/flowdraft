FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies: FFmpeg and library requirements for chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Install playwright python package and browsers
RUN pip install --no-cache-dir playwright==1.61.0
RUN playwright install --with-deps chromium

# Copy backend source and scripts
COPY backend /app/backend
COPY scripts /app/scripts

# Set workdir to backend
WORKDIR /app/backend

# Run the worker script
CMD ["python", "-m", "app.worker"]
