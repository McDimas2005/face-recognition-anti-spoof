FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_ENV=production
ENV API_STORAGE_PATH=/tmp/face-attendance
ENV API_RETAIN_ENROLLMENT_IMAGES=false
ENV API_RETAIN_REVIEW_IMAGES=false
ENV PORT=7860

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/alembic.ini /app/alembic.ini
COPY apps/api/alembic /app/alembic
COPY apps/api/app /app/app
COPY legacy/DNN /app/legacy/DNN
COPY deploy/huggingface/start-api.sh /app/start-api.sh

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && chmod +x /app/start-api.sh

CMD ["/app/start-api.sh"]
