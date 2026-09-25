# ==============================================================================
# IBVAP AI Engine - Multi-Stream Supervisor & Inference Dockerfile
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install native multimedia and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU and vision / AI requirements
COPY ai_engine/docker_requirements.txt /app/ai_engine/docker_requirements.txt
RUN pip install --no-cache-dir -r /app/ai_engine/docker_requirements.txt

# Copy backend module (for AlertEngine schemas and Redis event bus models)
COPY backend/ /app/backend/

# Copy AI Engine source code and pre-baked local model weights
COPY ai_engine/ /app/ai_engine/

# Copy mock streams, face galleries, and spatial rules
COPY mock_streams/ /app/mock_streams/

# Ensure default output storage directory exists
RUN mkdir -p /app/storage /app/recordings

# Launch StreamManager supervisor over configured streams
CMD ["python", "-m", "ai_engine.stream_manager", "--config", "mock_streams/streams.json"]
