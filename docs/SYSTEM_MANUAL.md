# System Manual

This manual provides step-by-step instructions for system administrators to deploy and manage the on-premise Small Language Model (SLM) orchestration system on `Vast.ai`.

## System Overview

### Architecture
The system runs as a multi-container application using Docker Compose, comprising the following services (refer to Figure 3.1 High-Level System Architecture Diagram):
- `ollama`: Serves local SLMs and embedding models (GPU-accelerated).
- `rag-api-{embedder}`: A set of FastAPI services for retrieval logic using FAISS vector indexes.
- `litellm`: A unified OpenAI-compatible proxy that routes requests to local services or external cloud APIs.
- `open-webui`: UI for users to interact with the models.
- `index-builder`: One-time job responsible for creating the FAISS indexes from source documents.
- `benchmarker`: Services containing scripts for system evaluation.

### Data Flow
The high-level data and service interaction flow is as follows:
Documents → `index-builder` → RAG APIs → `litellm` Proxy → `open-webui`

## Prerequisites

### Vast.ai Account
1. Create an account at https://vast.ai/.
2. Add credits to your account ($5-10 is recommended for initial testing).
3. **Add your public SSH key** to your account settings to enable secure, passwordless login to rented VMs.

### API Keys
Obtain API keys if you plan to benchmark the system against external cloud providers:
- **OpenAI**: https://platform.openai.com/account/api-keys
- **Anthropic**: https://console.anthropic.com/settings/keys
- **Google Gemini**: https://aistudio.google.com/app/apikey

### Setting Environment Variables
To ensure secrets are securely available to the VM at runtime, add them to your `Vast.ai` account. Navigate to **Account → Environment Variables → Add Variable** and add the following, replacing placeholders with your keys.

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

**Important:** Do not hardcode secrets into templates.

## Launching on Vast.ai

### Apply Template
1. Navigate to the template: **Vast.ai On-Premise Template**: https://cloud.vast.ai?ref_id=274010&template_id=609448d4f98ab33f7b4c3f8a8477c2ed
2. Apply the following filters:
   - #GPUs: 1x
   - Location: Europe
   - Sort: Price (inc.)
3. Select an instance with **1x RTX 4090** and click **Rent**.

### Automated On-Start Script
Upon launch, `Vast.ai` automatically executes an on-start script which performs the following tasks. Please allow approximately 5–10 minutes for this process to complete.
- Installs dependencies (Docker, NVIDIA Container Toolkit).
- Clones the project repository to `/root/on-premise-slm`.
- Writes a `.env` file from your account's environment variables.
- Launches the full Docker stack using `docker-compose.yml` and `docker-compose.vm.yml`.
- Preloads all required models into the `ollama` service.
- Builds the FAISS vector indexes.

## Verification and Troubleshooting

After the on-start script finishes, follow these steps to verify that the system is running correctly.

### Connect via SSH
Find the connection details in the `Vast.ai` console under **Instances → Connect** and use the provided command to connect to the VM.
```bash
ssh -p <PORT> root@<HOST_IP>
```

### Step 1: Verify Running Services
First, check that all Docker containers were started correctly.
```bash
docker ps
```
You should see the following containers listed as running: `ollama`, `litellm`, `rag-api-bge`, `rag-api-qwen3`, `rag-api-e5`, and `open-webui`.

If any containers are missing, you can start the full stack with the following command:
```bash
cd /root/on-premise-slm
docker-compose -f docker-compose.yml -f docker-compose.vm.yml up -d
```

### Step 2: Perform Service Health Checks
Run these commands from within the VM to confirm the core services are responsive.
```bash
# Check Ollama status
curl -s http://localhost:11434/api/version | jq .

# Check LiteLLM proxy status (should list available models)
curl -s http://localhost:4000/v1/models | jq .

# Check RAG API status (bge embedder instance)
curl -s http://localhost:8001/info | jq .
```

### Step 3: Verify GPU Access
A common failure point is the `ollama` container not having proper access to the GPU. To verify this, run:
```bash
docker exec ollama nvidia-smi
```
This command should output the NVIDIA driver and GPU details. If you get an error, it means the container cannot access the GPU. You can also monitor GPU utilization in real-time with:
```bash
watch -n 0.5 nvidia-smi
```

