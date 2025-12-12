FROM python:3.11-slim

WORKDIR /app

# Copy shared protocol
COPY common ./common
COPY ground-station/ .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5003
CMD ["python", "ground.py"]
