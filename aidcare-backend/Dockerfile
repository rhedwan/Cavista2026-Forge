# Dockerfile
FROM python:3.11-slim-bullseye

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --- System Dependencies ---
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libboost-all-dev \
    libssl-dev \
    libffi-dev \
    python3-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    git \
    # apt-get install tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# --- Python Dependencies ---
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# --- App Source ---
COPY . .

# --- Explicitly ensure FAISS knowledge bases are present ---
COPY data/kb_chw/ ./data/kb_chw/
COPY data/kb_clinical/ ./data/kb_clinical/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
