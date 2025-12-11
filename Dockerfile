FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

COPY .env ./

CMD ["python", "reminder_bot.py"]
