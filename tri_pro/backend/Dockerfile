FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 (psycopg2 빌드용 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render 등은 PORT 환경변수를 주입함
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w 2 --bind 0.0.0.0:${PORT} --timeout 120 main:app"]
