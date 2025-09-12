import os
import re
import argparse
from typing import List, Optional
import requests
from dotenv import load_dotenv

from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_ollama import OllamaEmbeddings


# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
# Allow overriding the handbook markdown path for A/B testing
DATA_DIR = "data/cs-handbook"
INDEX_DIR = os.getenv("INDEX_DIR")  # If building multiple, this is ignored
EMBEDDING_MODELS_ENV = os.getenv("EMBEDDING_MODELS")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Default list used when building multiple without explicit env/args
DEFAULT_EMBEDDING_MODELS: List[str] = [
    "bge-m3",
    "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0",
    "yxchia/multilingual-e5-large-instruct",
]


def _slug_from_embedding(model_name: str) -> str:
    """Create a filesystem-safe slug from the embedding model identifier."""
    return re.sub(r"[^A-Za-z0-9]+", "_", model_name.lower())


def _parse_models_csv(csv_value: str) -> List[str]:
    return [m.strip() for m in csv_value.split(",") if m.strip()]


def _load_documents():
    """Load documents based on HANDBOOK_MD_PATH or markdown under data/."""
    from pathlib import Path
    from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader

    loader = DirectoryLoader(
        DATA_DIR,
        glob="**/*.md",
        loader_cls=UnstructuredMarkdownLoader,
        show_progress=True,
        use_multithreading=True,
    )

    docs = loader.load()
    if not docs:
        print("No documents found. Exiting.")
    else:
        print(f"Loaded {len(docs)} document(s).")
    return docs

def _split_documents_header_aware(docs):
    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)

    header_docs = []
    for d in docs:
        try:
            parts = md_splitter.split_text(d.page_content)
        except Exception:
            parts = [d]
        for s in parts:
            # Merge metadata and derive a concise section label
            md = dict(getattr(d, "metadata", {}))
            md.update(getattr(s, "metadata", {}))
            section = " > ".join([v for v in [md.get("h1"), md.get("h2"), md.get("h3")] if v])
            if section:
                md["section"] = section
            if "source" not in md and "source" in getattr(d, "metadata", {}):
                md["source"] = d.metadata["source"]
            s.metadata = md
            header_docs.append(s)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return text_splitter.split_documents(header_docs)


def _is_running_in_docker() -> bool:
    """Lightweight detection if running inside a container."""
    if os.path.exists("/.dockerenv"):
        return True
    cgroup_path = "/proc/1/cgroup"
    try:
        if os.path.exists(cgroup_path):
            with open(cgroup_path, "r", encoding="utf-8") as f:
                content = f.read()
                return "docker" in content or "kubepods" in content
    except Exception:
        pass
    return False


def resolve_ollama_base_url(preset: Optional[str]) -> str:
    """Resolve Ollama base URL based on explicit env, preset, or environment."""
    # 1) If explicitly set via env, keep it (most explicit wins)
    if OLLAMA_BASE_URL:
        return OLLAMA_BASE_URL

    # 2) Preset override
    if preset == "local":
        return "http://localhost:11434"
    if preset == "vm":
        # Containers reach host Ollama via this DNS alias
        return "http://host.docker.internal:11434"

    # 3) Auto-detect: host => localhost, container => host.docker.internal
    return "http://host.docker.internal:11434" if _is_running_in_docker() else "http://localhost:11434"

def main():
    """
    Build FAISS indexes for a list of embedding models only.
    Order of precedence for selecting models:
      1) --models (comma-separated)
      2) EMBEDDING_MODELS env var (comma-separated)
      3) DEFAULT_EMBEDDING_MODELS constant
    """
    parser = argparse.ArgumentParser(description="Build FAISS index(es) for a list of embedding models.")
    parser.add_argument("--models", help="Comma-separated embedding models to build (overrides env/default)")
    parser.add_argument("--preset", choices=["local", "vm"], help="Environment preset to resolve endpoints")
    args = parser.parse_args()

    print("--- Starting FAISS Index Build ---")

    # Resolve endpoints
    global OLLAMA_BASE_URL
    OLLAMA_BASE_URL = resolve_ollama_base_url(args.preset)
    print(f"Using OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")

    # Decide which embeddings to build
    embeddings_to_build: List[str]
    if args.models:
        embeddings_to_build = _parse_models_csv(args.models)
    else:
        if EMBEDDING_MODELS_ENV:
            embeddings_to_build = _parse_models_csv(EMBEDDING_MODELS_ENV)
        else:
            embeddings_to_build = DEFAULT_EMBEDDING_MODELS

    if not embeddings_to_build:
        print("No embedding models specified. Set --models or EMBEDDING_MODELS.")
        return

    is_multi = len(embeddings_to_build) > 1
    if is_multi and INDEX_DIR:
        print(f"NOTE: Ignoring INDEX_DIR='{INDEX_DIR}' because multiple embeddings will be built.")

    # --- 1. Load Documents once ---
    docs = _load_documents()
    if not docs:
        return
    # --- 2. Split Documents into Chunks once ---
    print("Splitting documents into chunks (header-aware)...")
    splits = _split_documents_header_aware(docs)
    print(f"Created {len(splits)} document chunks.")

    # --- 3. Build per embedding ---

    success_count = 0
    for embedding_model in embeddings_to_build:
        print(f"\n=== Building index for embedding: {embedding_model} ===")

        # Ensure the embedding model is pulled locally in the ollama container
        try:
            print(f"Pulling embedding model '{embedding_model}' from Ollama...")
            requests.post(f"{OLLAMA_BASE_URL}/api/pull", json={"name": embedding_model}, timeout=600)
            print("Successfully pulled embedding model.")
        except Exception as e:
            print(f"Warning: Could not pull embedding model '{embedding_model}'. It may need to be pulled manually. Error: {e}")

        # Determine per-embedding index directory
        target_index_dir = INDEX_DIR
        if not target_index_dir or is_multi:
            slug = _slug_from_embedding(embedding_model)
            target_index_dir = f".rag_cache/{slug}/faiss_index"
        print(f"Using index directory: '{target_index_dir}'")

        # Create embeddings and vector store
        embeddings = OllamaEmbeddings(
            model=embedding_model,
            base_url=OLLAMA_BASE_URL,
        )
        print("Creating FAISS vector store from document chunks...")
        vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)

        print(f"Saving FAISS index to '{target_index_dir}'...")
        os.makedirs(target_index_dir, exist_ok=True)
        vectorstore.save_local(target_index_dir)
        print(f"✓ Completed: {embedding_model}")
        success_count += 1

    print(f"\n--- FAISS Index Build Complete: {success_count}/{len(embeddings_to_build)} successful ---")

if __name__ == "__main__":
    main()
