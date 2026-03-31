FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000 \
    FLASK_DEBUG=0

WORKDIR /app

COPY requirements.txt ./

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY app.py db.py README.md api_guide.md ./
COPY static ./static
COPY templates ./templates

EXPOSE 5000

CMD ["python", "app.py"]
