FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p data/pages uploads

EXPOSE 10000

CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2
