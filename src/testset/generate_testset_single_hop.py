import os
import re
import json
import argparse
from dataclasses import dataclass
import typing as t
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Modern Ragas imports for single-hop generation
from ragas.testset import TestsetGenerator
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.persona import Persona
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# Single-hop synthesizer imports based on documentation
from ragas.testset.synthesizers.single_hop import (
    SingleHopQuerySynthesizer,
    SingleHopScenario,
)
from ragas.testset.synthesizers.prompts import (
    ThemesPersonasInput,
    ThemesPersonasMatchingPrompt,
)

from ragas.testset.transforms import (
    apply_transforms,
    HeadlinesExtractor,
    HeadlineSplitter,
    KeyphrasesExtractor,
)
from ragas.run_config import RunConfig

# Load environment variables
load_dotenv()

# Patterns to remove irrelevant content from the handbook
CRUFT_PATTERNS = [
    r"\*\*TABLE MISSING: Programme Info\*\*",
    r"On this page",
    r"Handbook Index",
    r"SharePoint",
    r"\[SKIPPING[^\]]*\]",
    r"\(https://search2.ucl.ac.uk/s/search.html?[^\)]+\)",
]


# --- Custom Single-Hop Synthesizer Implementation ---
@dataclass
class UCLSingleHopQuerySynthesizer(SingleHopQuerySynthesizer):
    """
    Custom Single-Hop Synthesizer optimized for UCL CS Handbook content.
    Based on official Ragas documentation pattern.
    """

    theme_persona_matching_prompt = ThemesPersonasMatchingPrompt()

    async def _generate_scenarios(
        self,
        n: int,
        knowledge_graph: KnowledgeGraph,
        persona_list: List[Persona],
        callbacks=None,
    ) -> t.List[SingleHopScenario]:

        property_name = "keyphrases"

        # Find all nodes with keyphrases (CHUNK nodes after HeadlineSplitter)
        qualified_nodes = []
        total_chunk_nodes = 0

        for node in knowledge_graph.nodes:
            if node.type.name == "CHUNK":
                total_chunk_nodes += 1
                if node.get_property(property_name):
                    qualified_nodes.append(node)

        if not qualified_nodes:
            print("⚠️ No qualified CHUNK nodes found with keyphrases")
            return []

        print(f"✅ Found {len(qualified_nodes)} qualified nodes (out of {total_chunk_nodes} CHUNK nodes) for single-hop generation")

        # Calculate samples per node
        number_of_samples_per_node = max(1, n // len(qualified_nodes))

        scenarios = []
        for node in qualified_nodes:
            if len(scenarios) >= n:
                break

            # Extract themes (keyphrases) from the node
            themes = node.properties.get(property_name, [])
            if not themes:
                continue

            # Match themes with personas
            prompt_input = ThemesPersonasInput(themes=themes, personas=persona_list)
            persona_concepts = await self.theme_persona_matching_prompt.generate(
                data=prompt_input, llm=self.llm, callbacks=callbacks
            )

            # Prepare scenario combinations
            base_scenarios = self.prepare_combinations(
                node,
                themes,
                personas=persona_list,
                persona_concepts=persona_concepts.mapping,
            )

            # Sample the required number of scenarios
            sampled_scenarios = self.sample_combinations(
                base_scenarios, number_of_samples_per_node
            )
            scenarios.extend(sampled_scenarios)

        return scenarios[:n]  # Ensure we don't exceed requested number


def create_knowledge_graph(file_path: str, llm: LangchainLLMWrapper) -> KnowledgeGraph:
    """
    Builds a Knowledge Graph optimized for single-hop query generation.
    Note: No OverlapScoreBuilder needed for single-hop queries.
    """
    print("🚀 Phase 1: Building Knowledge Graph for single-hop queries...")

    loader = TextLoader(file_path, encoding="utf-8")
    doc_text = loader.load()[0].page_content

    # Clean the document
    for pattern in CRUFT_PATTERNS:
        doc_text = re.sub(pattern, "", doc_text, flags=re.IGNORECASE | re.MULTILINE)
    cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", doc_text)

    # Split into sections using all markdown header levels for better granularity
    headers_to_split_on = [
        ("##", "section"),
        ("###", "subsection"),
        ("####", "topic"),
        ("#####", "subtopic")
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    chunks = splitter.split_text(cleaned_text)

    # Create initial document nodes
    nodes = [
        Node(
            type=NodeType.DOCUMENT,
            properties={
                "page_content": chunk.page_content,
                "document_metadata": chunk.metadata,
            },
        )
        for chunk in chunks
        if len(chunk.page_content.split()) > 50  # Filter substantial chunks
    ]
    kg = KnowledgeGraph(nodes=nodes)

    # Apply transforms (no relationship builders needed for single-hop)
    # Adjusted token limits for more granular chunks from enhanced header splitting
    transforms = [
        HeadlinesExtractor(llm=llm),
        HeadlineSplitter(min_tokens=200, max_tokens=800),
        KeyphrasesExtractor(llm=llm, property_name="keyphrases", max_num=10),
    ]

    apply_transforms(kg, transforms=transforms)
    print(f"✅ Knowledge Graph built with {len(kg.nodes)} nodes.")
    return kg


def main():
    """Main function to run the single-hop test set generation pipeline."""
    parser = argparse.ArgumentParser(description="Generate high-quality single-hop testset using advanced Ragas API.")
    parser.add_argument("--document", type=str, default="data/cs-handbook.md", help="Path to the markdown document.")
    parser.add_argument("--size", type=int, default=20, help="Number of questions to generate.")
    parser.add_argument("--dept", type=str, default="ucl-cs", help="Department slug for filename.")
    parser.add_argument("--generator-model", type=str, default="gpt-4.1", help="Model for generation.")
    args = parser.parse_args()

    # Initialize models
    generator_llm = LangchainLLMWrapper(ChatOpenAI(model=args.generator_model))
    embedding_model = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

    # Phase 1: Build Knowledge Graph
    knowledge_graph = create_knowledge_graph(args.document, generator_llm)

    # Phase 2: Configure Personas
    print("\n🚀 Phase 2: Configuring Personas for UCL CS students...")

    personas = [
        Persona(
            name="injured_undergraduate",
            role_description="An undergraduate student who has hurt themselves and wants to know how to get an extension or support for missed deadlines."
        ),
        Persona(
            name="struggling_postgraduate",
            role_description="A Master's student who is worried about failing or missing coursework and needs clarity on resits, condonement, or progression rules."
        ),
        Persona(
            name="international_student",
            role_description="An international student concerned about visa requirements, travel, and how academic issues like resits or deferrals may affect their status."
        ),
        Persona(
            name="disabled_student",
            role_description="A student with a disability or long-term condition seeking information about reasonable adjustments, SORA, and who to contact for support."
        ),
        Persona(
            name="module_choice_student",
            role_description="A student unsure about how to select optional modules, late registration, or interdisciplinary modules, and wants guidance on the process."
        ),
        Persona(
            name="worried_exam_candidate",
            role_description="A student anxious about exams, asking about timetable clashes, exam formats, or what happens if they are ill during exams."
        ),
        Persona(
            name="faculty_member",
            role_description="A staff or faculty member who wants to check policies about communication with students, extenuating circumstances procedures, or progression rules."
        ),
        Persona(
            name="everyday_undergraduate",
            role_description="A first-year undergraduate who has everyday concerns such as where to find timetables, how to contact admin staff, or how teaching is structured."
        ),
    ]


    # Phase 3: Configure Single-Hop Query Distribution
    print("\n🚀 Phase 3: Configuring single-hop query synthesizer...")
    query_distribution = [
        (UCLSingleHopQuerySynthesizer(llm=generator_llm), 1.0),
    ]
    print("✅ Single-hop synthesizer configured.")

    # Phase 4: Generate Test Set
    print(f"\n🚀 Phase 4: Generating {args.size} single-hop questions...")
    print("⚙️ Configuration:")
    print(f"   • Model: {args.generator_model}")
    print(f"   • Max Workers: 1 (rate limit friendly)")
    print(f"   • Timeout: 5 minutes per request")
    print(f"   • Max Retries: 10 (will wait through rate limits)")
    print("⏳ Note: Script will automatically retry through rate limits - please be patient!")

    generator = TestsetGenerator(
        llm=generator_llm,
        embedding_model=embedding_model,
        persona_list=personas,
        knowledge_graph=knowledge_graph,
    )
    # Configure RunConfig for rate limit resilience
    # Reduce concurrency and increase retries to handle rate limits gracefully
    run_config = RunConfig(
        max_workers=1,    # Reduce to 1 worker to avoid overwhelming API
        timeout=300,      # Increase timeout to 5 minutes per request
        max_retries=10    # More retries for rate limit recovery
    )

    dataset = generator.generate(
        testset_size=args.size,
        query_distribution=query_distribution,
        run_config=run_config,
    )

    # Phase 5: Save Results
    print("\n🚀 Phase 5: Saving results...")
    out_dir = "testset"
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = args.generator_model.replace(":", "_").replace("/", "_")
    out_path = os.path.join(
        out_dir,
        f"{args.dept}_single_hop_testset_{model_slug}_{timestamp}.json"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset.to_list(), f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Success! Saved {len(dataset.to_list())} high-quality single-hop samples to {out_path}")

    # Show sample questions
    if dataset.to_list():
        print("\n📋 Sample Questions Generated:")
        for i, sample in enumerate(dataset.to_list()[:3], 1):
            print(f"  {i}. {sample['user_input']}")


if __name__ == "__main__":
    main()
