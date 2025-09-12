# Using the wrong embedding models already, these are the ones I should be using:
    # - [ ] Qwen3-Embedding-0.6B-GGUF
    #     - [ ] ollama pull hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
    # - [ ] multilingual-e5-large-instruct
    #     - [ ] ollama pull yxchia/multilingual-e5-large-instruct
    # - [ ] bge-m3
    #     - [ ] ollama pull bge-m3

#  Embeddings map is all wrong, that

# Good if I just make it answer all the questions first then perform the evals because of timeout

#  I need to provide a better prompt when it performs the benchmarking, just as if it were a RAG application

"""
Rewriting the benchmarking script to evaluate Small Language Models (SLMs) and compare them to each other.

The embeddings I will be using are:
    - [ ] Qwen3-Embedding-0.6B-GGUF
    - [ ] multilingual-e5-large-instruct
    - [ ] bge-m3

The SLMs I will be using are:
    - [ ] Phi-4-mini-instruct
        - [ ] ollama pull hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M
    - [ ] Phi-3.5-mini-instruct
        - [ ] ollama pull hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M
    - [ ] Phi-3-mini-instruct
        - [ ] ollama pull hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf
    - [ ] Qwen2.5-3B-Instruct
        - [ ] ollama pull hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M
    - [ ] Falcon3-3B-Instruct-GGUF
        - [ ] ollama pull hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M
    - [ ] Llama-3.2-3B-Instruct-GGUF
        - [ ] ollama pull hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M

The LLMs I will be using are:
    - [ ] gpt-5
    - [ ] Gemini 2.5 Pro
    - [ ] Whatever other LLM is top in leaderboard
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from ragas import evaluate, EvaluationDataset
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from datasets import Dataset

def get_env_with_fallback(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with fallback to default."""
    return os.getenv(key, default)


def parse_key_value_list(kv_string: str) -> Dict[str, str]:
    """Parse comma-separated key=value pairs into dictionary."""
    if not kv_string:
        return {}

    result = {}
    for pair in kv_string.split(','):
        if '=' in pair:
            key, value = pair.split('=', 1)
            result[key.strip()] = value.strip()
    return result

