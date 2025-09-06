## Single-Hop Testset Generation

High-quality single-hop question generation for the UCL CS Student Handbook using modern RAGAS testset APIs and LangChain wrappers.

### Purpose

- **Goal**: Produce a clean, persona-aware, single-hop QA testset for RAG evaluation.
- **Source**: Markdown handbook (e.g., `data/cs-handbook.md`).
- **Output**: Timestamped JSON in `data/testset/`, ready for downstream RAG benchmarking.

### File

- `generate_testset_single_hop.py`: End-to-end pipeline to build a knowledge graph from Markdown, synthesize single-hop questions, and save a dataset.

## How it Works

The script runs in five phases, mirroring the code:

1) Knowledge Graph Build
- Cleans navigation cruft and normalizes whitespace.
- Splits Markdown by headers (`##`, `###`, `####`, `#####`) using `MarkdownHeaderTextSplitter`.
- Creates initial `DOCUMENT` nodes, then applies transforms:
  - `HeadlinesExtractor` (LLM): extracts section headlines.
  - `HeadlineSplitter`: creates granular `CHUNK` nodes (200–800 tokens).
  - `KeyphrasesExtractor` (LLM): adds `keyphrases` property to chunks.

2) Personas
- Preconfigured UCL-centric personas (e.g., injured undergraduate, international student, disabled student, faculty member, etc.).

3) Single-Hop Synthesizer
- Custom `UCLSingleHopQuerySynthesizer` filters `CHUNK` nodes that already have `keyphrases` and samples scenarios.
- Uses `ThemesPersonasMatchingPrompt` to match themes ↔ personas before generating prompts.

4) Generation
- `TestsetGenerator.generate()` combines the LLM, embeddings, personas, and the knowledge graph.
- Conservative `RunConfig` for rate limits: `max_workers=1`, `timeout=300`, `max_retries=10`.

5) Save Results
- Writes JSON to `data/testset/{dept}_single_hop_testset_{model}_{timestamp}.json`.
- Prints a few sample questions to stdout.

## Prerequisites

- Python 3.11
- Dependencies: `pip install -r src/requirements.txt`
- Environment: `.env` with `OPENAI_API_KEY` (loaded via `python-dotenv`).
- Input document: `data/cs-handbook.md` (or another cleaned Markdown file). If you need to generate it, see the Markdown conversion README in `src/markdown_conversion/`.

## Usage

### Basic

```bash
python src/testset/generate_testset_single_hop.py \
  --size 20 \
  --generator-model gpt-4.1
```

### Custom document and department slug

```bash
python src/testset/generate_testset_single_hop.py \
  --document data/cs-handbook.md \
  --size 50 \
  --dept ucl-cs \
  --generator-model gpt-4.1
```

### Parameters

- **--document**: Path to Markdown input. Default: `data/cs-handbook.md`.
- **--size**: Number of questions to generate. Default: `20`.
- **--dept**: Department slug used in output filename. Default: `ucl-cs`.
- **--generator-model**: OpenAI model for generation (LangChain `ChatOpenAI`). Default: `gpt-4.1`.

Environment variables (from `.env`):
- **OPENAI_API_KEY**: Required for both `ChatOpenAI` and `OpenAIEmbeddings`.

## Output

- Location: `data/testset/`
- Filename pattern: `{dept}_single_hop_testset_{model}_{YYYYmmdd_HHMMSS}.json`
- Content: A list of generated samples compatible with RAGAS testset format. Keys include at least `user_input` (shown in the console). Other fields may vary by RAGAS version.

Example (illustrative):

```json
[
  {
    "user_input": "How do I request an extension due to injury?",
    "metadata": {
      "persona": "injured_undergraduate",
      "themes": ["extensions", "mitigating circumstances"]
    }
  }
]
```

## Notes & Tips

- Rate limits: The script is configured to be resilient (`max_workers=1`, generous retries/timeouts). It may pause and resume through HTTP 429/5xx conditions.
- Harmless logs: You may see lines like `Property 'keyphrases' already exists in node '...'. Skipping!` while transforms run. This is expected when a property is already present.
- Coverage: Only `CHUNK` nodes that have `keyphrases` are considered for sampling. If you see `No qualified CHUNK nodes found`, verify the input Markdown quality and heading structure.
- Document quality: Better heading hierarchy and cleaned text improve chunking and keyphrase extraction. See `src/markdown_conversion/README.md` for generating high-quality Markdown.

## Customization

- Personas: Edit the `personas` list in `generate_testset_single_hop.py` to reflect new roles.
- Cleaning rules: Adjust `CRUFT_PATTERNS` to remove additional navigation or boilerplate.
- Chunk sizes: Tweak `HeadlineSplitter(min_tokens=..., max_tokens=...)` to control granularity.
- Models:
  - Generation: Change `--generator-model` to any OpenAI model supported by your account.
  - Embeddings: The script uses `OpenAIEmbeddings()` via LangChain. Swap to another embeddings wrapper if needed.

## Troubleshooting

- Missing API key: Ensure `.env` contains `OPENAI_API_KEY` and that your shell loads it (the script calls `load_dotenv()`).
- Empty or tiny output: Increase `--size`, confirm the document has sufficient structured content, and check that header levels exist (`##`/`###` etc.).
- Slow runs: This is by design to respect rate limits. For faster local testing, try smaller `--size`.

## Related

- Main project README: `../../README.md`
- Markdown conversion pipeline: `../markdown_conversion/README.md`
- RAG benchmarking entrypoint: `../../src/benchmark.py`
