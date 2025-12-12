# monitor/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# ensure CA certs for any outbound calls
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

COPY monitor/ .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5002
CMD ["python", "app.py"]
