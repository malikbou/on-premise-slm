# Testset Generation Agent Instructions

## MANDATORY: Planning Approval Process
**BEFORE WRITING ANY CODE:**
1. Create detailed implementation plan using template in `.cursorrules`
2. Present plan to user for approval
3. Wait for explicit user confirmation before proceeding
4. Only execute code after receiving approval

## Role
You are a testset generation expert creating 100 high-quality questions from the UCL CS handbook for comprehensive RAG evaluation using knowledge graph-enhanced generation. Support both Mac local development and Vast.ai GPU VM deployment workflows.

## Current Problem Analysis

**Existing Testset Issues:**
- **Only 7 questions total** in current `CS_testset_from_markdown_gpt-4o-mini_20250803_175526.json`
- **All single-hop questions**: No complex reasoning or multi-hop queries
- **Limited coverage**: Missing critical handbook sections (staff contacts, assessment policies, support services)
- **Basic complexity**: Only "single_hop_specific_query_synthesizer" type questions
- **Inadequate for thesis evaluation**: Need 100 diverse questions for robust benchmarking

**Missing Question Types:**
- Multi-hop reasoning requiring connection between sections
- Complex policy interpretation scenarios
- Cross-referential questions linking multiple handbook areas
- Edge case situations combining multiple rules/procedures

## Knowledge Graph Strategy

### Phase 1: Knowledge Graph Implementation
**Leverage Existing `generate_testset_kg.py`:**
- ✅ Already implements RAGAS knowledge graph approach
- ✅ Supports multi-hop question generation via `KnowledgeGraph` and `Node` structures
- ✅ Has semantic heading-based chunking for better context preservation
- ✅ Includes sophisticated transformations: `KeyphrasesExtractor`, `SummaryExtractor`, `NERExtractor`

**Enhance for CS Handbook:**
1. **Adapt chunk strategy** for academic document structure (sections 1-24)
2. **Configure entity extraction** for CS-specific entities (staff roles, deadlines, procedures)
3. **Optimize relationship building** between handbook sections using `SummaryCosineSimilarityBuilder`

### Phase 2: Question Type Distribution

**Target 100 Questions with Strategic Mix:**

1. **Single-Hop Factual** (40 questions - 40%):
   - Staff contact information queries
   - Deadline and date queries
   - Direct policy statements
   - Support service details

2. **Multi-Hop Reasoning** (35 questions - 35%):
   - Cross-section policy interactions
   - Procedure chains requiring multiple steps
   - Conditional scenarios (e.g., "What if I'm international AND part-time?")
   - Complex academic pathway questions

3. **Interpretive/Analytical** (20 questions - 20%):
   - Policy application to specific scenarios
   - Edge case interpretations
   - Conflict resolution between different rules
   - Academic misconduct and appeals processes

4. **Persona-Based Scenarios** (5 questions - 5%):
   - Crisis situations ("I'm failing and on student visa")
   - Complex academic planning scenarios
   - Special circumstances applications

### Phase 3: Student Persona Integration

**Expand Beyond Current Personas:**
- **Anxious First-Year**: Basic navigation and deadlines
- **International Student**: Visa compliance and support
- **Struggling Student**: Academic recovery and support services
- **Part-Time Student**: Flexibility and scheduling
- **Postgraduate**: Research and dissertation requirements
- **Student with Disabilities**: Accessibility and accommodations

## Technical Implementation Plan

### Primary Tool Selection
**Use `generate_testset_kg.py` as foundation:**
```python
# Enhanced knowledge graph generation for CS handbook
from ragas.testset.graph import KnowledgeGraph
from ragas.testset.synthesizers import QueryDistribution
from ragas.testset.synthesizers.multi_hop import (
    MultiHopAbstractQuerySynthesizer,
    MultiHopSpecificQuerySynthesizer,
)

# Configure for CS handbook structure
query_distribution = QueryDistribution(
    single_hop_specific=0.4,
    multi_hop_specific=0.25,
    multi_hop_abstract=0.1,
    persona_based=0.25
)
```

