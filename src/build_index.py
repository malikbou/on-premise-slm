import os
import re
import argparse
from typing import List
import requests
from dotenv import load_dotenv

from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
# Allow overriding the handbook markdown path for A/B testing
HANDBOOK_MD_PATH = os.getenv("HANDBOOK_MD_PATH")
DATA_DIR = "data/"
INDEX_DIR = os.getenv("INDEX_DIR")  # If building multiple, this is ignored
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_MODELS_ENV = os.getenv("EMBEDDING_MODELS")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

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
    """Load documents based on HANDBOOK_MD_PATH or all markdown under data/."""
    from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader

    print(f"Loading documents from '{DATA_DIR}' directory..." if not HANDBOOK_MD_PATH else f"Loading single markdown file: {HANDBOOK_MD_PATH}")
    if HANDBOOK_MD_PATH:
        try:
            loader = DirectoryLoader(
                os.path.dirname(HANDBOOK_MD_PATH) or ".",
                glob=os.path.basename(HANDBOOK_MD_PATH),
                loader_cls=UnstructuredMarkdownLoader,
                show_progress=False,
                use_multithreading=False,
            )
            docs = loader.load()
            print(f"Loaded {len(docs)} document(s) from HANDBOOK_MD_PATH.")
            return docs
        except Exception as e:
            print(f"Failed to load HANDBOOK_MD_PATH='{HANDBOOK_MD_PATH}': {e}")
            return []
    else:
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
            print(f"Loaded {len(docs)} documents.")
        return docs

def main():
    """
    Build FAISS indexes for one or multiple embedding models.
    Default: build for multiple embeddings (EMBEDDING_MODELS env or built-in list).
    Single build: pass --embedding or set EMBEDDING_MODEL.
    """
    parser = argparse.ArgumentParser(description="Build FAISS index(es) for one or more embedding models.")
    parser.add_argument("--embedding", help="Single embedding model to build (overrides multi)")
    parser.add_argument("--models", help="Comma-separated embedding models to build (overrides env)")
    args = parser.parse_args()

    print("--- Starting FAISS Index Build ---")

    # Decide which embeddings to build
    embeddings_to_build: List[str]
    if args.embedding:
        embeddings_to_build = [args.embedding]
    elif args.models:
        embeddings_to_build = _parse_models_csv(args.models)
    elif EMBEDDING_MODEL_NAME and not EMBEDDING_MODELS_ENV:
        # Respect single-model env only when EMBEDDING_MODELS not provided
        embeddings_to_build = [EMBEDDING_MODEL_NAME]
    else:
        if EMBEDDING_MODELS_ENV:
            embeddings_to_build = _parse_models_csv(EMBEDDING_MODELS_ENV)
        else:
            embeddings_to_build = DEFAULT_EMBEDDING_MODELS

    is_multi = len(embeddings_to_build) > 1
    if is_multi and INDEX_DIR:
        print(f"NOTE: Ignoring INDEX_DIR='{INDEX_DIR}' because multiple embeddings will be built.")

    # --- 1. Load Documents once ---
    docs = _load_documents()
    if not docs:
        return

    # --- 2. Split Documents into Chunks once ---
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    splits = text_splitter.split_documents(docs)
    print(f"Created {len(splits)} document chunks.")

    # --- 3. Build per embedding ---
    from langchain_ollama import OllamaEmbeddings
    from langchain_community.vectorstores import FAISS

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
            keep_alive=0,
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
