FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=pip_ca \
    PIP_CERT=${PIP_CERT:-/etc/ssl/certs/ca-certificates.crt} \
    sh -c 'if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; exec pip install --no-cache-dir -r requirements.txt'
RUN groupadd -g 10001 bot \
    && useradd -u 10001 -g bot --no-create-home bot \
    && install -d -o bot -g bot -m 0700 /app/data
COPY --chown=bot:bot app ./app
USER bot
CMD ["python", "-m", "app.main"]
