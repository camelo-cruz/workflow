FROM continuumio/miniconda3:latest

# Set working directory to /app
WORKDIR /app

# Copy only environment.yml first (better caching for rebuilds)
COPY environment.yml .

# Create the conda environment
RUN conda env create -f environment.yml && \
    conda clean -afy

# Make RUN commands use the new environment
SHELL ["conda", "run", "-n", "tgt", "/bin/bash", "-c"]

# Copy all source code (backend + frontend/dist)
COPY . .

# Change working directory to backend so uvicorn runs from there
WORKDIR /app/backend

# Expose API port
EXPOSE 8000

# Run FastAPI app with Uvicorn
CMD ["conda", "run", "-n", "tgt", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]