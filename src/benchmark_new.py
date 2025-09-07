#!/usr/bin/env python3
"""
Simple RAG Benchmarking Script

Environment-driven benchmarking for RAG answer quality across multiple
retrieval embeddings and generators (local SLMs via Ollama and cloud models via LiteLLM).

Designed to run unchanged on Mac (localhost) and VM (Docker network).
"""

import os
import argparse
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from ragas import evaluate, EvaluationDataset
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)
from langchain_ollama import OllamaEmbeddings
from langchain_openai import ChatOpenAI


def get_env_required(key: str) -> str:
    """Get required environment variable or exit with error."""
    value = os.getenv(key)
    if not value:
        print(f"ERROR: Required environment variable {key} not set")
        exit(1)
    return value


def get_env_default(key: str, default: str) -> str:
    """Get environment variable with default value."""
    return os.getenv(key, default)


def parse_comma_separated(value: str) -> List[str]:
    """Parse comma-separated string into list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_api_map(value: str) -> Dict[str, str]:
    """Parse comma-separated key=value pairs into dictionary."""
    result = {}
    for pair in parse_comma_separated(value):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filenames."""
    return (
        text.replace("/", "_")
        .replace(":", "_")
        .replace(" ", "_")
        .replace("*", "_")
    )


def ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def get_preset_defaults(preset: Optional[str]) -> tuple[str, Optional[str], Optional[str]]:
    """Return (embedding_api_map_str, ollama_base, litellm_base) defaults for a preset."""
    if preset == "local":
        # Localhost ports for the three embeddings
        api_map = (
            "nomic-embed-text=http://localhost:8002,"
            "bge-m3=http://localhost:8001,"
            "yxchia/multilingual-e5-large-instruct=http://localhost:8003"
        )
        return api_map, "http://localhost:11434", "http://localhost:4000"
    if preset == "vm":
        # Compose service DNS names
        api_map = (
            "bge-m3=http://rag-api-bge:8000,"
            "nomic-embed-text=http://rag-api-nomic:8000,"
            "yxchia/multilingual-e5-large-instruct=http://rag-api-e5:8000"
        )
        return api_map, "http://ollama:11434", "http://litellm:4000"
    return "", None, None


def parse_cli_and_env() -> Dict[str, Any]:
    """Parse CLI args with env fallback and sensible defaults."""
    parser = argparse.ArgumentParser(description="Simple RAG Benchmarker (CLI-first)")
    parser.add_argument("--preset", choices=["local", "vm"], help="Preconfigure endpoints for local or vm")
    parser.add_argument("--testset", help="Path to testset JSON file (TESTSET_FILE)")
    parser.add_argument("--num-questions", type=int, help="Limit number of questions (NUM_QUESTIONS_TO_TEST)")
    parser.add_argument("--embeddings", help="Comma-separated embeddings (EMBEDDING_MODELS)")
    parser.add_argument("--embedding-api-map", help="Comma-separated key=value list (EMBEDDING_API_MAP)")
    parser.add_argument("--models", help="Comma-separated generators (MODELS_TO_TEST)")
    parser.add_argument("--ollama-base", help="Ollama base URL for RAGAS embeddings (OLLAMA_BASE_URL)")
    parser.add_argument("--litellm", help="LiteLLM base URL for judge (LITELLM_API_BASE)")
    parser.add_argument("--results-dir", help="Results directory (RESULTS_DIR)")
    parser.add_argument("--run-stamp", help="Run stamp (RUN_STAMP)")

    args = parser.parse_args()

    # Preset defaults
    preset_api_map, preset_ollama, preset_litellm = get_preset_defaults(args.preset if hasattr(args, "preset") else None)

    # Defaults per user preference
    default_embeddings = "nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct"
    default_models = (
        "ollama/hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M," \
        "ollama/hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M," \
        "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M," \
        "ollama/hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M," \
        "ollama/hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M," \
        "azure-gpt5"
    )

    cfg: Dict[str, Any] = {}
    cfg["testset_file"] = args.testset or os.getenv("TESTSET_FILE", "data/testset/baseline_7_questions.json")
    cfg["num_questions"] = int(args.num_questions if args.num_questions is not None else os.getenv("NUM_QUESTIONS_TO_TEST", "7"))
    cfg["embedding_models_str"] = args.embeddings or os.getenv("EMBEDDING_MODELS", default_embeddings)

    # CLI > ENV > PRESET for embedding_api_map
    cfg["embedding_api_map_str"] = (
        (args.embedding_api_map if args.embedding_api_map else None)
        or os.getenv("EMBEDDING_API_MAP")
        or preset_api_map
        or ""
    )

    cfg["models_to_test_str"] = args.models or os.getenv("MODELS_TO_TEST", default_models)
    cfg["ollama_base_url"] = args.ollama_base or os.getenv("OLLAMA_BASE_URL") or preset_ollama or "http://localhost:11434"
    cfg["litellm_api_base"] = args.litellm or os.getenv("LITELLM_API_BASE") or preset_litellm or "http://localhost:4000"
    cfg["results_dir"] = args.results_dir or os.getenv("RESULTS_DIR", "results")
    cfg["run_stamp"] = args.run_stamp or os.getenv("RUN_STAMP", datetime.now().strftime("%Y%m%d_%H%M%S"))

    # Optional fallback for base RAG API if a mapping entry is missing
    cfg["rag_api_base"] = os.getenv("RAG_API_BASE", "http://localhost:8000")
    return cfg


