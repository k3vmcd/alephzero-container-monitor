FROM python:3.9-slim-buster
WORKDIR /app
RUN apt-get update && apt-get install -y su-exec
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]