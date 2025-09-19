# Appendix B: System Manual

This manual provides step-by-step instructions for system administrators to deploy and manage the on-premise Small Language Model (SLM) orchestration system on Vast.ai.

---

## B.1 System Overview

**Architecture at a Glance**
The system runs as a multi-container application using Docker Compose:

- **ollama** – Serves local SLMs and embedding models (GPU-accelerated).
- **rag-api-{embedder}** – FastAPI services for retrieval using FAISS indexes.
- **litellm** – Unified OpenAI-compatible proxy, routes requests locally or to cloud APIs.
- **open-webui** – Web interface for users to chat with models.
- **index-builder** – One-time job to create FAISS indexes from documents.
- **benchmarker / throughput-runner** – Scripts for evaluation.

**Flow:**
Documents → Index Builder → RAG APIs → LiteLLM Proxy → OpenWebUI.

---

## B.2 Prerequisites

### B.2.1 Vast.ai Account
1. Create an account: [Vast.ai](https://vast.ai/)
2. Add credits (recommended: $10 for testing).
3. [Add your public SSH key](https://vast.ai/docs/ssh-keys/) to account settings.
   - This allows passwordless login to rented VMs via SSH.

### B.2.2 API Keys
Obtain API keys if you plan to benchmark against cloud providers:

- [OpenAI](https://platform.openai.com/account/api-keys)
- [Anthropic](https://console.anthropic.com/settings/keys)
- [Google Gemini](https://aistudio.google.com/app/apikey)

### B.2.3 Setting Environment Variables
In the Vast.ai console:
**Account → Environment Variables → Add Variable**

Paste the following (replace placeholders with your keys):

```bash
OPENAI_API_KEY=xxxx
ANTHROPIC_API_KEY=xxxx
GEMINI_API_KEY=xxxx
AZURE_OPENAI_API_BASE=https://emtechfoundrytrial2.cognitiveservices.azure.com
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_API_KEY=XXXX
AZURE_OPENAI_API_BASE_4_1=https://llm-benchmarking.cognitiveservices.azure.com
AZURE_OPENAI_API_VERSION_4_1=2025-01-01-preview
AZURE_OPENAI_API_KEY_4_1=XXXX
````

This ensures secrets are available inside the VM at runtime.
**Do not hardcode secrets into templates.**

---

## B.3 Launching on Vast.ai

### B.3.1 Apply Template
1. Navigate to the template: [Vast.ai On-Premise Template](https://cloud.vast.ai?ref_id=274010&template_id=609448d4f98ab33f7b4c3f8a8477c2ed)
2. Apply filters:
   * #GPUs: 1x
   * Location: Europe
   * Sort: Price (inc.)
3. Select **1x RTX 4090** and click **Rent**.

### B.3.2 Start VM
Vast.ai automatically executes an on-start script:
   * Installs dependencies (Docker, NVIDIA toolkit).
   * Clones the project repo to `/root/on-premise-slm`.
   * Writes `.env` from your account variables.
   * Launches Docker stack with `docker-compose.yml` + `docker-compose.vm.yml`.
   * Preloads models into **ollama**.
   * Builds FAISS indexes.

Allow \~5–10 minutes.

---

## B.4 Verification

### B.4.1 Connect via SSH

```bash
ssh -p <PORT> root@<HOST_IP>
```

(Find port and IP in Vast.ai console → **Instances** → **Connect**.)

### B.4.2 Check Services

```bash
docker ps
```

Expected containers: `ollama`, `litellm`, `rag-api-bge`, `rag-api-qwen3`, `rag-api-e5`, `open-webui`.

### B.4.3 Quick Health Checks

```bash
curl -s http://localhost:11434/api/version | jq .
curl -s http://localhost:4000/v1/models | jq .
curl -s http://localhost:8001/info | jq .
```

### B.4.4 If Health Checks Fail

Run recovery scripts:

```bash
cd /root/on-premise-slm
./scripts/vm-quickstart.sh
```

Or step-by-step:
```bash
cd /root/on-premise-slm
./scripts/vm-write-env.sh
./scripts/vm-core-up.sh
./scripts/vm-preload.sh http://localhost:11434
./scripts/vm-build-indexes.sh
```

Check GPU:
```bash
nvidia-smi
```

If Ollama is not using GPU:
```bash
docker restart ollama
```
---

## B.5 Accessing OpenWebUI

OpenWebUI provides the main user interface.

### B.5.1 Find External URL

1. In Vast.ai console → Instance → **IP Port Info**.
2. Look for mapping like: `90.240.219.112:28244 → 3000/tcp`.
3. Open:

   ```
   http://90.240.219.112:28244
   ```

### B.5.2 First-Time Setup

1. Create an **admin account**.
2. Configure:

   * **Admin Settings → Connections → Manage OpenAI API Connections → +**

     * Add: `http://rag-api-bge:8000/v1` → Save
   * Disable **Ollama API**.
   * **Models tab:** Disable cloud models if desired.
   * **Interface → Import Prompt Suggestions:**
     Upload `data/prompt-suggestions/prompt-suggestions-ucl-cs-handbook.json`.
   * **Add additional users:**
     Navbar → **Users** → **+** → **Add User** (provide email & password).

3. Start using the app:

   * Home icon → run a suggested prompt.
   * If slow: run `nvidia-smi` and restart Ollama.


---

## B.6 Running Evaluations

### B.6.1 Lightweight Local Benchmark

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm benchmarker
```

### B.6.2 Lightweight Throughput

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner
```

### B.6.3 Full Benchmark (5+ hrs, includes cloud models)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm benchmarker --preset full
```

### B.6.4 Full Throughput (5+ hrs)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner --preset full
```

---

## B.7 Results and Graphs

Results saved under `/root/on-premise-slm/results`.

### B.7.1 View Files

```bash
ls results/
```

### B.7.2 Generate Graphs

```bash
python src/plotting/plot_results.py results/<filename>.json
```

### B.7.3 Export Results

From local machine:

```bash
scp -P <PORT> root@<HOST_IP>:/root/on-premise-slm/results/* ./results/
```

### B.7.4 Remote Editing with VS Code / Cursor

For easier development and inspection of files, you can connect directly to the VM via SSH from your IDE.

- **VS Code:** Use the [Remote - SSH extension](https://code.visualstudio.com/docs/remote/ssh).
- **Cursor:** Cursor has built-in support for remote SSH (see [cursor.com](https://www.cursor.com/)).

Once connected, open the folder:
```bash
/root/on-premise-slm
```

This allows you to edit files, run scripts, and monitor logs directly from your IDE.


---

## B.8 Common Issues & Fixes

| Issue             | Fix                                                 |
| ----------------- | --------------------------------------------------- |
| WebUI not loading | `docker logs open-webui`, check port mapping        |
| Curl checks fail  | `./scripts/vm-quickstart.sh`                        |
| GPU idle          | `nvidia-smi`; if idle → `docker restart ollama`     |
| FAISS error       | `./scripts/vm-build-indexes.sh`                     |
| Missing API keys  | `./scripts/vm-write-env.sh` after updating env vars |

---

## B.9 Source Code

Complete source code:
[GitHub Repository](https://github.com/your-repo-link)

---
