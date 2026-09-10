FROM python:3.11-slim

# Tesseract engine + Arabic and English language data.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 app:app"]

