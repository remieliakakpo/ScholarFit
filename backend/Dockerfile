FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
# uploads/ créé ici pour que le volume Docker hérite des droits de l'utilisateur de l'API
RUN useradd --create-home --uid 10001 scholarfit && mkdir -p /app/uploads && chown -R scholarfit /app
USER scholarfit
EXPOSE 8000
# La base est créée et les données d'exemple chargées au premier démarrage (idempotent).
CMD ["sh", "-c", "python -m app.cli seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
