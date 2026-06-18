FROM python:3.11-slim

WORKDIR /app

# libgomp1: OpenMP runtime required by lightgbm's native lib (the [ml] surrogate
# forecast). python:3.11-slim omits it, so without this lightgbm import fails with
# "libgomp.so.1: cannot open shared object file" and the surrogate silently falls
# back to heuristics.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend/greenflow ./backend/greenflow
# CPU-only torch FIRST, from PyTorch's CPU index, so sentence-transformers below
# doesn't pull the ~2GB CUDA build. Keeps the image lean; BGE-M3 + reranker run
# on CPU anyway.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# [ml] = lightgbm + numpy + pandas (EnergyPlus-DoE surrogate: demand_forecast
# pre-cool + what-if action scoring). [embeddings] = sentence-transformers for
# BGE-M3 dense embeddings + bge-reranker-v2-m3 cross-encoder (hybrid RAG).
RUN pip install --no-cache-dir -e ".[ml,embeddings]"

COPY scripts ./scripts
COPY db ./db

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "greenflow.api.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
