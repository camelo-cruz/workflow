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

# Set working directory and switch user
WORKDIR /app
USER user

# Copy and install requirements
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# Copy the rest of the project
COPY --chown=user . .

# Collect static files (optional)
RUN python manage.py collectstatic --noinput || true

# Start Gunicorn server on port 7860 (required by Hugging Face Spaces)
CMD ["gunicorn", "workflow.wsgi:application", "--bind", "0.0.0.0:7860", "--timeout", "3600", "--workers", "1"]