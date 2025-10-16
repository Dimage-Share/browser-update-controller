FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data dir
RUN mkdir -p /app/data

EXPOSE 6001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6001"]
