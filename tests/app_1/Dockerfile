FROM python:3.12-slim

WORKDIR /app
COPY tests/app_1/ .
RUN pip install --no-cache-dir rich pyyaml click
CMD ["python", "main.py"]
