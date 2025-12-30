# FILE: chatvat/bot_template/Dockerfile

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# 1. System Dependencies
# Added 'libasound2' and others often needed by Playwright/Headless browsers
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. LAYER A: The Optimized Environment (Heavy Libs)
# We copy and install requirements FIRST.
# This ensures Torch CPU is installed before 'chatvat' can accidentally pull Torch GPU.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. LAYER B: Browser Engines (Critical for Crawl4AI)
# Since your requirements include 'playwright', we must install the browsers.
# We install only chromium to save space (add firefox/webkit if needed).
RUN python -m playwright install --with-deps chromium

# 4. LAYER C: Your Core Engine (The Factory Logic)
# Pip will see that dependencies (torch, etc.) are already met by Layer A.
# It will only install the 'chatvat' code itself.
RUN pip install chatvat

# 5. Copy User Config & Code
COPY . .

# 6. Security & Runtime
RUN useradd -m -u 1000 chatvat-user && \
    mkdir -p /app/data && \
    chown -R chatvat-user:chatvat-user /app

USER chatvat-user
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/main.py"]