### Enhanced Configuration
1. **Document Processing**: Use the advanced semantic chunking in `generate_testset_kg.py`
2. **Entity Enhancement**: Focus on CS-specific entities (Programme Director, Module Leader, etc.)
3. **Relationship Building**: Connect related handbook sections via knowledge graph
4. **Quality Validation**: Implement robust filtering for academic relevance

### Integration Strategy
1. **Modify existing `generate_testset_kg.py`**:
   - Update for CS handbook path and structure
   - Configure chunk size for optimal section coverage
   - Add CS-specific entity patterns and relationships

2. **Add quality validation layer**:
   - Verify questions reference actual handbook content
   - Ensure multi-hop questions span different sections
   - Validate persona-based questions match realistic scenarios

3. **Output optimization**:
   - Maintain compatibility with existing benchmark pipeline
   - Add metadata for question type and complexity analysis
   - Include source section tracking for coverage validation

## Success Criteria & Validation

### Quantitative Targets
- **100 total questions** (vs current 7)
- **35+ multi-hop questions** (vs current 0)
- **Coverage of all 24 handbook sections**
- **Question distribution matching academic needs**
- **90%+ questions answerable from improved document**

### Quality Metrics
- **Multi-hop validation**: Questions requiring 2+ handbook sections
- **Persona authenticity**: Questions matching real student scenarios
- **Academic relevance**: All questions address practical student/teacher needs
- **Difficulty progression**: Mix of basic, intermediate, and complex questions

### Test Validation Queries
Process these scenarios to validate comprehensive coverage:
- **Simple**: "Who is the Departmental Tutor?" (requires staff table recovery)
- **Multi-hop**: "As an international student, what happens if I fail my modules and need to retake?" (visa + academic + progression)
- **Procedural**: "How do I appeal a grade while on study abroad?" (appeals + international + assessment)
- **Edge case**: "Can I take a year in industry if I'm already part-time?" (YII + part-time + timeline)

## File Locations & Implementation
- **Primary tool**: Enhance `src/generate_testset_kg.py` for CS handbook
- **Input**: `data/cs-handbook-docling.md` (after document processing improvements)
- **Output**: `testset/CS_handbook_100_kg_questions_[timestamp].json`
- **Backup approach**: `src/generate_super_testset.py` with persona enhancement
- **Validation**: Compare against existing 7-question testset for improvement metrics

## Migration Strategy
1. **Phase 1**: Enhance `generate_testset_kg.py` with CS-specific configurations
2. **Phase 2**: Generate initial 100-question testset with knowledge graph approach
3. **Phase 3**: Validate and refine based on RAG performance testing
4. **Phase 4**: Integrate with improved document processing for maximum quality

## Cross-Platform Development Strategy

### Mac Local Development:
- **Small Testsets**: Generate 10-20 questions for quick validation and iteration
- **API Cost Management**: Use smaller, cheaper models for development (gpt-4o-mini)
- **Fast Feedback**: Validate question quality and format before full generation

### Vast.ai GPU VM Deployment:
- **Full 100-Question Generation**: Complete testset generation with full knowledge graph
- **Model Optimization**: Use larger, more capable models for final question quality
- **Batch Processing**: Generate questions in batches to manage memory and API costs

### Platform-Specific Configuration:
```python
def get_testset_config():
    """Platform-specific testset generation configuration"""
    import platform

    if platform.system() == 'Darwin':  # Mac local
        return {
            'testset_size': 20,  # Smaller for testing
            'model': 'gpt-4o-mini',
            'batch_size': 5,
            'parallel_workers': 1,
            'mode': 'development'
        }
    else:  # Vast.ai VM
        return {
            'testset_size': 100,  # Full testset
            'model': 'gpt-4o',
            'batch_size': 10,
            'parallel_workers': 3,
            'mode': 'production'
        }
```

### Development Workflow:
1. **Mac Phase**: Develop and validate with 20-question testset
2. **Transition**: Test knowledge graph generation with sample data
3. **VM Phase**: Generate full 100-question testset for benchmarking
4. **Validation**: Compare quality metrics between platforms

This approach leverages your existing sophisticated knowledge graph infrastructure while addressing the critical gap of having only 7 questions for a thesis-level evaluation system, with appropriate scaling for development vs production environments.
