### STAGE 1: frontend builder ###
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

### STAGE 2: runtime ###
FROM mambaorg/micromamba:1.5.8 AS runtime
WORKDIR /app
USER root

# default non-root user in this image is mambauser
ENV MAMBA_USER=mambauser

# env first for caching
COPY --chown=${MAMBA_USER}:${MAMBA_USER} environment.yml /tmp/environment.yml
RUN micromamba create -y -n tgt -f /tmp/environment.yml \
 && micromamba clean --all --yes

# writable dirs
RUN install -d -m 0775 -o ${MAMBA_USER} -g ${MAMBA_USER} /app/backend/training/data /app/backend/models

# app code
COPY --chown=${MAMBA_USER}:${MAMBA_USER} backend/ /app/backend/
# use stage INDEX to avoid name resolution issues
COPY --from=0 --chown=${MAMBA_USER}:${MAMBA_USER} /app/frontend/dist /app/frontend/dist

# ensure group-write
RUN chown -R ${MAMBA_USER}:${MAMBA_USER} /app && chmod -R g+rwX /app

WORKDIR /app/backend
USER ${MAMBA_USER}

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "micromamba", "run", "-n", "tgt"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
