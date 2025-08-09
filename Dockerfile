### STAGE 1: frontend builder ###
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# only copy package files first for caching
COPY frontend/package*.json ./
RUN npm ci

# now copy rest and build
COPY frontend/ ./
RUN npm run build        # produces ./dist/

### STAGE 2: final image (micromamba) ###
FROM mambaorg/micromamba:1.5.8 as runtime
# Create env
WORKDIR /app
COPY --chown=micromamba:micromamba environment.yml /tmp/environment.yml
RUN micromamba create -y -n tgt -f /tmp/environment.yml \
 && micromamba clean --all --yes

# Make the env default for RUN/CMD
SHELL ["/usr/local/bin/_entrypoint.sh", "micromamba", "run", "-n", "tgt", "/bin/bash", "-lc"]

# Copy backend code
COPY --chown=micromamba:micromamba backend/ /app/backend/

# Copy built frontend assets from builder
COPY --from=frontend-builder --chown=micromamba:micromamba /app/frontend/dist /app/frontend/dist

# Route caches to a writable mount so models aren't baked into layers
ENV HF_HOME=/cache/hf \
    HF_HUB_CACHE=/cache/hf \
    TRANSFORMERS_CACHE=/cache/hf \
    XDG_CACHE_HOME=/cache \
    WHISPER_CACHE_DIR=/cache/whisper

WORKDIR /app/backend
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "micromamba", "run", "-n", "tgt"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
