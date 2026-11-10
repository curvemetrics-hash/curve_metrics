# Standard production container for developer app
FROM python:3.12-slim

WORKDIR /app

# Zero third-party bloat needed for the core service
COPY app.py /app/app.py

ENV PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

USER 10001

CMD ["python", "/app/app.py"]
