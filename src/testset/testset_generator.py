import os
import re
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ragas.testset import TestsetGenerator
from ragas.testset.persona import Persona
from ragas.run_config import RunConfig

# Load environment variables from a .env file
load_dotenv()

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_and_chunk_document(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """
    Loads a markdown document and splits it into structured, filtered chunks.
    This function uses markdown headings as primary separators for more coherent chunks
    and filters out chunks that are too short to be useful.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found at: {file_path}")

    logger.info(f"Loading document from {file_path}...")
    # Using TextLoader as it's simple and effective for markdown
    loader = TextLoader(file_path, encoding="utf-8")
    documents = loader.load()

    logger.info("Splitting document into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""], # Prioritize splitting on headings
        keep_separator=True,
    )

    chunks = splitter.split_documents(documents)

    # Filter out very short or irrelevant chunks to improve question quality
    filtered_chunks: List[Document] = []
    for chunk in chunks:
        content = chunk.page_content.strip()
        # Remove any placeholder text if it exists
        content = re.sub(r"\[SKIPPING[^\]]*\]", "", content)
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content) # Normalize newlines

        # Keep chunks that have a reasonable amount of content
        if len(content) > 100 and len(content.split()) > 20:
            chunk.page_content = content
            filtered_chunks.append(chunk)

    logger.info(f"Created {len(filtered_chunks)} chunks after filtering (from an initial {len(chunks)}).")
    return filtered_chunks


def derive_personas_from_document(md_text: str) -> List[Persona]:
    """
    Derives a list of Persona objects based on keywords found in the document text.
    This creates more realistic and targeted questions for the test set.
    """
    logger.info("Deriving personas from document content...")
    personas: List[Persona] = []
    lowered_text = md_text.lower()

    if "undergraduate" in lowered_text or "bsc" in lowered_text:
        personas.append(Persona(
            name="first_year_undergraduate",
            role_description="A new undergraduate student trying to understand university life, module selection, and where to find support services."
        ))
    if "postgraduate" in lowered_text or "msc" in lowered_text or "dissertation" in lowered_text:
        personas.append(Persona(
            name="postgraduate_student",
            role_description="A postgraduate student focused on programme structure, dissertation requirements, and research ethics."
        ))
    if "visa" in lowered_text or "international" in lowered_text:
        personas.append(Persona(
            name="international_student",
            role_description="An international student concerned with visa regulations, accommodation, and settling into the UK."
        ))
    if "faculty" in lowered_text or "staff" in lowered_text:
         personas.append(Persona(
            name="academic_staff_member",
            role_description="A faculty member or personal tutor looking for specific details on departmental policies, student support procedures, and academic regulations to advise students accurately."
        ))

    # Add a default persona if none are found
    if not personas:
        personas.append(Persona(
            name="general_student",
            role_description="A typical UCL student seeking guidance on academic policies, deadlines, and available resources."
        ))

    logger.info(f"Derived {len(personas)} personas: {[p.name for p in personas]}")
    return personas

def validate_and_convert_to_json(testset) -> List[Dict]:
    """
    Filters generated samples for quality and converts them to the desired JSON schema.
    This ensures compatibility with your benchmarking script.
    """
    logger.info(f"Validating and converting {len(testset.samples)} generated samples...")
    output_samples: List[Dict] = []
    for idx, sample in enumerate(testset.samples):
        # Ensure all required fields are present and not empty
        question = getattr(sample.eval_sample, "user_input", "").strip()
        answer = getattr(sample.eval_sample, "reference", "").strip()
        contexts = getattr(sample.eval_sample, "reference_contexts", [])

        if len(question) < 15 or len(answer) < 15 or not contexts:
            logger.warning(f"Skipping low-quality sample: {question}")
            continue

        data = {
            "user_input": question,
            "reference_contexts": contexts,
            "reference": answer,
            "synthesizer_name": getattr(sample, "synthesizer_name", "unknown"),
            "sample_id": f"cs_handbook_{datetime.now().strftime('%Y%m%d')}_{idx:03d}",
            "generated_at": datetime.now().isoformat(),
        }
        output_samples.append(data)

    logger.info(f"Returning {len(output_samples)} valid samples.")
    return output_samples

def main() -> None:
    """
    Main execution function that parses arguments and runs the test set generation pipeline.
    """
    parser = argparse.ArgumentParser(description="Generate a high-quality testset for a RAG system using Ragas.")
    parser.add_argument("--document", type=str, default="data/cs-handbook-gemini-cleaned.md", help="Path to the markdown document.")
    parser.add_argument("--size", type=int, default=100, help="The number of questions to generate for the test set.")
    parser.add_argument("--output", type=str, default="data/output/ucl_cs_handbook_testset.json", help="Path to save the output JSON file.")
    parser.add_argument("--model", type=str, default="gpt-4.1-mini", help="The OpenAI model to use for generation.")
    parser.add_argument("--chunk-size", type=int, default=1000, help="The size of each document chunk.")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="The overlap between document chunks.")
    args = parser.parse_args()

    # Initialize OpenAI models
    llm = ChatOpenAI(model=args.model, temperature=0.3)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # Load and process the document
    chunks = load_and_chunk_document(args.document, args.chunk_size, args.chunk_overlap)

    # Initialize the TestsetGenerator
    generator = TestsetGenerator.from_langchain(
        llm=llm,
        embedding_model=embeddings,
    )

    # Derive and set personas for targeted question generation
    with open(args.document, "r", encoding="utf-8") as f:
        full_text = f.read()
    generator.persona_list = derive_personas_from_document(full_text)

    # Generate the test set
    logger.info(f"Generating a test set of {args.size} questions using the '{args.model}' model. This may take a while...")
    testset = generator.generate_with_langchain_docs(
        documents=chunks,
        testset_size=args.size,
        # run_config=RunConfig(timeout=600, max_retries=5), # Add robustness
        raise_exceptions=False, # Continue generation even if some samples fail
    )

    # Validate and format the output
    output_data = validate_and_convert_to_json(testset)

    # Save the test set to a JSON file
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully saved {len(output_data)} samples to {args.output}")

if __name__ == "__main__":
    main()
