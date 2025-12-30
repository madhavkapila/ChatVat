# FILE: chatvat/bot_template/Dockerfile

FROM python:3.12-slim

# PYTHONUNBUFFERED=1: Ensures logs appear immediately in Docker console
# PYTHONDONTWRITEBYTECODE=1: Prevents creation of .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 'curl' is needed for the HEALTHCHECK command below
# 'build-essential' helps if any pip packages need compiling
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


COPY requirements.txt .
RUN pip install -r requirements.txt

# 6. Copy Application Code
COPY . .

# 7. Permissions & Security
# Create a dedicated user so the app doesn't run as root (Security Best Practice)
RUN useradd -m -u 1000 chatvat-user && \
    mkdir -p /app/data && \
    chown -R chatvat-user:chatvat-user /app

# Switch to the secure user
USER chatvat-user

# 8. Expose Port
EXPOSE 8000

# 9. Healthcheck
# Docker will ping this endpoint every 30s. If it fails 3 times, the container is marked unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 10. Start Command
# Uses the standard Python entry point which triggers uvicorn
CMD ["python", "src/main.py"]