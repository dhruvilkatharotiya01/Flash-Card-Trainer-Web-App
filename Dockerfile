FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FLASHCARDS_DATA=/app/instance/flashcards.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flashcards ./flashcards
COPY data ./data
COPY app.py .

RUN useradd --create-home --uid 1000 app && mkdir -p instance && chown app instance
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "app:app"]
