# MiniKV Dockerfile
# Multi-stage build for optimized image size

# Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY core/ ./core/
COPY server/ ./server/
COPY client/ ./client/
COPY benchmarks/ ./benchmarks/
COPY tests/ ./tests/
COPY example.py .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Create volume for persistent data
VOLUME ["/app/data"]

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MINIKV_DB_PATH=/app/data/minikv.db
ENV MINIKV_WAL_PATH=/app/data/minikv.wal

# Expose port for future API (optional)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "from server.router import Router; r = Router(enable_persistence=False, enable_wal=False); r.start(); r.set('health', 'ok'); assert r.get('health') == 'ok'; r.stop()" || exit 1

# Default command: run CLI
CMD ["python3", "-m", "client.cli"]

