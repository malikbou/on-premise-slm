#!/usr/bin/env python3
"""
Base Testset Generator for UCL Computer Science Handbook

Generates a small evaluation dataset using local ragas 0.3.1 APIs.

Usage (dev):
  python src/testset/generate_testset.py \
    --document data/cs-handbook.md \
    --size 10 \
    --output testset/generated/base_dev10.json \
    --model gpt-4o-mini
"""

import argparse
import json
import os
import re
from datetime import datetime
from typing import List, Dict

import logging
from dotenv import load_dotenv

load_dotenv()

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import QueryDistribution
from ragas.run_config import RunConfig


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_and_chunk_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """Load and chunk the handbook markdown with structure-aware separators."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")

    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n# ", "\n## ", "\n### ", "\n\n", "\n", " ", ""],
        keep_separator=True,
    )

    chunks = splitter.split_documents(documents)
    filtered: List[Document] = []
    for chunk in chunks:
        content = chunk.page_content.strip()
        if (len(content) < 100) or (len(content.split()) < 20):
            continue
        content = re.sub(r"\[SKIPPING[^\]]*\]", "", content)
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)
        chunk.page_content = content.strip()
        filtered.append(chunk)

    logger.info("Created %d chunks after filtering", len(filtered))
    return filtered


def derive_personas_from_document(md_text: str) -> List[Dict[str, str]]:
    """Derive a minimal persona list from document hints.

    Note: Agents are expected to enhance this step. This is a safe placeholder
    to allow the generator to run now.
    """
    personas: List[Dict[str, str]] = []
    lowered = md_text.lower()
    if "visa" in lowered or "immigration" in lowered:
        personas.append({
            "name": "international_student",
            "description": "Student on a visa focused on compliance and attendance.",
            "role_description": "Concerned about immigration rules and academic progression."
        })
    if "part-time" in lowered or "part time" in lowered:
        personas.append({
            "name": "part_time_student",
            "description": "Student balancing work and studies, needs flexibility.",
            "role_description": "Juggles deadlines and scheduling constraints."
        })
    if "msc" in lowered or "postgraduate" in lowered:
        personas.append({
            "name": "postgraduate_student",
            "description": "Postgraduate focused on research/dissertation requirements.",
            "role_description": "Asks detailed questions about research procedures."
        })
    if not personas:
        personas = [{
            "name": "general_student",
            "description": "Typical CS student seeking guidance on policies.",
            "role_description": "Seeks clarity on deadlines, assessments, and support."
        }]
    return personas


def validate_and_convert(samples) -> List[Dict]:
    """Apply strict filters and convert to required schema."""
    output: List[Dict] = []
    for idx, sample in enumerate(samples):
        user_input = (getattr(sample, "user_input", "") or "").strip()
        reference = (getattr(sample, "reference", "") or "").strip()
        reference_contexts = getattr(sample, "reference_contexts", []) or []

        if len(user_input) < 10:
            continue
        if len(reference) < 10:
            continue
        if not reference_contexts:
            continue

        data = {
            "user_input": user_input,
            "reference_contexts": reference_contexts,
            "reference": reference,
            "sample_id": f"cs_handbook_{idx:03d}",
            "generated_at": datetime.now().isoformat(),
        }
        output.append(data)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a base testset using ragas 0.3.1")
    parser.add_argument("--document", default="data/cs-handbook.md")
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--output", default="testset/generated/base_dev10.json")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    args = parser.parse_args()

    llm = ChatOpenAI(model=args.model, temperature=0.4)
    embeddings = OpenAIEmbeddings()

    chunks = load_and_chunk_document(args.document, args.chunk_size, args.chunk_overlap)

    generator = TestsetGenerator.from_langchain(
        llm=llm,
        embedding_model=embeddings,
    )

    with open(args.document, "r", encoding="utf-8") as f:
        md_text = f.read()
    generator.persona_list = derive_personas_from_document(md_text)

    testset = generator.generate_with_langchain_docs(
        documents=chunks,
        testset_size=args.size,
        run_config=RunConfig(timeout=300, max_retries=3),
        with_debugging_logs=False,
        raise_exceptions=False,
        # use default query distribution from ragas 0.3.1
    )

    data = validate_and_convert(testset.samples)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved %s (%d samples)", args.output, len(data))


if __name__ == "__main__":
    main()
