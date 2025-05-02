# Base image
FROM python:3.12-slim

#––– Install system dependencies as root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ffmpeg cmake libsndfile1 git curl build-essential libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

#––– Create a non-root user
RUN useradd -m -u 1000 user

#––– Switch to that user
USER user

#––– Set home & PATH
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

#––– Work directory
WORKDIR $HOME/app

#––– Upgrade pip as non-root
RUN pip install --no-cache-dir --upgrade pip

#––– Copy your code in, owned by `user`
COPY --chown=user . $HOME/app

#––– Install Python deps
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --user -r requirements.txt

#––– Collect static files
RUN python manage.py collectstatic --noinput || true

# Expose the port Hugging Face expects
EXPOSE 7860

# Start Django on port 7860 with unbuffered output
CMD ["workflow.asgi:application", "--host", "0.0.0.0", "--port", "7860", "--lifespan", "off"]
