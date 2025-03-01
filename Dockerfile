FROM python:3.9-slim-buster
WORKDIR /app
RUN retry_apt_update() { \
    apt-get update && apt-get install -y su-exec && return 0; \
    sleep 5; \
    apt-get update && apt-get install -y su-exec && return 0; \
    sleep 10; \
    apt-get update && apt-get install -y su-exec && return 0; \
    return 1; \
}; retry_apt_update || exit 1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]