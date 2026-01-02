# ChatVat (The ChatBot🤖 Factory🏭)

> **The Universal RAG Chatbot Factory**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Style](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](https://github.com/madhavkapila/ChatVat)

---

## 🌟 The Vision

**ChatVat** is not just another chatbot script. It is a **Manufacturing Plant** for self-contained AI systems.

It solves the "It works on my machine" problem by adhering to a strict **"Zero-Dependency"** philosophy. ChatVat takes your raw data sources—websites, secured APIs, and documents—and fuses them with a production-grade RAG engine into a sealed Docker container. This "capsule" contains everything needed to run: the code, the database, the browser, and the API server.

You can deploy a ChatVat bot anywhere: from a MacBook Air to an air-gapped server in Antarctica, with nothing but Docker installed.

### Core Philosophy
* **Split Architecture:** A lightweight CLI (~15MB) for management, and a heavy-duty Docker container for the AI engine. No more installing 3GB of CUDA drivers on your laptop just to run a build tool.
* **Universal Connectivity:** Acts as a generic **MCP (Model Context Protocol)** connector. Can ingest data from any API using custom headers and auth keys.
> Disclaimer :  We advise users to ensure they have authorized access to secured APIs and to follow the provider's guidelines when extracting data from sensitive APIs. Read the full disclaimer below for more details.  
* **Self-Healing:** Built-in deduplication (Content Hashing), crash recovery, and "Ghost Entry" prevention.
* **Production Parity:** The bot you test locally is bit-for-bit identical to the bot you deploy, thanks to baked-in browser binaries.

---

## ⚡ Quick Start

### 1. Installation
Install the lightweight ChatVat CLI. (It installs in seconds and won't bloat your system).

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
* **Connecting Data Sources** (URLs, Secured APIs, or Local Files)
* **Defining Deployment Ports**

### 3. Build the Capsule
Compile your configuration and the ChatVat engine into a Docker Image.

```bash
chatvat build
```

> **What happens here?**
> The CLI performs **Source Injection**: it copies the core engine code into a build context, injects your `chatvat.config.json`, and triggers a multi-stage Docker build. It optimizes the image by installing specific browser binaries (Chromium only) and purging build tools, keeping the final image lean.

### 4. Deploy Anywhere
Run your bot using standard Docker commands. Note the use of `--ipc=host` to prevent browser crashes on memory-heavy sites.

```bash
# Example: Running on Port 8000
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --ipc=host \
  --restart always \
  --name crypto-bot \
  chatvat-bot
```

---

## 🧠 Architecture Deep Dive

ChatVat implements a modular **RAG (Retrieval-Augmented Generation)** pipeline designed for resilience.

### The Components

| Component | Role | Description |
| :--- | :--- | :--- |
| **The Builder** | CLI Manager | Runs on host. Lightweight (~15MB). Orchestrates the factory process and Docker builds. |
| **The Cortex** | Intelligence | Powered by **Groq** for ultra-fast inference and **HuggingFace** for embeddings. Runs inside Docker. |
| **The Memory** | Vector Store | A persistent, thread-safe **ChromaDB** instance. Uses MD5 hashing to silently drop duplicate data during ingestion. |
| **The Eyes** | Crawler | A headless **Chromium** browser (via Crawl4AI/Playwright) managed with `--ipc=host` stability to read dynamic JS websites. |
| **The Connector** | Universal MCP | A polymorphic ingestor that can authenticate with secured APIs using environment-variable masking (e.g., `${API_KEY}`). |
| **The API** | Interface | A high-performance **FastAPI** server exposing REST endpoints. |

### The "Split Strategy" Workflow

Unlike traditional tools that force you to install heavy AI libraries locally:

1.  **Local (Host):** You only have `typer`, `rich`, and `requests`. Fast and clean.
2.  **Container (Engine):** The Docker build installs `torch`, `langchain`, `playwright`, and `chromadb`.
3.  **Result:** You get the power of a heavy AI stack without polluting your local development environment.

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
            "target": "[https://docs.stripe.com](https://docs.stripe.com)"
        },
        {
            "type": "dynamic_json",
            "target": "[https://api.github.com/repos/my-org/my-repo/issues](https://api.github.com/repos/my-org/my-repo/issues)",
            "headers": {
                "Authorization": "Bearer ${GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
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
* **`static_url`**: Uses Playwright to render JavaScript before scraping.
* **`dynamic_json`**: Acts as a Universal Connector. Supports custom headers.
* **`headers`**: Securely inject secrets using `${VAR_NAME}` syntax. The engine resolves these from the container's environment variables at runtime.
* **`llm-model`**: You can select your required Groq LLM model while initialising the ChatBot. 

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
  "version": "0.1.9"
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
  "message": "What is the return policy for digital items?"
}
```
**Response:**
```json
{
  "message": "According to the policy document, digital items are non-refundable once downloaded..."
}
```

---

## ⚠️ Disclaimer & Legal Notice

**Author:** Madhav Kapila
**Project:** ChatVat - Conversational AI & Web Crawling Engine

This software is provided for **educational and research purposes only**.

1.  **No Liability:** The author (Madhav Kapila) is not responsible for any damage caused by the use of this tool. This includes, but is not limited to:
    * IP bans or blacklisting of your device/server.
    * Legal consequences of crawling restricted or sensitive websites.
    * Data loss or corruption on the user's local machine or target infrastructure.
2.  **User Responsibility:** You, the user, acknowledge that you are solely responsible for compliance with all applicable laws and regulations (such as GDPR, CFAA, or Terms of Service of target websites) when using this software.
3.  **"As Is" Warranty:** This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement.

**By downloading, installing, or using this software, you agree to these terms.**

---

<p align="center">
  Built with ❤️ by <b>Madhav Kapila</b>.
</p>