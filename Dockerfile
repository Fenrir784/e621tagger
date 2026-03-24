FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p models data

COPY models/ ./models/
COPY data/ ./data/
# Replace copy with ADD if building locally
#ADD https://huggingface.co/RedRocket/JTP-3/resolve/main/models/jtp-3-hydra.safetensors models/jtp-3-hydra.safetensors
#ADD https://huggingface.co/RedRocket/JTP-3/resolve/main/data/jtp-3-hydra-tags.csv data/jtp-3-hydra-tags.csv

COPY *.py ./
ARG APP_VERSION=test
COPY templates/ ./templates/
COPY static/ ./static/

RUN sed -i "s/{{APP_VERSION}}/${APP_VERSION}/g" templates/index.html static/service-worker.js

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
