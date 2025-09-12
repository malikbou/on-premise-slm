# Problems and Solutions Log

Add newest entries at the top (reverse chronological). Keep entries concise and link to evidence.

Template (narrative-friendly):

```
## <YYYY-MM-DD> — <Short, descriptive title>

- Area: <component/file/path>
- Context
  <What you were trying to accomplish and why it matters.>

- Symptoms
  <What you observed; include error messages and examples.>

- Root cause
  <What was actually wrong; call out version/behavior mismatches.>

- Resolution
  <What you changed (code/config), and why it addressed the root cause.>

- Validation
  <How you verified the fix: checks, sample outputs, metrics.>

- Lessons learned
  <Actionable takeaways and guidance for future work.>

- Evidence
  <Links to commits/PRs, runs, datasets, screenshots, or local paths.>

- Follow-ups
  <Next steps: perf, docs, tests, risks to monitor.>
```

Entries:

## 2025-09-12 — Making Ragas testset generation reliable and controllable (single-hop + multi-hop)

- Area: src/testset/*.ipynb, ragas testset synthesizers and transforms

- Context
  I needed to generate high-quality single-hop and multi-hop testsets over the UCL CS handbook, with control over query style (formal) and length, and predictable performance.

- Symptoms
  1) Multi-hop failed with “ValueError: No clusters found in the knowledge graph” despite running OverlapScoreBuilder.
  2) Multi-hop specific raised a Pydantic “themes must be List[str]” error.
  3) Queries mixed informal phrasing (“can u”, “whats…”) and occasional noise.
  4) Multi-hop abstract was slow and sometimes produced weak combinations.

- Root cause
  - Relationship naming mismatch: OverlapScoreBuilder creates edges of type "{property}_overlap" and score property "{property}_overlap_score"; synthesizers were pointed to generic names or function predicates.
  - Overlapped items are stored as tuples; persona prompt expected List[str].
  - “Formal” is not a literal QueryStyle; code uses QueryStyle.PERFECT_GRAMMAR.
  - Abstract synthesizer assumed node “themes” and explored too many clusters (depth and breadth), causing slow LLM calls.

- Resolution
  - Aligned names: used relation_type="keyphrases_overlap" and relation_property="keyphrases_overlap_score" (built via OverlapScoreBuilder(property_name="keyphrases", new_property_name="overlap_score")).
  - Patched multi-hop specific: flattened overlapped_items to strings for persona matching while keeping pairs for combinations.
  - Subclassed synthesizers to force QueryStyle.PERFECT_GRAMMAR and a fixed QueryLength.
  - Tuned abstract: set abstract_property_name="keyphrases", depth_limit=2, and capped clusters; tightened overlap thresholds to reduce graph density.
  - Added pre-flight checks on the exact KG used by TestsetGenerator (triplets/clusters present; generator.knowledge_graph is kg).
  - Ensured personas respect schema (name, role_description) and used num_personas=len(personas) to avoid slicing to 3.

- Validation
  - Pre-flight showed thousands of keyphrases_overlap edges, nonzero triplets and indirect clusters.
  - Generated coherent questions for both multi-hop specific and abstract; style/length controlled; fewer informal phrasings; improved focus.
  - Example reference for approach: Ragas custom multi-hop guide (edge and persona mapping patterns) https://docs.ragas.io/en/latest/howtos/customizations/testgenerator/_testgen-customisation/#create-multi-hop-query

- Lessons learned
  - Always inspect local Ragas source for exact enums, available synthesizers, and relationship naming; online docs may lag.
  - Multi-hop pipeline hinges on consistent property/edge naming and object shapes (tuple vs string).
  - Style/length should be enforced inside synthesizer prepare_combinations, not by prompt alone.
  - Abstract generation needs hard caps (depth, clusters) and stricter overlap to stay fast and relevant.

- Evidence
  - Notebooks: src/testset/generate_testset.ipynb
  - Datasets: data/testset/cs-handbook_testset_gpt-4.1-mini_20250912_130930.json
  - Rule updates capturing conventions: .cursor/rules/ragas-local-source.mdc, testset-generation.mdc, project-standards.mdc

- Follow-ups
  - Add light post-generation cleanup (spelling, casing) and simple heuristics to drop noisy prompts.
  - Consider a small unit test around OverlapScoreBuilder naming and a smoke test ensuring nonzero triplets/clusters.
  - Explore batching/run_config for consistent latency; optionally surface a “fast/quality” toggle in notebooks.
