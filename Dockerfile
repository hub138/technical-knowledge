FROM python:3.12-slim

WORKDIR /app
COPY site /app/site
COPY vault /app/vault
COPY index.html README.md PROJECT_MAP.md CONTRIBUTING.md INTEGRATION_NOTES.md DEPLOYMENT.md /app/
COPY projects /app/projects

ENV KNOWLEDGE_HOST=0.0.0.0 \
    KNOWLEDGE_PORT=8787 \
    PYTHONUNBUFFERED=1
EXPOSE 8787

USER nobody
CMD ["python", "/app/site/server.py", "--root", "/app/vault", "--host", "0.0.0.0", "--port", "8787"]
