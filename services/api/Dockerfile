FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY services/api/pyproject.toml ./
COPY services/api/app ./app
COPY data ./data
COPY eval/report.json eval/labels.json eval/labels.sha256 ./eval/

RUN pip install --no-cache-dir .

EXPOSE 8000

# Hosting platforms pass the port in $PORT; default 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
