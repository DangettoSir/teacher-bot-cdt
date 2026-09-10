FROM python:3.13-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY run_tests.py .

RUN mkdir -p /app/data

CMD ["sh", "-c", "python run_tests.py && python -m app.main"]