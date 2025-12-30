# ChatVat 🏭
> **The Universal RAG Chatbot Factory**

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](#license)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Style](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)

---

## 🌟 The Vision

**ChatVat** is not just another chatbot script. It is a **Manufacturing Plant** for self-contained AI systems. 

It solves the "It works on my machine" problem by adhering to a strict **"Zero-Dependency"** philosophy. ChatVat takes your raw data sources—websites, APIs, and documents—and fuses them with a production-grade RAG engine into a sealed Docker container. This "capsule" contains everything needed to run: the code, the database, the browser, and the API server.

You can deploy a ChatVat bot anywhere: from a MacBook Air to an air-gapped server in Antarctica, without installing Python or git.

### Core Philosophy
* **Production Parity:** The bot you test locally is bit-for-bit identical to the bot you deploy.
* **Source Injection:** The engine code is "injected" directly into the container during the build. No external git clones or PyPI downloads are required inside the image.
* **Self-Healing:** Built-in deduplication (MD5 Hashing), crash recovery, and "Ghost Entry" prevention.

---

## ⚡ Quick Start

### 1. Installation
Install the ChatVat CLI from the source (or your private registry).

```bash
pip install chatvat
```

### 2. Initialize the Assembly Line
Create a clean directory for your new bot and run the configuration wizard.

```bash
mkdir my-crypto-bot
cd my-crypto-bot
chatvat init
```

*The wizard will guide you through:*
* **Naming your bot**
* **Setting up AI Brain** (Groq Llama-3 + HuggingFace Embeddings)
* **Connecting Data Sources** (URLs, APIs, or Local Files)
* **Defining Deployment Ports**

### 3. Build the Capsule
Compile your configuration and the ChatVat engine into a Docker Image.

```bash
chatvat build
```

> **What happens here?** > The CLI locates the `chatvat` library on your system, copies the core engine code into a build context, injects your `chatvat.config.json`, and triggers a Docker build. The result is a sealed image containing your specific bot.

### 4. Deploy Anywhere
Run your bot using standard Docker commands. It injects your API keys at runtime for security.

```bash
# Example: Running on Port 8000
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name crypto-bot \
  chatvat-bot
```

---

## 🧠 Architecture Deep Dive

ChatVat implements a modular **RAG (Retrieval-Augmented Generation)** pipeline designed for resilience.


### The Components

| Component | Role | Description |
| :--- | :--- | :--- |
| **The Cortex** | Intelligence | Powered by **Groq** for ultra-fast inference using the model of your choice and **HuggingFace** for embeddings. |
| **The Memory** | Vector Store | A persistent, thread-safe **ChromaDB** instance. It uses MD5 hashing to prevent duplicate data entry. |
| **The Eyes** | Crawler | A headless **Chromium** browser (via Crawl4AI/Playwright) capable of reading dynamic JS-heavy websites. |
| **The Nervous System** | Ingestor | A background worker that auto-updates knowledge every `X` minutes (configurable). |
| **The API** | Interface | A high-performance **FastAPI** server exposing REST endpoints. |

### The "Source Injection" Workflow

Unlike traditional builds that `pip install` libraries from the internet, ChatVat performs **Source Injection**:

1.  **Locate:** The CLI finds where `chatvat` is installed on your host machine.
2.  **Extract:** It copies the raw Python source code of the engine.
3.  **Inject:** It places this code into the `/app` directory of the Docker container.
4.  **Seal:** The Dockerfile sets `PYTHONPATH=/app`, making the injected code instantly executable without installation.

---

## 🛠️ Configuration Guide

Your bot is defined by `chatvat.config.json`. You can edit this file manually after running `init`.

```json
{
    "bot_name": "ChatVatBot",
    "port": 8000,
    "refresh_interval_minutes": 60,
    "system_prompt": "You are a helpful assistant for the .....",
    "llm_model": "llama-3.1-70b-versatile",
    "embedding_model": "all-MiniLM-L6-v2",
    "sources": [
        {
            "type": "static_url",
            "target": "[https://www.amazon.com/gp/bestsellers/books/ref=zg_bs_nav](https://www.amazon.com/gp/bestsellers/books/ref=zg_bs_nav)"
        },
        {
            "type": "dynamic_json",
            "target": "[https://YOUR_API_ENDPOINT](https://YOUR_API_ENDPOINT)",
            "headers": {
                "Authorization": "Bearer ${API_KEY}"
            }
        },
        {
            "type": "local_file",
            "target": "./policy_docs.pdf"
        }
    ]
}
```

* **`refresh_interval_minutes`**: Set to `0` to disable auto-updates.
* **`sources`**: Supports `static_url` (Websites), `dynamic_json` (REST APIs), and `local_file` (PDF/TXT).
* **`headers`**: Can use `${VAR_NAME}` syntax to reference environment variables from your `.env` file.

---

## 📚 API Reference

Once the container is running, interact with it via HTTP REST API.

### 1. Health Check
Used by cloud balancers (AWS/Render) to verify the bot is alive.

```bash
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 2. Chat Interface
The main endpoint for sending queries.

```bash
POST /chat
```
**Payload:**
```json
{
  "message": "What events are happening on Day 1?"
}
```
**Response:**
```json
{
  "message": "On Day 1, the opening ceremony starts at 10 AM..."
}
```

---

## ⚖️ License & Proprietary Notice

**Copyright © 2025 Madhav Kapila. All Rights Reserved.**

This software is **Proprietary (Closed Source)**.

* **Usage:** You are granted a limited license to use this tool for educational, private testing, or internal business purposes.
* **Restrictions:**
    * You **MAY NOT** copy, modify, redistribute, sell, or lease any part of the `chatvat` source code.
    * You **MAY NOT** reverse engineer or attempt to extract the source code.
    * You **MAY NOT** upload this package to public registries (like PyPI) or public repositories (like GitHub) without prior written permission.

*All intellectual property rights remain exclusively with Madhav Kapila.*

---

<p align="center">
  Built with ❤️ by the <b>ChatVat Factory</b>.
</p>