def get_default_embedding_api_map(preset: str) -> Dict[str, str]:
    """Get default embedding API map based on preset."""
    if preset == "local":
        return {
            "bge-m3": "http://localhost:8001",
            "yxchia/multilingual-e5-large-instruct": "http://localhost:8003",
            "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0": "http://localhost:8002",
        }
    elif preset == "vm":
        return {
            "bge-m3": "http://rag-api-bge:8000",
            "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0": "http://rag-api-qwen3:8000",
            "yxchia/multilingual-e5-large-instruct": "http://rag-api-e5:8000",
        }
    else:
        return {}

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all required flags."""
    parser = argparse.ArgumentParser(
        description="Simple RAG benchmarking script",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Presets
    parser.add_argument(
        "--preset",
        choices=["local", "vm"],
        help="Environment preset (local: localhost ports, vm: Docker service DNS)"
    )

    # Core configuration
    parser.add_argument(
        "--testset",
        default=get_env_with_fallback("TESTSET_FILE", "data/testset/cs-handbook_testset_gpt-4.1-mini_20250912_130930.json"),
        help="Path to testset file"
    )

    parser.add_argument(
        "--num-questions",
        type=int,
        default=int(get_env_with_fallback("NUM_QUESTIONS_TO_TEST", "10")),
        help="Number of questions to test"
    )

    parser.add_argument(
        "--embeddings",
        default=get_env_with_fallback("EMBEDDING_MODELS", "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0,bge-m3,yxchia/multilingual-e5-large-instruct"),
        help="Comma-separated embedding models"
    )

    parser.add_argument(
        "--embedding-api-map",
        default=get_env_with_fallback("EMBEDDING_API_MAP", ""),
        help="Comma-separated key=value API mappings"
    )

    # Default models from ollama list
    default_models = ",".join([
        "ollama/hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf",
        "ollama/hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M",
        "ollama/hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M",
        "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M",
        "ollama/hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M",
        "ollama/hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
        "azure-gpt5"
    ])

    parser.add_argument(
        "--models",
        default=get_env_with_fallback("MODELS_TO_TEST", default_models),
        help="Comma-separated models to test"
    )

    # API endpoints
    parser.add_argument(
        "--ollama-base",
        default=get_env_with_fallback("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Ollama base URL for RAGAS embeddings"
    )

    parser.add_argument(
        "--litellm",
        default=get_env_with_fallback("LITELLM_API_BASE", "http://localhost:4000"),
        help="LiteLLM API base URL for judge"
    )

    # Output configuration
    parser.add_argument(
        "--results-dir",
        default=get_env_with_fallback("RESULTS_DIR", "results/benchmarking"),
        help="Results directory"
    )

    parser.add_argument(
        "--run-stamp",
        default=get_env_with_fallback("RUN_STAMP", datetime.now().strftime("%Y%m%d_%H%M%S")),
        help="Run timestamp/identifier"
    )

    # Mode control
    parser.add_argument(
        "--mode",
        choices=["all", "generate", "evaluate"],
        default=get_env_with_fallback("MODE", "all"),
        help="Execution mode"
    )

    # Ollama lifecycle
    parser.add_argument(
        "--print-ollama-ps",
        action="store_true",
        help="Print Ollama models before/after each run"
    )

    parser.add_argument(
        "--stop-after",
        action="store_true",
        help="Stop Ollama model after answering questions"
    )

    parser.add_argument(
        "--stop-mode",
        choices=["host", "container"],
        help="How to stop Ollama models (auto-detected from preset if not set)"
    )

    parser.add_argument(
        "--ollama-container",
        default="ollama",
        help="Ollama container name for container stop mode"
    )

    return parser

def apply_preset_defaults(args: argparse.Namespace) -> None:
    """Apply preset defaults where CLI args weren't provided."""
    if not args.preset:
        return

    # Set API endpoints if not explicitly provided
    if args.ollama_base == "http://localhost:11434" and args.preset == "vm":
        args.ollama_base = "http://ollama:11434"
    elif args.ollama_base == "http://localhost:11434" and args.preset == "local":
        args.ollama_base = "http://localhost:11434"

    if args.litellm == "http://localhost:4000" and args.preset == "vm":
        args.litellm = "http://litellm:4000"
    elif args.litellm == "http://localhost:4000" and args.preset == "local":
        args.litellm = "http://localhost:4000"

    # Set embedding API map if not provided
    if not args.embedding_api_map:
        default_map = get_default_embedding_api_map(args.preset)
        # Convert back to string format
        args.embedding_api_map = ",".join([f"{k}={v}" for k, v in default_map.items()])

    # Set stop mode based on preset if not provided
    if not args.stop_mode:
        args.stop_mode = "host" if args.preset == "local" else "container"

def load_testset(testset_path: str, num_questions: int) -> List[Dict]:
    """Load and slice testset."""
    print(f"Loading testset from {testset_path}")

    with open(testset_path, 'r') as f:
        data = json.load(f)

    questions = data[:num_questions] if num_questions > 0 else data
    print(f"Loaded {len(questions)} questions")
    return questions

