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
    PATH=/home/user/.local/bin:$PATH

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

# (Optional) tell Docker the app listens on 80
EXPOSE 80
# Run Django dev server on port 80
CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]
