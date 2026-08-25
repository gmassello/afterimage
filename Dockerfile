FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

ENV AFTERIMAGE_WEIGHTS_DIR=/opt/models
COPY models/ /opt/models/
COPY services/ services/
