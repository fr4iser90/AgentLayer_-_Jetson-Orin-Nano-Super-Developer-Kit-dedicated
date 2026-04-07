FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tools ./tools
COPY interfaces ./interfaces
COPY workflows ./workflows
COPY workspace ./workspace

# copy entrypoint script for alembic stamp/upgrade
COPY scripts/alembic_entrypoint.sh /usr/local/bin/alembic_entrypoint.sh
RUN chmod +x /usr/local/bin/alembic_entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/alembic_entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
