FROM python:3.11-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt
RUN useradd --create-home --uid 10001 hongik && mkdir /state && chown hongik:hongik /state
COPY --chown=hongik:hongik backend/ ./
USER hongik
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--max-requests", "1000", "--max-requests-jitter", "100", "--error-logfile", "-"]

FROM api AS worker
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir paddlepaddle==3.2.2 paddleocr==3.3.2 paddlex==3.3.13
RUN mkdir -p /home/hongik/.paddlex /home/hongik/.cache && chown -R hongik:hongik /home/hongik/.paddlex /home/hongik/.cache
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True OCR_CPU_THREADS=2
USER hongik
CMD ["celery", "-A", "core", "worker", "--concurrency=1", "--loglevel=WARNING", "--without-gossip", "--without-mingle", "--without-heartbeat"]
