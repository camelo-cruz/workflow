# Base image
FROM python:3.12

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg cmake libsndfile1 git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies early
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Now copy the entire Django project
COPY . .

# Collect static files (optional)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Start Gunicorn server
CMD ["gunicorn", "workflow.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "3600", "--workers", "1"]