### STAGE 1: frontend builder ###
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# Install ALL deps (incl. dev) for the build
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
# If you have native deps, uncomment the apk line above this RUN (see Option B)
RUN npm run build \
 && rm -rf node_modules \
 && npm cache clean --force


### STAGE 2: runtime ###
FROM mambaorg/micromamba:1.5.8 AS runtime
WORKDIR /app
USER root

# default non-root user in this image is mambauser
ENV MAMBA_USER=mambauser

# Keep pip from caching; reduces layer size
ENV PIP_NO_CACHE_DIR=1

# Create env first for caching, then clean conda+pip caches
COPY --chown=${MAMBA_USER}:${MAMBA_USER} environment.yml /tmp/environment.yml
RUN micromamba create -y -n tgt -f /tmp/environment.yml \
 && micromamba run -n tgt pip cache purge || true \
 && micromamba clean --all --yes \
 && chown -R ${MAMBA_USER}:${MAMBA_USER} /opt/conda/envs/tgt   # <-- make site-packages writable

# Writable dirs used at runtime
RUN install -d -m 0775 -o ${MAMBA_USER} -g ${MAMBA_USER} \
      /app/backend/training/data \
      /app/backend/models

# App code
COPY --chown=${MAMBA_USER}:${MAMBA_USER} backend/ /app/backend/
# Bring in built frontend assets from the builder stage
COPY --from=frontend-builder --chown=${MAMBA_USER}:${MAMBA_USER} /app/frontend/dist /app/frontend/dist

# Ensure group-write
RUN chown -R ${MAMBA_USER}:${MAMBA_USER} /app && chmod -R g+rwX /app

WORKDIR /app/backend
USER ${MAMBA_USER}

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "micromamba", "run", "-n", "tgt"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
