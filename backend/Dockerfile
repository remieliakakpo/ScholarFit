FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 scholarfit && chown -R scholarfit /app
USER scholarfit
EXPOSE 8000
# Migrations de la base et données d'exemple à chaque démarrage (idempotent). Comptes de démo
# seulement si APP_ENV=dev ; sinon : python -m app.cli create-admin EMAIL.
CMD ["sh", "-c", "python -m app.cli seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
