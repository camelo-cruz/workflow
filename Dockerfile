### STAGE 1: frontend builder ###
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# only copy package files first for caching
COPY frontend/package*.json ./
RUN npm ci

# now copy rest and build
COPY frontend/ ./
RUN npm run build        # produces ./dist/


### STAGE 2: final image ###
FROM continuumio/miniconda3:latest
WORKDIR /app

# 1) Install conda environment
COPY environment.yml ./
RUN conda env create -f environment.yml && \
    conda clean -afy

# 2) Make conda env the default for all RUN/ENTRYPOINT/CMD
SHELL ["conda", "run", "-n", "tgt", "/bin/bash", "-c"]

# 3) Copy in backend code
COPY backend/ ./backend/

# 4) Copy built frontend assets
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 5) Expose and run
WORKDIR /app/backend
EXPOSE 8000

# ENTRYPOINT will prefix every invocation with `conda run -n tgt`
ENTRYPOINT ["conda", "run", "-n", "tgt"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
