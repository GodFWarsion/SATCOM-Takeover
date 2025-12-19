FROM python:3.10-slim

# Install nginx
RUN apt-get update && \
    apt-get install -y nginx curl && \
    rm -rf /var/lib/apt/lists/*

# App directory
WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/shared/support


# App + nginx config
COPY app.py /app/app.py
COPY nginx.conf /etc/nginx/nginx.conf
COPY templates/ /app/templates/


# Expose nginx port
EXPOSE 80

CMD sh -c "nginx -g 'daemon off;' & exec python app.py"


