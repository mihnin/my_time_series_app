# --- CUDA PROD DOCKERFILE ---
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

RUN apt-get update && \
    apt-get install -y python3.10 python3.10-venv python3.10-distutils python3-pip && \
    ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]