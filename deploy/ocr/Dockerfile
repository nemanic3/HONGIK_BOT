FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir paddlepaddle==3.2.2 paddleocr==3.3.2 paddlex==3.3.13
WORKDIR /app
COPY backend/requirements.txt backend/requirements-ocr.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ocr.txt
COPY backend/ ./
ENV PYTHONDONTWRITEBYTECODE=1 PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
