# Multi-Agent Competition Framework

## Overview
Run multiple Cursor agents on the same task to compare approaches and select the best implementation.

## Competition Setup

### Method 1: Branch-Based Competition (Recommended)
```bash
# Initial setup
git checkout -b baseline-implementation

# Create competition branches
git checkout -b agent-1-conservative-approach
git checkout -b agent-2-aggressive-approach
git checkout -b agent-3-hybrid-approach

# Each agent works on their branch
# Instructions: "Read .agent-prompts/document-processor.md and implement your approach"
```

### Method 2: Directory-Based Competition
```bash
# Create experiment structure
mkdir -p experiments/task-name/
├── agent-1-approach/
├── agent-2-approach/
├── agent-3-approach/
├── evaluation-criteria.md
└── results-comparison/
```

## Agent Competition Instructions

### For Document Processing Task:
**Agent 1 Prompt:**
```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: CONSERVATIVE
- Focus on reliability and backward compatibility
- Implement Docling with fallback to existing PyMuPDF
- Prioritize table extraction accuracy over speed
- Branch: agent-1-conservative-approach

Success Criteria:
- All 15+ tables extracted correctly
- No breaking changes to existing pipeline
- Comprehensive error handling
```

**Agent 2 Prompt:**
```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: AGGRESSIVE OPTIMIZATION
- Focus on performance and cutting-edge features
- Full Docling integration with advanced features
- Optimize for speed and GPU acceleration
- Branch: agent-2-aggressive-approach

Success Criteria:
- Fastest processing time
- Maximum feature utilization
- GPU-optimized performance
```

**Agent 3 Prompt:**
```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: HYBRID BALANCE
- Balance reliability with performance
- Modular implementation allowing feature toggles
- Cross-platform optimization (Mac + Vast.ai)
- Branch: agent-3-hybrid-approach

Success Criteria:
- Best overall balance of speed and reliability
- Cross-platform compatibility
- Configurable feature set
```

## Evaluation Framework

### Quantitative Metrics:
- **Processing Time**: Document conversion speed
- **Table Recovery**: Number of tables successfully extracted (target: 15+)
- **Accuracy**: Quality of Markdown output vs manual verification
- **Memory Usage**: Peak RAM/VRAM during processing
- **Error Rate**: Failed conversions or corrupted output

### Qualitative Assessment:
- **Code Quality**: Readability, maintainability, documentation
- **Integration**: How well it fits with existing pipeline
- **Robustness**: Error handling and edge case management
- **Innovation**: Novel approaches or optimizations

### Comparison Template:
```markdown
# Agent Competition Results: Document Processing

## Agent 1 (Conservative)
- **Processing Time**: X seconds
- **Tables Extracted**: X/15+
- **Memory Usage**: X MB peak
- **Code Quality**: X/10
- **Notable Features**: [list]
- **Pros**: [list]
- **Cons**: [list]

## Agent 2 (Aggressive)
[same format]

## Agent 3 (Hybrid)
[same format]

## Winner Selection:
**Chosen Approach**: Agent X
**Reasoning**: [detailed explanation]
**Integration Plan**: [merge strategy]
```

## Implementation Workflow

### Phase 1: Setup Competition
1. Create branches/directories for each agent
2. Provide agent-specific prompts with approach differentiation
3. Set clear evaluation criteria and timelines

### Phase 2: Parallel Development
1. Each agent works independently on their approach
2. Regular progress checkpoints without cross-contamination
3. Document decision-making and approach rationale

### Phase 3: Evaluation & Selection
1. Run standardized tests on all implementations
2. Compare quantitative and qualitative metrics
3. Select winning approach or create hybrid solution

### Phase 4: Integration
1. Merge winning approach to main branch
2. Document lessons learned from other approaches
3. Archive alternative implementations for future reference

## Best Practices

### For Agents:
- **Read the base agent prompt first** (e.g., document-processor.md)
- **MANDATORY: Create implementation plan** and get user approval before coding
- **Focus on your assigned approach** (conservative/aggressive/hybrid)
- **Document your reasoning** for major decisions
- **Test thoroughly** with provided validation criteria
- **Don't peek** at other agents' work until evaluation phase

### For Project Owner:
- **Clear differentiation** in agent approaches to avoid duplication
- **Standardized testing** for fair comparison
- **Objective evaluation criteria** defined upfront
- **Timeline management** to prevent endless iteration

## Competition Templates

### Quick Start Commands:
```bash
# Setup competition branches
git checkout -b agent-1-conservative
git checkout -b agent-2-aggressive
git checkout -b agent-3-hybrid

# Agent instruction template
echo "Agent X: Read .agent-prompts/[task].md, implement [approach] approach on branch agent-X-[approach]"

# Evaluation command
./evaluate-agent-competition.sh document-processing
```

This framework allows systematic comparison of different implementation approaches while maintaining code organization and evaluation objectivity.
