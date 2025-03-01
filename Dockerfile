FROM python:3.9-slim-bookworm
WORKDIR /app

# Install gosu and docker.io (Docker CLI)
RUN apt-get update && apt-get install -y \
    gosu \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]