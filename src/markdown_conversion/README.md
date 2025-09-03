# Markdown Conversion Pipeline

Purpose: Convert the UCL CS Student Handbook PDF to high-quality Markdown optimized for RAG.

## Structure

- `pipeline.py`: Orchestrates conversion → post-processing → emission
- `engines/`
  - `docling_engine.py`: Primary Docling-based conversion
  - `fallbacks/pdfplumber_fallback.py`: Simple table fallback
- Post-processors: `src/markdown_conversion/postprocess.py` (re-export from the former `src/postprocess_markdown.py`)
- Platform config via `src/common/platform.py` (re-exported by `src/common/platform_config.py`)

## Usage

Generate Markdown (new CLI):

```bash
python -m src.markdown_conversion.cli convert --input "data/Computer Science Student Handbook 2024-25.pdf" --output data/cs-handbook-hybrid.md --save-metrics
```

Validate (tables, links, headings):

```bash
python -m src.markdown_conversion.cli validate --old data/cs-handbook.md --new data/cs-handbook-hybrid.md --out results/table_validation_hybrid.json
```

Index for RAG:

```bash
HANDBOOK_MD_PATH=data/cs-handbook-hybrid.md python src/build_index.py
```

## Key Features

- Docling-first conversion with optional fallbacks
- Post-processing passes (current behavior):
  - Remove TOC/index and repeated headers/footers; trim preamble to the first numeric "## 1"
  - Normalize headings by section numbering; demote unnumbered headings under numbered parents
  - Autolink emails/URLs (skips code and tables); improve link labels for known UCL domains
  - Authentic inline links via PDF annotations when available (Academic Manual, Module Catalogue)
  - Table normalization (GFM) and de-duplication
  - Paragraph reflow and symbol cleanup (✓, ✗, smart quotes/dashes)
  - Navigation bloat removal (e.g., Quick Links blocks)
- Important: Inline-only links — link sections ("Quick Links"/"Links (N)") are disabled by default to avoid polluting Markdown
- Cross-platform defaults (Mac vs Vast.ai) via env/config

## Environment Toggles

- `REMOVE_ANNEXES` (default: true)
- `LINK_MODE` = inline_then_fallback | off (default: inline_then_fallback)
- `LINK_PLACEMENT` = nearest_section | end_of_doc (default: nearest_section)
- `ADD_QUICK_LINKS` (default: true)
- `TRIM_BEFORE_SECTION1` (default: true)
- `TABLE_FALLBACK_EXTRACTOR` = off | pdfplumber (default: off)

### Recommended link behavior

- To keep clean inline-only output (no link sections), either:
  - Set `LINK_MODE=off` when running convert, or
  - Rely on the pipeline’s current default which strips residual `Links (N)` headings

### Fallback-only run (no Docling)

If Docling is unavailable locally, enable the pdfplumber fallback to still produce a useful output with recovered tables:

```bash
TABLE_FALLBACK_EXTRACTOR=pdfplumber \
python -m src.markdown_conversion.cli convert \
  --input "data/Computer Science Student Handbook 2024-25.pdf" \
  --output data/cs-handbook-hybrid.md --save-metrics
```

## Notes

- Backwards compatibility: `src/process_documents_hybrid.py` delegates to this pipeline.
- Outputs: `data/cs-handbook-hybrid.md` plus `__metrics.json` if `--save-metrics`.
