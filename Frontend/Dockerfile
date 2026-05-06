FROM python:3.11-slim

WORKDIR /api

# System deps required by MediaPipe on Linux (inside Docker)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-create models directory so the auto-download has somewhere to write
RUN mkdir -p /api/models

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]