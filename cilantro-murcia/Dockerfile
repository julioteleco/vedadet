FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# DATABASE_URL, ANTHROPIC_API_KEY, SIAR_API_KEY, AEMET_API_KEY, FCM_CREDENTIALS
# se inyectan por entorno (ver docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
