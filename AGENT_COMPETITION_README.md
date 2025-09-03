# Multi-Agent Document Processing Competition

## Quick Start

### 1. Launch All Agents
```bash
./launch-multi-agent-competition.sh
```

This will open 3 Cursor windows with isolated profiles.

### 2. Set Up Each Agent
In each Cursor window, switch to the respective branch:

**Window 1 (Conservative):**
```bash
git checkout agent-1-conservative-docprocessing
```

**Window 2 (Aggressive):**
```bash  
git checkout agent-2-aggressive-docprocessing
```

**Window 3 (Hybrid):**
```bash
git checkout agent-3-hybrid-docprocessing
```

### 3. Agent Instructions
Copy and paste the appropriate prompt from `agent-prompts.md` into each Cursor window:

- **Agent 1**: Conservative approach (reliability-focused)
- **Agent 2**: Aggressive approach (performance-focused)  
- **Agent 3**: Hybrid approach (balanced)

**IMPORTANT**: Each agent must read `.agent-prompts/document-processor.md` first!

### 4. Monitor Progress
Let each agent work independently. They should:
1. Read the document processor instructions
2. Create and get approval for implementation plan
3. Implement their approach
4. Test and validate results

### 5. Evaluate Results
When all agents are done:
```bash
./evaluate-competition.sh
```

## Competition Structure

### Branches
- `agent-1-conservative-docprocessing` - Reliability-focused approach
- `agent-2-aggressive-docprocessing` - Performance-focused approach
- `agent-3-hybrid-docprocessing` - Balanced approach

### Expected Outputs
Each agent should produce:
- `data/cs-handbook-{approach}.md` - Converted markdown file
- `src/process_documents_{approach}.py` - Implementation script
- Documentation of their approach and results

### Success Criteria
- **Table Recovery**: Extract all 15+ missing tables from the PDF
- **Quality**: Proper markdown formatting and structure
- **Integration**: Compatible with existing `build_index.py`
- **Performance**: Reasonable processing time
- **Reliability**: Error handling and fallback mechanisms

## Evaluation Metrics

### Quantitative
- Number of tables successfully extracted
- Processing time
- File size and structure
- Memory usage
- Error rate

### Qualitative  
- Code quality and maintainability
- Integration with existing pipeline
- Documentation and comments
- Innovation and novel approaches
- Cross-platform compatibility

## Manual Testing Queries
Test each implementation with these queries:
- "Who is the Departmental Tutor?" (requires staff table)
- "When is the coursework deadline?" (requires term dates table)  
- "What are the progression requirements?" (requires assessment table)
- "How do I contact my Programme Director?" (requires contact table)

## Troubleshooting

### If Cursor instances don't launch properly:
```bash
# Check if profiles were created
ls -la ~/.cursor-agents/

# Launch manually
cursor --user-data-dir=~/.cursor-agents/agent1-conservative /Users/Malik/code/malikbou/ucl/thesis/on-premise-slm
```

### If branches are missing:
```bash
git branch -a
# Create missing branches if needed
git checkout -b agent-X-approach-docprocessing
```

### If evaluation fails:
```bash
# Check for expected output files
ls -la data/cs-handbook-*.md
ls -la src/process_documents_*.py
```

## Competition Flow

1. **Setup** ✅ (You are here)
2. **Launch** → Run `./launch-multi-agent-competition.sh`
3. **Compete** → Each agent implements their approach
4. **Evaluate** → Run `./evaluate-competition.sh`
5. **Select Winner** → Choose best approach for integration

Ready to begin the competition! 🏁
