FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY ml/ ./ml/

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend:/app/ml
ENV DATABASE_URL=postgresql+asyncpg://recoverai:recoverai@postgres:5432/recoverai
ENV REDIS_URL=redis://redis:6379/0
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
