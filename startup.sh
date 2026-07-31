#!/bin/sh
set -eu
# Start the FastAPI app with Gunicorn and Uvicorn workers.
exec gunicorn \
  -w "${WEB_CONCURRENCY:-2}" \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  backend.app.main:app