def print_ollama_models(ollama_base: str) -> None:
    """Print currently loaded Ollama models."""
    try:
        response = requests.get(f"{ollama_base}/api/ps", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                print("Loaded Ollama models:")
                for model in models:
                    print(f"  - {model.get('name', 'unknown')}")
            else:
                print("No Ollama models currently loaded")
        else:
            print(f"Failed to get Ollama models: {response.status_code}")
    except Exception as e:
        print(f"Error checking Ollama models: {e}")


def stop_ollama_model(model_name: str, stop_mode: str, container_name: str) -> None:
    """Stop an Ollama model."""
    # Extract just the model part (remove ollama/ prefix)
    if model_name.startswith("ollama/"):
        ollama_model = model_name[7:]  # Remove "ollama/" prefix
    else:
        return  # Not an Ollama model

    try:
        if stop_mode == "host":
            cmd = ["ollama", "stop", ollama_model]
        else:  # container
            cmd = ["docker", "exec", container_name, "ollama", "stop", ollama_model]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"Stopped model: {ollama_model}")
        else:
            print(f"Failed to stop {ollama_model}: {result.stderr}")
    except Exception as e:
        print(f"Error stopping {ollama_model}: {e}")

def generate_answers(args: argparse.Namespace) -> None:
    """Generate answers for all embedding/model combinations."""
    print(f"\n=== GENERATE MODE ===")

    # Load testset
    questions = load_testset(args.testset, args.num_questions)

    # Parse embeddings and models
    embeddings = [e.strip() for e in args.embeddings.split(',')]
    models = [m.strip() for m in args.models.split(',')]

    # Parse embedding API map
    api_map = parse_key_value_list(args.embedding_api_map)

    # Create results directory
    results_dir = Path(args.results_dir) / args.run_stamp
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"Results will be saved to: {results_dir}")
    print(f"Testing {len(embeddings)} embeddings × {len(models)} models = {len(embeddings) * len(models)} combinations")

    for embedding in embeddings:
        if embedding not in api_map:
            print(f"Warning: No API mapping for embedding '{embedding}', skipping")
            continue

        api_base = api_map[embedding]
        api_url = f"{api_base}/query"

        print(f"\n--- Processing embedding: {embedding} ---")
        print(f"API URL: {api_url}")

        for model in models:
            print(f"\nTesting model: {model}")

            if model.startswith("ollama/"):
                print("Models before:")
                print_ollama_models(args.ollama_base)

            # Generate answers
            answers = []
            for i, question_data in enumerate(questions):
                question = question_data.get("user_input", "")
                reference = question_data.get("reference", "")

                try:
                    # Make API call
                    payload = {"question": question, "model_name": model}
                    response = requests.post(api_url, json=payload, timeout=120)

                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("answer", "")

                        # Print answer snippet for immediate feedback
                        snippet = (answer or "").strip().replace("\n", " ")[:60]
                        print(f"    Q{i+1}/{len(questions)}: {snippet}...")

                        answer_record = {
                            "user_input": question,
                            "response": answer,
                            # "retrieved_contexts": result.get("contexts", []),
                            "retrieved_contexts": [doc.get('page_content', "") for doc in result.get('source_documents', [])],
                            "reference": reference
                        }
                    else:
                        print(f"  Question {i+1}: API error {response.status_code}")
                        answer_record = {
                            "user_input": question,
                            "response": "",
                            "retrieved_contexts": [],
                            "reference": reference
                        }

                except Exception as e:
                    print(f"  Question {i+1}: Error - {e}")
                    answer_record = {
                        "user_input": question,
                        "response": "",
                        "retrieved_contexts": [],
                        "reference": reference
                    }

                answers.append(answer_record)


            # Save answers
            filename = f"answers__{embedding.replace('/', '_')}__{model.replace('/', '_')}.json"
            filepath = results_dir / filename

            with open(filepath, 'w') as f:
                json.dump(answers, f, indent=2)

            print(f"Saved answers to: {filename}")

            if model.startswith("ollama/"):
                print("Models after:")
                print_ollama_models(args.ollama_base)

            if args.stop_after and model.startswith("ollama/"):
                stop_ollama_model(model, args.stop_mode, args.ollama_container)

                # Check models after stop to verify it worked
                print("Models after stop:")
                print_ollama_models(args.ollama_base)

