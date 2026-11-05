FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn z2.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
