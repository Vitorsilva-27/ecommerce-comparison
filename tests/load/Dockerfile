FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy test files
COPY locustfile.py .

# Create results directory
RUN mkdir -p /app/results

ENV PYTHONUNBUFFERED=1

# Default command runs Locust web UI
CMD ["locust", "-f", "/app/locustfile.py", "--host", "http://api-gateway:8000"]