def evaluate_answers(args: argparse.Namespace) -> None:
    """Evaluate existing answer files using RAGAS."""
    print(f"\n=== EVALUATE MODE ===")

    results_dir = Path(args.results_dir) / args.run_stamp

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return

    # Find all answer files
    answer_files = list(results_dir.glob("answers__*.json"))

    if not answer_files:
        print(f"No answer files found in {results_dir}")
        return

    print(f"Found {len(answer_files)} answer files to evaluate")

    # Setup RAGAS components
    judge_llm = ChatOpenAI(
        # model="azure-gpt5",
        model="gpt-4o-mini",
        api_key="dummy",  # LiteLLM handles this
        base_url=f"{args.litellm}/v1"
    )

    ragas_embeddings = OpenAIEmbeddings(
        openai_api_key="dummy",  # LiteLLM handles this
        openai_api_base=f"{args.litellm}/v1"
    )

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    summary_data = {}

    for answer_file in answer_files:
        print(f"\nEvaluating: {answer_file.name}")

        # Extract embedding and model from filename
        parts = answer_file.stem.split("__")
        if len(parts) >= 3:
            embedding = parts[1]
            model = "__".join(parts[2:])  # Handle models with underscores
        else:
            print(f"Skipping malformed filename: {answer_file.name}")
            continue

        try:
            # Load answers
            with open(answer_file, 'r') as f:
                answers = json.load(f)

            # Filter out empty answers
            valid_answers = [
                ans for ans in answers
                if ans.get("response", "").strip() and ans.get("retrieved_contexts")
            ]

            if not valid_answers:
                print(f"  No valid answers found, skipping evaluation")
                summary_data[f"{embedding}__{model}"] = {"error": "no_valid_answers"}
                continue

            print(f"  Evaluating {len(valid_answers)}/{len(answers)} valid answers")

            # Create RAGAS dataset
            dataset = Dataset.from_dict({
                "question": [ans["user_input"] for ans in valid_answers],
                "answer": [ans["response"] for ans in valid_answers],
                "contexts": [ans["retrieved_contexts"] for ans in valid_answers],
                "ground_truth": [ans["reference"] for ans in valid_answers]
            })

            # Run evaluation
            result = evaluate(
                dataset,
                metrics=metrics,
                llm=judge_llm,
                embeddings=ragas_embeddings
            )

            # Convert to serializable format (simple approach from benchmark.py)
            scores = {}

            if hasattr(result, "to_pandas"):
                # Modern RAGAS version - use pandas dataframe
                df = result.to_pandas()
                for col in df.select_dtypes(include="number").columns:
                    score = float(df[col].mean())
                    scores[col] = score
            elif hasattr(result, 'items'):
                # Old RAGAS version - result is dict-like
                for metric_name, score in result.items():
                    if hasattr(score, 'item'):  # Handle numpy types
                        scores[metric_name] = float(score.item())
                    else:
                        scores[metric_name] = float(score)
            else:
                # Fallback
                scores = {"result": str(result)}

            print(f"  Scores: {scores}")

            # Save individual scores
            scores_file = results_dir / f"scores__{embedding.replace('/', '_')}__{model.replace('/', '_')}.json"
            with open(scores_file, 'w') as f:
                json.dump(scores, f, indent=2)

            summary_data[f"{embedding}__{model}"] = scores

        except Exception as e:
            print(f"  Evaluation failed: {e}")
            summary_data[f"{embedding}__{model}"] = {"error": str(e)}

    # Save summary
    summary_file = results_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary_data, f, indent=2)

    print(f"\nSummary saved to: {summary_file}")

def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Apply preset defaults
    apply_preset_defaults(args)

    print(f"Simple RAG Benchmarker")
    print(f"Mode: {args.mode}")
    print(f"Preset: {args.preset or 'none'}")
    print(f"Results: {args.results_dir}/{args.run_stamp}")

    if args.mode in ["all", "generate"]:
        generate_answers(args)

    if args.mode in ["all", "evaluate"]:
        pass
        evaluate_answers(args)

    print(f"\nBenchmarking complete!")


if __name__ == "__main__":
    main()
