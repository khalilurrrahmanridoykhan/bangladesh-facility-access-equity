FROM python:3.12-alpine

RUN addgroup -g 10001 app && adduser -D -u 10001 -G app app
WORKDIR /app
COPY --chown=app:app scripts/serve_app.py scripts/serve_app.py
COPY --chown=app:app web web
RUN mkdir -p data/reports && chown -R app:app data

USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"
CMD ["python", "scripts/serve_app.py", "--host", "0.0.0.0", "--port", "8080"]
