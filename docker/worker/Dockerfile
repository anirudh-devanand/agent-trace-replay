FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y --no-install-recommends \
    librdkafka1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src/
RUN pip install --no-cache-dir .

COPY docker/entrypoint-worker.sh ./entrypoint-worker.sh
RUN sed -i 's/\r$//' ./entrypoint-worker.sh && chmod +x ./entrypoint-worker.sh

EXPOSE 8002

ENTRYPOINT ["./entrypoint-worker.sh"]