def load_testset(file_path: str, num_questions: int) -> Optional[List[Dict[str, Any]]]:
    """Load testset with memory-efficient slicing."""
    try:
        with open(file_path, 'r') as f:
            testset_data = json.load(f)

        # Memory-efficient slicing
        if num_questions > 0:
            testset_data = testset_data[:num_questions]

        print(f"Loaded {len(testset_data)} question(s) from {file_path}")
        return testset_data

    except Exception as e:
        print(f"ERROR: Could not load testset '{file_path}': {e}")
        return None


def generate_answers(questions: List[str], api_url: str, model_name: str) -> tuple[List[str], List[List[str]]]:
    """Generate answers sequentially for all questions."""
    answers = []
    contexts = []

    print(f"  Generating {len(questions)} answers with {model_name}...")

    for i, question in enumerate(questions, 1):
        try:
            response = requests.post(
                api_url,
                json={"question": question, "model_name": model_name},
                timeout=600
            )
            response.raise_for_status()
            data = response.json()

            answer = data.get('answer', "")
            question_contexts = [doc.get('page_content', "") for doc in data.get('source_documents', [])]

            answers.append(answer)
            contexts.append(question_contexts)

            # Progress indicator
            snippet = (answer or "").strip().replace("\n", " ")[:60]
            print(f"    Q{i}/{len(questions)}: {snippet}...")

        except Exception as e:
            print(f"    Q{i}/{len(questions)}: ERROR - {str(e)[:60]}...")
            answers.append("")
            contexts.append([])

    return answers, contexts


def save_answers(answers_data: List[Dict[str, Any]], file_path: str) -> bool:
    """Save raw answers to JSON file."""
    try:
        with open(file_path, "w") as f:
            json.dump(answers_data, f, indent=2)
        print(f"  Saved answers to {file_path}")
        return True
    except Exception as e:
        print(f"  WARNING: Failed to save answers to {file_path}: {e}")
        return False


def build_evaluation_dataset(testset_data: List[Dict[str, Any]], answers: List[str], contexts: List[List[str]]) -> Optional[EvaluationDataset]:
    """Build guarded EvaluationDataset, skipping empty answers."""
    try:
        valid_records = []

        for i, item in enumerate(testset_data):
            # Skip empty answers to avoid metric errors
            if not (answers[i] or "").strip():
                continue

            valid_records.append({
                "user_input": item['user_input'],
                "response": answers[i],
                "retrieved_contexts": contexts[i],
                "reference": item['reference'],
            })

        if not valid_records:
            print("  WARNING: No valid records for evaluation (all answers empty)")
            return None

        print(f"  Built evaluation dataset with {len(valid_records)} valid records")
        return EvaluationDataset.from_list(valid_records)

    except Exception as e:
        print(f"  ERROR: Failed to create evaluation dataset: {e}")
        return None


def evaluate_ragas_metrics(dataset: EvaluationDataset, judge_llm, ragas_embeddings) -> Dict[str, Any]:
    """Evaluate RAGAS metrics with error handling."""
    try:
        print("  Evaluating RAGAS metrics...")

        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=judge_llm,
            embeddings=ragas_embeddings,
            raise_exceptions=False,
            batch_size=1,
        )

        # Extract scores
        scores = {}
        if hasattr(result, "to_pandas"):
            df = result.to_pandas()
            for col in df.select_dtypes(include="number").columns:
                score = float(df[col].mean())
                scores[col] = score
                print(f"    {col}: {score:.4f}")
        else:
            scores = {"result": str(result)}

        return scores

    except Exception as e:
        print(f"  ERROR: RAGAS evaluation failed: {e}")
        return {"error": str(e)}


def save_scores(scores: Dict[str, Any], file_path: str) -> bool:
    """Save scores to JSON file."""
    try:
        with open(file_path, "w") as f:
            json.dump(scores, f, indent=2)
        print(f"  Saved scores to {file_path}")
        return True
    except Exception as e:
        print(f"  WARNING: Failed to save scores to {file_path}: {e}")
        return False


