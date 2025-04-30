# Base image
FROM python:3.12-slim

# Create non-root user
RUN useradd -m -u 1000 user

USER user

# Set home to the user's home directory
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Try and run pip command after setting the user with `USER user` to avoid permission issues with Python
RUN pip install --no-cache-dir --upgrade pip

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user . $HOME/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg cmake libsndfile1 git curl build-essential libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*


RUN mkdir -p $HOME/app/staticfiles

# Copy requirements and install Python packages as user
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Start Gunicorn on port 7860 (required by Hugging Face)
CMD ["gunicorn", "--log-level", "debug", "--bind", "0.0.0.0:7860", "workflow.wsgi:application"]
