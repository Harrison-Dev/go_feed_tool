# Lightweight Python image for inference
# Build from ml/ directory: docker build -f inference/Dockerfile -t predict-service .
FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY inference/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory structure
RUN mkdir -p /app/training /app/models

# Copy feature engineering module (needed for FEATURE_NAMES)
COPY training/feature_engineering.py /app/training/feature_engineering.py
RUN touch /app/training/__init__.py

# Copy application code
COPY inference/predict_service.py .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run service
CMD ["uvicorn", "predict_service:app", "--host", "0.0.0.0", "--port", "5000"]
