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

# Modern Ragas imports for a robust, multi-hop generation process
from ragas.testset import TestsetGenerator
from ragas.testset.graph import KnowledgeGraph, Node, NodeType
from ragas.testset.persona import Persona
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# Corrected Synthesizer imports based on your feedback and docs
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)
from ragas.testset.synthesizers.multi_hop.base import (
    MultiHopQuerySynthesizer,
    MultiHopScenario,
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
    OverlapScoreBuilder,
)
from ragas.run_config import RunConfig

# Load environment variables from your .env file
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


# --- Custom Multi-Hop Synthesizer Implementation ---
@dataclass
class MyMultiHopQuery(MultiHopQuerySynthesizer):
    """
    Custom Multi-Hop Synthesizer that inherits from the base abstract class
    and implements the scenario generation logic.
    """

    theme_persona_matching_prompt = ThemesPersonasMatchingPrompt()

    async def _generate_scenarios(
        self,
        n: int,
        knowledge_graph: KnowledgeGraph,
        persona_list: List[Persona],
        callbacks=None,
    ) -> t.List[MultiHopScenario]:
        results = knowledge_graph.find_two_nodes_single_rel(
            relationship_condition=lambda rel: (
                True if rel.type == "keyphrases_overlap" else False
            )
        )
        if not results:
            return []

        num_sample_per_triplet = max(1, n // len(results))
        scenarios = []
        for triplet in results:
            if len(scenarios) >= n:
                break

            node_a, node_b = triplet[0], triplet[-1]
            overlapped_keywords = triplet[1].properties.get("overlapped_items")
            if overlapped_keywords:
                themes = list(dict(overlapped_keywords).keys())
                prompt_input = ThemesPersonasInput(themes=themes, personas=persona_list)
                persona_concepts = await self.theme_persona_matching_prompt.generate(
                    data=prompt_input, llm=self.llm, callbacks=callbacks
                )
                overlapped_keywords = [list(item) for item in overlapped_keywords]
                base_scenarios = self.prepare_combinations(
                    [node_a, node_b],
                    overlapped_keywords,
                    personas=persona_list,
                    persona_item_mapping=persona_concepts.mapping,
                    property_name="keyphrases",
                )
                base_scenarios = self.sample_diverse_combinations(
                    base_scenarios, num_sample_per_triplet
                )
                scenarios.extend(base_scenarios)

        return scenarios


def create_knowledge_graph(file_path: str, llm: LangchainLLMWrapper) -> KnowledgeGraph:
    """
    Builds a rich Knowledge Graph by loading, cleaning, and running the
    correct sequence of transforms on the document.
    """
    print("🚀 Phase 1: Building a rich Knowledge Graph...")

    loader = TextLoader(file_path, encoding="utf-8")
    doc_text = loader.load()[0].page_content
    for pattern in CRUFT_PATTERNS:
        doc_text = re.sub(pattern, "", doc_text, flags=re.IGNORECASE | re.MULTILINE)
    cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", doc_text)

    headers_to_split_on = [("##", "section"), ("###", "subsection")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    chunks = splitter.split_text(cleaned_text)

    nodes = [
        Node(
            type=NodeType.DOCUMENT,
            properties={
                "page_content": chunk.page_content,
                "document_metadata": chunk.metadata,
            },
        )
        for chunk in chunks
        if len(chunk.page_content.split()) > 50
    ]
    kg = KnowledgeGraph(nodes=nodes)

    # Correctly sequence the transforms
    transforms = [
        HeadlinesExtractor(llm=llm),
        HeadlineSplitter(min_tokens=300, max_tokens=1000),
        KeyphrasesExtractor(llm=llm),
        OverlapScoreBuilder(),
    ]

    apply_transforms(kg, transforms=transforms)
    print(f"✅ Knowledge Graph built and transformed with {len(kg.nodes)} nodes.")
    return kg


def main():
    """Main function to run the test set generation pipeline."""
    parser = argparse.ArgumentParser(description="Generate a high-quality test set using the modern ragas API.")
    parser.add_argument("--document", type=str, default="data/cs-handbook.md", help="Path to the markdown document.")
    parser.add_argument("--size", type=int, default=10, help="Number of questions to generate.")
    parser.add_argument("--dept", type=str, default="ucl-cs", help="Department slug for filename.")
    parser.add_argument("--generator-model", type=str, default="gpt-4o-mini", help="Model for generation.")
    args = parser.parse_args()

    # Initialize models
    generator_llm = LangchainLLMWrapper(ChatOpenAI(model=args.generator_model))
    embedding_model = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

    # Phase 1
    knowledge_graph = create_knowledge_graph(args.document, generator_llm)

    # Phase 2
    print("\n🚀 Phase 2: Configuring diverse Synthesizers and Personas...")
    personas = [
        Persona(
            name="new_undergraduate",
            role_description="A first-year undergraduate at UCL CS, concerned with module registration, key dates, and finding academic support."
        ),
        Persona(
            name="postgraduate_researcher",
            role_description="A Master's student focused on their dissertation, interested in research ethics, project requirements, and academic integrity."
        ),
    ]

    # Configure query distribution with the custom multi-hop synthesizer
    query_distribution = [
        (SingleHopSpecificQuerySynthesizer(llm=generator_llm), 0.7),
        (MyMultiHopQuery(llm=generator_llm), 0.3),
    ]
    print("✅ Synthesizers and Personas configured.")

    # Phase 3
    print("\n🚀 Phase 3: Generating test set and saving to JSON...")
    generator = TestsetGenerator(
        llm=generator_llm,
        embedding_model=embedding_model,
        persona_list=personas,
        knowledge_graph=knowledge_graph,
    )
    run_config = RunConfig(max_workers=4, timeout=120, max_retries=3)

    dataset = generator.generate(
        testset_size=args.size,
        query_distribution=query_distribution,
        run_config=run_config,
    )

    # Save results
    out_dir = "testset"
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = args.generator_model.replace(":", "_").replace("/", "_")
    out_path = os.path.join(
        out_dir,
        f"{args.dept}_testset_{model_slug}_{timestamp}.json"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset.to_list(), f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Success! Saved {len(dataset.to_list())} high-quality samples to {out_path}")


if __name__ == "__main__":
    main()
