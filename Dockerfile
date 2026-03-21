FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN wget -O models/jtp-3-hydra.safetensors \
    https://huggingface.co/RedRocket/JTP-3/resolve/main/models/jtp-3-hydra.safetensors && \
    wget -O data/jtp-3-hydra-tags.csv \
    https://huggingface.co/RedRocket/JTP-3/resolve/main/data/jtp-3-hydra-tags.csv

COPY *.py ./
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
