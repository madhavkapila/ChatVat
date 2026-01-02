# FILE: chatvat/bot_template/Dockerfile

FROM python:3.11-slim

# 1. Set Environment Variables FIRST
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/ms-playwright

# 2. Install System Dependencies (Required for Chrome to run)
# We do this early so it's cached. Added --no-install-recommends to reduce size.
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# 3. Install Python Dependencies (INCLUDES PLAYWRIGHT PACKAGE)
# This MUST happen before we try to use 'python -m playwright'
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. NOW Install the Browsers (The "Eyes")
# Since pip install is done, 'python -m playwright' will now work.
# [OPTIMIZED] Only install chromium and cleanup caches immediately to save ~1.2GB.
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    python -m playwright install --with-deps chromium && \
    chmod -R 755 $PLAYWRIGHT_BROWSERS_PATH && \
    rm -rf /root/.cache/pip && \
    rm -rf /root/.cache/ms-playwright/firefox* && \
    rm -rf /root/.cache/ms-playwright/webkit*

# 5. Inject Source Code (The "Brain")
COPY . .

# 6. Runtime Configuration
ENV PYTHONPATH=/app

# 7. Security (Non-root user)
# [OPTIMIZED] Clean up build tools before finalizing.
RUN apt-get purge -y --auto-remove build-essential && \
    useradd -m -u 1000 chatvat-user && \
    mkdir -p /app/data && \
    chown -R chatvat-user:chatvat-user /app

USER chatvat-user
EXPOSE 8000

# 8. Healthcheck & Start
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/main.py"]