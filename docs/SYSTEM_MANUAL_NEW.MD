# Appendix B: System Manual

This manual provides technical instructions for developers and system administrators to deploy, manage, and reproduce the on-premise SLM orchestration system using a GPU-accelerated environment on Vast.ai.

## B.1 System Architecture Overview

**High-Level Diagram:** The system is designed as a multi-container application orchestrated by Docker Compose. The diagram below (Figure 3.1 from the thesis) illustrates the interaction between the core services.

**Core Components:** The key services managed by Docker Compose are:

- **ollama:** Serves local Small Language Models (SLMs) and embedding models, utilizing the host's GPU.
- **rag-api-{embedder_name}:** A set of FastAPI services, one for each embedding model, handling the retrieval logic from a dedicated FAISS index.
- **litellm:** A proxy that provides a unified, OpenAI-compatible endpoint, routing requests to either the local ollama service or external cloud APIs based on the model name.
- **open-webui:** The user-facing web interface for interacting with the models.
- **index-builder:** A one-off job that creates the FAISS vector stores from the source documents.

## B.2 Prerequisites and Initial Setup

The primary deployment target is a Vast.ai GPU virtual machine. The following steps must be completed before launching the instance.

### B.2.1 Vast.ai Account Setup

1. Create an account on [Vast.ai](https://vast.ai/) and add credits.
2. Follow the [Vast.ai Quick Start Guide](https://docs.vast.ai/quickstart) to familiarize yourself with the platform.
3. Add your public SSH key to your Vast.ai account settings to enable secure remote access.

### B.2.2 Cloud Provider API Keys

To enable benchmarking against cloud models, you must acquire API keys from the respective providers. The system uses LiteLLM to manage these connections, which are configured via environment variables.

1. **OpenAI, Anthropic, Gemini:** Create accounts and generate API keys for each service.
2. **Microsoft Azure AI:**
   - Set up an Azure account with access to Azure AI Services.
   - Deploy the required models (e.g., gpt-5-3, gpt-4.1-mini) in your Azure AI Studio. Note: The model deployment name is critical.
   - As shown in `config.yaml`, LiteLLM uses friendly aliases like `azure-gpt5`. You must ensure the model parameter in `config.yaml` (e.g., `azure/gpt-5-3`) exactly matches your Azure deployment name.
   - You will need separate endpoint credentials (API_BASE, API_VERSION, API_KEY) for each model deployment if they are in different projects or regions.

### B.2.3 Required: Store API keys in Vast Account Environment Variables (do not put secrets in templates)

Vast.ai templates should not contain API keys. Templates that include secrets can be blocked from saving and may show the error "Failed to create template!". Instead, add all provider keys in your Vast console; they will be injected into every instance automatically as secrets and are available to the system at runtime.

1. In the Vast console, go to: Account → Environment Variables → Add Variable.
2. Paste the following block and replace placeholders with your values:

```
OPENAI_API_KEY=INSERT YOUR OPENAI KEY
GEMINI_API_KEY=INSERT YOUR GEMINI KEY
ANTHROPIC_API_KEY=INSERT YOUR ANTHROPIC KEY
AZURE_OPENAI_API_BASE=INSERT YOUR AZURE OPENAI KEY
AZURE_OPENAI_API_VERSION=INSERT YOUR API VERSION KEY
AZURE_OPENAI_API_KEY=ETC
AZURE_OPENAI_API_BASE_4_1=INSERT YOUR AZURE OPENAI KEY
AZURE_OPENAI_API_VERSION_4_1=INSERT ETC
AZURE_OPENAI_API_KEY_4_1=INSERT ETC
```

3. Save. These variables will be present inside your VM/container at launch.
4. Do not duplicate these values in the template; keep the template free of secrets.

## B.3 Launching and Deployment

### B.3.1 Selecting and Launching the VM

1. Navigate to the Vast.ai templates page and select the public template for this project (link to be provided).
2. The template is pre-configured with the necessary Docker image and on-start script.
3. Ensure your provider keys are added in Account → Environment Variables (Section B.2.3). Do not place secrets in the template. The instance will receive these variables automatically at launch.
4. Apply filters to find a suitable GPU instance. The benchmarks for this thesis were performed on an NVIDIA RTX 4090, which is the recommended choice for reproducing results.
5. Rent the instance. Vast.ai will begin the setup process.

### B.3.2 Automated On-Start Script

Upon launch, the VM automatically executes an on-start script that performs the entire system setup:

1. **Installs Dependencies:** git, docker, docker-compose, and the NVIDIA Container Toolkit are installed.
2. **Clones Repository:** The project's Git repository is cloned to `/root/on-premise-slm`.
3. **Writes Environment:** The instance environment (including variables injected from Account → Environment Variables) is written to a `.env` file.
4. **Starts Core Services:** The script runs `docker-compose -f docker-compose.yml -f docker-compose.vm.yml up -d` to launch the full application stack.
5. **Preloads Models:** All required SLMs and embedding models are pulled into the ollama service.
6. **Builds Indexes:** The index-builder service runs to create the FAISS vector stores.

The machine is fully ready for use once this script completes.

## B.4 Verification and Smoke Tests

After the on-start script finishes, verify that the system is running correctly.

### B.4.1 Connecting to the VM

Connect to the instance using SSH from your local machine. You can find the SSH command in your Vast.ai console.

```bash
ssh -p <PORT> root@<HOST_IP>
```

**Important**: If connecting immediately after VM launch, wait 5-10 minutes for the on-start script to complete. You can monitor progress:

```bash
# Check if on-start script is still running
ps aux | grep vm-quickstart

# Monitor Docker containers starting up
docker ps -a

# Check service logs if needed
docker logs ollama
docker logs rag-api-bge
```

**SSH Connection Gotchas**:
- Vast.ai VMs use non-standard SSH ports (usually 10000+)
- SSH host keys change between VM instances - remove old entries: `ssh-keygen -R [host]:port`
- Some IDEs struggle with non-standard ports - use SSH config file
- If connection drops, the VM may have been stopped/preempted

### B.4.2 Manual Startup (if on-start failed)

If the automated on-start script failed or you need to restart services:

```bash
cd /root/on-premise-slm

# Full startup sequence
./scripts/vm-quickstart.sh

# Or step-by-step:
./scripts/vm-write-env.sh        # Creates .env from environment
./scripts/vm-build-indexes.sh    # Creates FAISS indexes (required first)
./scripts/vm-core-up.sh          # Starts Docker services
./scripts/vm-preload.sh http://localhost:11434  # Downloads models
```

**Environment Handling**: The `vm-write-env.sh` script sources `/etc/environment` and Vast.ai account variables, then writes a `.env` file with API keys. **Never put secrets in Vast.ai templates** - use Account → Environment Variables instead.

### B.4.3 Service Health Checks

Run these commands to confirm all services are responsive:

```bash
# Essential services (must work)
curl -s http://localhost:11434/api/version | jq .    # Ollama
curl -s http://localhost:4000/v1/models | jq .      # LiteLLM proxy
curl -s http://localhost:8001/info | jq .           # RAG API (bge-m3)
curl -s http://localhost:8002/info | jq .           # RAG API (qwen3)
curl -s http://localhost:8003/info | jq .           # RAG API (e5)

# Open WebUI (web interface)
curl -s http://localhost:3000 >/dev/null && echo "WebUI accessible"
```

**Troubleshooting**:
- If port 8001 fails: Check `docker logs rag-api-bge` for FAISS index errors
- If Ollama fails: Verify GPU access with `nvidia-smi` and check `docker logs ollama`
- If LiteLLM fails: Missing API keys in environment variables
- If ports 8002/8003 fail: Secondary embedding indexes may have failed to build

**GPU Performance Issues**:
- Check GPU access: `nvidia-smi` should show GPU utilization and VRAM usage
- If "failed to initialize CUDA" appears: Restart Ollama container
- Expected VRAM usage: ~6-7GB for multiple models
- Query performance: Should be <2 seconds for typical RAG queries

### B.4.4 Quick Validation Pipeline

```bash
cd /root/on-premise-slm

# Test RAG query performance (should complete in <2 seconds)
time curl -s http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"What are the key dates for term?","model_name":"ollama/hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M"}' | jq .answer

# Test both embedding models
curl -s http://localhost:8001/info | jq .embedding_model  # Should show "bge-m3"
curl -s http://localhost:8002/info | jq .embedding_model  # Should show "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
curl -s http://localhost:8003/info | jq .embedding_model  # Should show "yxchia/multilingual-e5-large-instruct"

# Check GPU utilization
nvidia-smi  # Should show ~6-7GB VRAM usage with Ollama processes

# Comprehensive smoke test
./scripts/vm-smoke.sh

# Expected: Query <2sec, GPU active, both embeddings working
```

## B.5 Development and Evaluation

### B.5.1 Remote Development with VS Code / Cursor

For easier file editing and script execution, you can connect your local IDE to the remote VM via SSH.

1. **VS Code:** Install the "Remote - SSH" extension. Use the SSH command from the Vast.ai console to add a new SSH host and connect to it.
2. **Cursor:** Cursor has native support for remote SSH development. Follow its documentation to connect to the VM.

Once connected, you can open the `/root/on-premise-slm` folder to interact with the project files as if they were local.

### B.5.2 Running Full Evaluations

With a remote IDE connection, you can easily trigger the full benchmarking scripts.

**RAG Quality Evaluation:**

```bash
# From a terminal in your IDE or an SSH session:
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm benchmarker
```

**Performance and Throughput Evaluation:**

```bash
# Edit the command in docker-compose.vm.yml for the `throughput-runner`
# service to specify the models and parameters you wish to test.
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner
```

Results will be saved to the `results/` directory.

## B.6 Source Code

The complete source code for this project is available in a public Git repository: https://github.com/malikbou/on-premise-slm