### Troubleshooting and Manual Recovery
If services are unresponsive or the GPU check fails, follow these recovery steps.

#### Restarting a Single Service
If the `ollama` service is running but not utilizing the GPU, a simple restart can often resolve the issue.
```bash
# Restart with proper GPU configuration
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d ollama

# Wait for Ollama to start
sleep 5

# Check if Ollama container has GPU access now
docker exec ollama nvidia-smi
```

#### Manual Reset
If issues persist, you can run the main startup script again.
```bash
cd /root/on-premise-slm
chmod +x scripts/*.sh
./scripts/vm-quickstart.sh
```
Alternatively, run the setup steps individually:
```bash
cd /root/on-premise-slm
chmod +x scripts/*.sh
./scripts/vm-write-env.sh
./scripts/vm-core-up.sh
./scripts/vm-preload.sh http://localhost:11434
./scripts/vm-build-indexes.sh
```

## Accessing OpenWebUI
OpenWebUI provides the main user interface for the system.

### Find External URL
1. In the `Vast.ai` console, navigate to your instance and click **IP Port Info**.
2. Look for the port mapping for the web UI, which will appear similar to: `90.240.219.112:28244 -> 3000/tcp`.
3. Open the external URL (e.g., http://90.240.219.112:28244) in your web browser.

### First-Time Setup
1. The first time you access the URL, you will be prompted to create an **admin account**.
2. After logging in, perform the following initial configuration:
   - Navigate to **Admin Settings → Connections → Manage OpenAI API Connections → +**.
   - Add the service URL: `http://rag-api-bge:8000/v1` and save.
   - Disable the default **Ollama API** connection if not needed directly.
   - In the **Models** tab, disable any cloud models you do not wish to expose to users.
   - In the **Interface** tab, use **Import Prompt Suggestions** to upload the file `data/prompt-suggestions/prompt-suggestions-ucl-cs-handbook.json`.
   - To add accounts for end-users, navigate to **Users → + → Add User** from the main navigation bar and provide an email and password.
3. The application is now ready. You can test it by clicking the home icon and running one of the suggested prompts.

## Running Evaluations
The following commands can be run from the `/root/on-premise-slm` directory on the VM.

### Lightweight Local Benchmark
```bash
./scripts/benchmark-simple.sh
```

### Lightweight Throughput Test
```bash
./scripts/throughput-simple.sh
```

### Full Benchmark (5+ hrs)
This includes benchmarking against configured cloud models.
```bash
./scripts/benchmark-full.sh
```

### Full Throughput Test (5+ hrs)
```bash
./scripts/throughput-full.sh
```

## Results and Graphs
Evaluation results are saved to the `/root/on-premise-slm/results` directory.

### View Result Files
```bash
ls results/
```

### Generate Graphs
```bash
# for RAG Quality Benchmark
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm benchmarker python src/benchmarking/plot_rag_results.py \
  results/TIMESTAMP/summary.json

# for throughput testing
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm benchmarker python src/throughput/plot_simple.py \
  results/TIMESTAMP/benchmark-results.csv
```

### Export Results
To copy results from the VM to your local machine, run this command from your local terminal:
```bash
scp -P <PORT> root@<HOST_IP>:/root/on-premise-slm/results/* ./results/
```

### Remote Editing with VS Code / Cursor
For easier development, connect to the VM via SSH from your IDE.
- **VS Code:** Use the Remote - SSH extension: https://code.visualstudio.com/docs/remote/ssh
- **Cursor:** Use the built-in remote SSH functionality.

Once connected, open the project folder at `/root/on-premise-slm` to edit files, run scripts, and monitor logs directly.

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| WebUI not loading | Check logs with `docker logs open-webui` and verify the port mapping. |
| Curl checks fail | Rerun the main startup script: `./scripts/vm-quickstart.sh`. |
| GPU is idle | Check usage with `nvidia-smi`. If idle, run `docker restart ollama`. |
| FAISS error | Rebuild the indexes with `./scripts/vm-build-indexes.sh`. |
| Missing API keys | Update environment variables in the Vast console, then run `./scripts/vm-write-env.sh`. |

## Source Code
The complete source code is available at the following GitHub repository: https://github.com/malikbou/on-premise-slm.
