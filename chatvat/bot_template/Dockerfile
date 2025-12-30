# FILE: chatvat/bot_template/Dockerfile

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

ENV PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/ms-playwright

RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    python -m playwright install --with-deps chromium && \
    chmod -R 755 $PLAYWRIGHT_BROWSERS_PATH

# We install libraries required for Headless Chrome (Playwright) to run reliably.
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libnss3 \
    libx11-xcb1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# We copy requirements.txt first to leverage Docker layer caching.
# NOTE: Ensure 'sentence-transformers' is added to your requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. INJECT ENGINE & LOGIC (The "Source Injection")
# The builder has placed the 'chatvat' source folder and 'src' entrypoint 
# right here in the build context. We copy them all in one go.
# Structure inside /app will be:
#   /app/chatvat/            <-- The Core Engine
#   /app/src/                <-- The Entrypoint
#   /app/chatvat.config.json <-- The User Config
#   /app/.env                <-- The Secrets
COPY . .

# CRITICAL: This tells Python "Look inside /app for modules".
# This allows 'import chatvat' to work without pip installing the package.
ENV PYTHONPATH=/app

# Security & Runtime Permissions
# We create a non-root user for security.
RUN useradd -m -u 1000 chatvat-user && \
    mkdir -p /app/data && \
    chown -R chatvat-user:chatvat-user /app

USER chatvat-user
EXPOSE 8000

# Healthcheck
# Ensures the container restarts if the API hangs.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start
CMD ["python", "src/main.py"]