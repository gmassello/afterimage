FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.lock ./
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps -r requirements.lock
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1@sha256:46d6625e68cbbdd2efab4a20245977664513f13ffef47915b000d431adcea0b4 /lambda-adapter /opt/extensions/lambda-adapter

ENV AFTERIMAGE_WEIGHTS_DIR=/opt/models
COPY models/ /opt/models/
COPY services/ services/

CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
