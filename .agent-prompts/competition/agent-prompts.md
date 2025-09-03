# Multi-Agent Competition Prompts for Document Processing

## Competition Overview
You are participating in a multi-agent competition for document processing. Three agents with different approaches will implement Docling-based PDF to Markdown conversion for the UCL CS Student Handbook.

**MANDATORY**: Each agent must read `.agent-prompts/document-processor.md` first for full context and requirements.

---

## Agent 1 Prompt: CONSERVATIVE APPROACH

```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: CONSERVATIVE
- Focus on reliability and backward compatibility
- Implement Docling with fallback to existing PyMuPDF
- Prioritize table extraction accuracy over speed
- Work on branch: agent-1-conservative-docprocessing

Success Criteria:
- All 15+ tables extracted correctly
- No breaking changes to existing pipeline
- Comprehensive error handling
- Robust fallback mechanisms

MANDATORY: Create implementation plan and get user approval before coding

Key Focus Areas:
1. Maintain compatibility with existing build_index.py
2. Implement thorough error handling and fallbacks
3. Validate table extraction quality over speed
4. Ensure cross-platform stability (Mac + Vast.ai)
5. Document all assumptions and limitations
```

---

## Agent 2 Prompt: AGGRESSIVE OPTIMIZATION

```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: AGGRESSIVE OPTIMIZATION
- Focus on performance and cutting-edge features
- Full Docling integration with advanced features
- Optimize for speed and GPU acceleration
- Work on branch: agent-2-aggressive-docprocessing

Success Criteria:
- Fastest processing time
- Maximum feature utilization
- GPU-optimized performance
- Advanced table processing techniques

MANDATORY: Create implementation plan and get user approval before coding

Key Focus Areas:
1. Leverage all Docling advanced features
2. Implement GPU acceleration where possible
3. Optimize for speed without compromising accuracy
4. Use parallel processing and async operations
5. Push the boundaries of what's possible with Docling
```

---

## Agent 3 Prompt: HYBRID BALANCE

```
You are participating in a multi-agent competition for document processing.

Read .agent-prompts/document-processor.md for full context.

Your approach: HYBRID BALANCE
- Balance reliability with performance
- Modular implementation allowing feature toggles
- Cross-platform optimization (Mac + Vast.ai)
- Work on branch: agent-3-hybrid-docprocessing

Success Criteria:
- Best overall balance of speed and reliability
- Cross-platform compatibility
- Configurable feature set
- Intelligent performance/accuracy trade-offs

MANDATORY: Create implementation plan and get user approval before coding

Key Focus Areas:
1. Create configurable processing pipeline
2. Implement intelligent fallback strategies
3. Optimize for both Mac and Vast.ai environments
4. Balance performance with reliability
5. Design modular architecture for future extensibility
```

---

## Competition Rules

### For All Agents:
1. **MUST read** `.agent-prompts/document-processor.md` first
2. **MANDATORY** planning phase - create detailed implementation plan and get user approval
3. Work independently on assigned branch
4. Focus on your specific approach (conservative/aggressive/hybrid)
5. Document decision-making rationale
6. Test thoroughly with validation criteria
7. No cross-contamination - don't look at other agents' work

### Evaluation Criteria:
- **Table Recovery**: Extract all 15+ missing tables
- **Processing Time**: Speed of conversion
- **Code Quality**: Maintainability and documentation
- **Integration**: Compatibility with existing pipeline
- **Cross-Platform**: Mac + Vast.ai performance
- **Innovation**: Novel approaches and optimizations

### Target Files:
- **Input**: `data/Computer Science Student Handbook 2024-25.pdf`
- **Output**: `data/cs-handbook-{approach}.md`
- **Implementation**: `src/process_documents_{approach}.py`
- **Requirements**: Update `src/requirements.txt` as needed

### Validation Queries:
Test your implementation with these queries:
- "Who is the Departmental Tutor?" (requires staff table)
- "When is the coursework deadline?" (requires term dates table)
- "What are the progression requirements?" (requires assessment table)
- "How do I contact my Programme Director?" (requires contact table)

Good luck! May the best approach win! 🏆
