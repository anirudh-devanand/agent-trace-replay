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
COPY alembic.ini ./
COPY alembic ./alembic/
RUN pip install --no-cache-dir .

COPY docker/entrypoint-api.sh ./entrypoint-api.sh
RUN sed -i 's/\r$//' ./entrypoint-api.sh && chmod +x ./entrypoint-api.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint-api.sh"]
