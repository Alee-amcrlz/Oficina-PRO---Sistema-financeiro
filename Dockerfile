FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV APP_ENV=local
ENV HOST=0.0.0.0
ENV PORT=4173

EXPOSE 4173

CMD ["sh", "-c", "python scripts/preflight.py && python scripts/validate_migrations.py && python scripts/apply_migrations.py && exec python server.py"]
