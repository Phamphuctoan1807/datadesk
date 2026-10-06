FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN g++ -O2 -std=c++17 -shared -fPIC -o libddengine.so engine.cpp
ENV COOKIE_SECURE=1 PYTHONUNBUFFERED=1
CMD gunicorn -w 1 --threads 8 --timeout 90 -b 0.0.0.0:${PORT:-10000} server:app
