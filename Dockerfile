FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/en_core_web_sm-3.8.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/en_core_web_sm-3.8.0-py3-none-any.whl \
    && rm /tmp/en_core_web_sm-3.8.0-py3-none-any.whl

COPY backend/ backend/
COPY prefect/ prefect/
COPY frontend/ frontend/
COPY data/ data/
COPY ontology/ ontology/

ENV SEMANTICA_DISABLE_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/prefect:/app

CMD ["python", "-m", "backend.api"]
