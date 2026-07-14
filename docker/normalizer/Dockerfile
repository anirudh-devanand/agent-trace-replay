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

COPY docker/entrypoint-normalizer.sh ./entrypoint-normalizer.sh
RUN sed -i 's/\r$//' ./entrypoint-normalizer.sh && chmod +x ./entrypoint-normalizer.sh

EXPOSE 8001

ENTRYPOINT ["./entrypoint-normalizer.sh"]
