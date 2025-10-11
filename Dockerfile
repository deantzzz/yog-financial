FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY infra ./infra
COPY workspaces ./workspaces
COPY logs ./logs

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
