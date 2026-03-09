FROM python:3.10-slim

# Install system deps: tesseract + Hindi + Marathi language packs
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libsm6 \
    libxrender1 \
    libxext6 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies FIRST (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway injects PORT env var
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
