FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml .
COPY uv.lock .

# Install Python dependencies
RUN pip install uv && \
    uv pip install -r uv.lock

# Copy source code
COPY . .

# Expose health check port
EXPOSE 8000

CMD ["python", "main.py"]
