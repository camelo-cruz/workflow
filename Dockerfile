# Base image
FROM python:3.12-slim

# Create non-root user
RUN useradd -m -u 1000 user

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/user/.local/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg cmake libsndfile1 git curl build-essential libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files as root first
COPY . .

# Create staticfiles dir and fix permissions before switching user
RUN mkdir -p /app/staticfiles && chown -R 1000:1000 /app

# Switch to non-root user
USER user

# Copy requirements and install Python packages as user
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Start Gunicorn on port 7860 (required by Hugging Face)
CMD ["gunicorn", "workflow.wsgi:application", "--bind", "0.0.0.0:7860", "--timeout", "3600", "--workers", "1"]