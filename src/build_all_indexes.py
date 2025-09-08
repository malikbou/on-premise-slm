#!/usr/bin/env python3
"""
Multi-embedding index builder that builds FAISS indexes for all configured embedding models.
This script automates the process of building indexes for multiple embedding models,
eliminating the need to manually specify each model.
"""
import os
import subprocess
import sys
from typing import List

def get_embedding_models() -> List[str]:
    """Get embedding models from environment or use defaults from docker-compose.yml."""
    default_models = [
        "bge-m3",
        "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0",
        "yxchia/multilingual-e5-large-instruct"
    ]
    models_str = os.getenv("EMBEDDING_MODELS", ",".join(default_models))
    return [model.strip() for model in models_str.split(",")]

def build_index_for_model(model: str) -> bool:
    """Build index for a specific embedding model using the existing build_index.py script."""
    print(f"\n{'='*60}")
    print(f"Building index for embedding model: {model}")
    print(f"{'='*60}")

    env = os.environ.copy()
    env["EMBEDDING_MODEL"] = model

    try:
        result = subprocess.run(
            ["python", "src/build_index.py"],
            env=env,
            check=True,
            capture_output=False
        )
        print(f"Successfully built index for {model}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to build index for {model}: {e}")
        return False

def main():
    """Build indexes for all embedding models."""
    models = get_embedding_models()
    print(f"Building indexes for {len(models)} embedding models...")
    print(f"Models: {', '.join(models)}")

    success_count = 0
    failed_models = []

    for model in models:
        if build_index_for_model(model):
            success_count += 1
        else:
            failed_models.append(model)

    print(f"\n{'='*60}")
    print(f"Index building complete: {success_count}/{len(models)} successful")
    if failed_models:
        print(f"Failed models: {', '.join(failed_models)}")
    print(f"{'='*60}")

    if success_count < len(models):
        sys.exit(1)

if __name__ == "__main__":
    main()