def update_summary(summary: Dict[str, Any], embedding_model: str, model_name: str, scores: Dict[str, Any], summary_file: str) -> None:
    """Update and save summary file."""
    try:
        summary.setdefault(embedding_model, {})[model_name] = scores

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"  Updated summary: {summary_file}")
    except Exception as e:
        print(f"  WARNING: Failed to update summary: {e}")


def main():
    """Main benchmarking function."""
    print("--- Simple RAG Benchmarking ---")

    # === CLI + ENV Configuration ===
    cfg = parse_cli_and_env()
    testset_file = cfg["testset_file"]
    num_questions = cfg["num_questions"]
    embedding_models = parse_comma_separated(cfg["embedding_models_str"])
    embedding_api_map = parse_api_map(cfg["embedding_api_map_str"]) if cfg["embedding_api_map_str"] else {}
    models_to_test = parse_comma_separated(cfg["models_to_test_str"])
    ollama_base_url = cfg["ollama_base_url"]
    litellm_api_base = cfg["litellm_api_base"]
    rag_api_base = cfg["rag_api_base"]
    results_dir = cfg["results_dir"]
    run_stamp = cfg["run_stamp"]

    run_dir = os.path.join(results_dir, run_stamp)
    ensure_dir(run_dir)

    print(f"Config: {num_questions} questions, {len(embedding_models)} embeddings, {len(models_to_test)} models")
    print(f"Results: {run_dir}")

    # === Load Testset ===
    print(f"\nLoading testset from {testset_file}...")
    testset_data = load_testset(testset_file, num_questions)
    if not testset_data:
        return

    # === Run Benchmarks ===
    summary = {}
    summary_file = os.path.join(run_dir, "summary.json")

    for embedding_model in embedding_models:
        print(f"\n=== Retrieval Embedding: {embedding_model} ===")

        # Resolve API URL for this embedding
        api_base = embedding_api_map.get(embedding_model, rag_api_base)
        api_url = api_base.rstrip("/") + "/query"
        print(f"API: {api_url}")

        for model_name in models_to_test:
            print(f"\n--- Model: {model_name} ---")

            # Extract questions for processing
            questions = [item['user_input'] for item in testset_data]

            # Generate answers
            answers, contexts = generate_answers(questions, api_url, model_name)

            # Save raw answers
            answers_data = []
            for i, item in enumerate(testset_data):
                answers_data.append({
                    "user_input": item['user_input'],
                    "response": answers[i],
                    "retrieved_contexts": contexts[i],
                    "reference": item['reference'],
                })

            answers_filename = f"answers__{sanitize_filename(embedding_model)}__{sanitize_filename(model_name)}.json"
            answers_path = os.path.join(run_dir, answers_filename)
            save_answers(answers_data, answers_path)

            # Build evaluation dataset
            evaluation_dataset = build_evaluation_dataset(testset_data, answers, contexts)

            if evaluation_dataset is None:
                scores = {"error": "no_valid_answers"}
                print("  Skipping evaluation (no valid answers)")
            else:
                # Setup RAGAS components
                ragas_embeddings = OllamaEmbeddings(
                    model=embedding_model,
                    base_url=ollama_base_url,
                    keep_alive=0,
                )

                judge_llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    openai_api_base=litellm_api_base,
                    openai_api_key=os.getenv("OPENAI_API_KEY", "anything"),
                    temperature=0,
                    timeout=600,
                )

                # Evaluate metrics
                scores = evaluate_ragas_metrics(evaluation_dataset, judge_llm, ragas_embeddings)

            # Save scores
            scores_filename = f"scores__{sanitize_filename(embedding_model)}__{sanitize_filename(model_name)}.json"
            scores_path = os.path.join(run_dir, scores_filename)
            save_scores(scores, scores_path)

            # Update summary
            update_summary(summary, embedding_model, model_name, scores, summary_file)

            print(f"  Completed: {embedding_model} + {model_name}")

    print(f"\n--- Benchmark Complete ---")
    print(f"Results saved to: {run_dir}")
    print(f"Summary: {summary_file}")

    # Print final summary
    print("\n--- Summary ---")
    for embedding_model, by_model in summary.items():
        print(f"\n{embedding_model}:")
        for model_name, results in by_model.items():
            if "error" in results:
                print(f"  {model_name}: ERROR - {results['error']}")
            else:
                score_strs = [f"{k}={v:.3f}" for k, v in results.items() if isinstance(v, (int, float))]
                print(f"  {model_name}: {', '.join(score_strs)}")


if __name__ == "__main__":
    main()
