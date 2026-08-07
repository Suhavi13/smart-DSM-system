# Package recommendation-service as an independently runnable FastAPI container.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install only this service's dependencies so every image has its own lifecycle.
COPY services/recommendation-service/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt

# Preserve the Stage 1/2 folder depth because service bootstrapping discovers
# the project root from /app/services/<service>/app/main.py.
COPY services/__init__.py /app/services/__init__.py
COPY services/shared /app/services/shared
COPY services/recommendation-service/app /app/services/recommendation-service/app

WORKDIR /app/services/recommendation-service

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
