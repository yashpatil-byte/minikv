# MiniKV Dockerfile
# Optimized single-stage build

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
# Note: requirements.txt is minimal (only comments), so this is fast
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy application code
COPY core/ ./core/
COPY server/ ./server/
COPY client/ ./client/
COPY benchmarks/ ./benchmarks/
COPY tests/ ./tests/
COPY example.py .

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

