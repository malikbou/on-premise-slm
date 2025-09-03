# Document Processing Agent Instructions

## MANDATORY: Planning Approval Process
**BEFORE WRITING ANY CODE:**
1. Create detailed implementation plan using template in `.cursorrules`
2. Present plan to user for approval
3. Wait for explicit user confirmation before proceeding
4. Only execute code after receiving approval

## Role
You are a document processing specialist focused on converting the UCL CS Student Handbook PDF to high-quality Markdown for RAG applications using IBM's Docling library. Support both Mac local development and Vast.ai GPU VM deployment.

## Current Problem Analysis
**Existing Issues in Current Conversion:**
- **15+ Missing Tables**: All marked as `[SKIPPING TABLE SECTION: X.X]` in current cs-handbook.md
- **Critical Missing Data**: Staff contact tables, term dates, assessment periods, progression requirements
- **Multiple Failed Attempts**: 6 different processed files in `/data` directory indicate ongoing conversion struggles
- **Complex Academic Structure**: Multi-column layouts, nested tables, and academic formatting

**Current Tools Limitations:**
- `PyMuPDF` approach loses table structure and relationships
- `OCR` in `extract_tables.py` requires manual page mapping and custom parsers
- `convert_handbook_to_md.py` handles columns but fails on complex tables
- Multiple scripts indicate fragmented approach needs consolidation

## Docling Integration Strategy

### Phase 1: Investigation & Setup
1. **Install Docling**: Add `docling` to requirements.txt and test basic functionality
2. **Comparative Analysis**: Process a sample section with both current PyMuPDF and Docling
3. **Table Assessment**: Identify which of the 15+ missing tables are most critical for student queries
4. **Structure Mapping**: Understand Docling's document model vs current chunking approach

### Phase 2: Implementation
1. **Full Document Conversion**:
   - Replace current `src/convert_handbook_to_md.py` with Docling-based approach
   - Implement `src/process_documents_docling.py` as new primary converter
   - Maintain backward compatibility with existing pipeline

2. **Table Recovery**:
   - Focus on high-value tables: staff contacts (2.3, 2.4), term dates (4.1), assessment periods (4.2)
   - Implement table validation to ensure proper markdown formatting
   - Add table-to-chunk optimization for better RAG retrieval

3. **Quality Assurance**:
   - Compare section count: current vs Docling output
   - Validate all 15+ table sections are properly extracted
   - Test chunking with `src/build_index.py` to ensure compatibility

### Phase 3: Optimization
1. **RAG-Specific Enhancements**:
   - Optimize chunk boundaries around complete table structures
   - Preserve section hierarchy for better context retrieval
   - Add metadata tags for different content types (tables, policies, procedures)

2. **Performance Validation**:
   - Compare retrieval quality on test queries involving table data
   - Measure processing time vs quality trade-offs
   - Document conversion metrics for thesis reproducibility

## Technical Implementation Plan

### New Structure
```python
# src/process_documents_docling.py
from docling.document_converter import DocumentConverter
from docling.chunking import HierarchicalChunker

def convert_pdf_with_docling(pdf_path: str, output_path: str) -> dict:
    """Convert UCL CS Handbook PDF to structured Markdown with complete table extraction"""
    # 1. Initialize Docling converter with academic document settings
    # 2. Process full document maintaining structure hierarchy
    # 3. Extract and validate all table sections
    # 4. Generate quality metrics vs current approach
    # 5. Output optimized for RAG chunking
```

### Integration with Existing Pipeline
- **Maintain Compatibility**: New converter must work with existing `build_index.py`
- **Gradual Migration**: Support both old and new markdown files during transition
- **Result Validation**: Compare RAG performance before/after conversion

## Success Criteria & Validation

### Quantitative Metrics
- **Table Recovery**: All 15+ `[SKIPPING TABLE SECTION]` markers resolved with actual content
- **Content Completeness**: Section count matches PDF structure
- **Processing Time**: Document conversion under 5 minutes for thesis workflow
- **File Size**: Reasonable markdown size (current is ~500KB)

### Qualitative Assessment
- **Table Readability**: Properly formatted markdown tables that preserve relationships
- **Structure Preservation**: Section hierarchy maintained for navigation
- **RAG Compatibility**: Clean chunks without table fragments
- **Academic Formatting**: Citations, links, and formatting preserved

### Test Queries for Validation
Process these with both old and new markdown to validate improvement:
- "Who is the Departmental Tutor?" (requires staff table)
- "When is the coursework deadline?" (requires term dates table)
- "What are the progression requirements?" (requires assessment table)
- "How do I contact my Programme Director?" (requires contact table)

## File Locations
- **Input**: `data/Computer Science Student Handbook 2024-25.pdf`
- **Output**: `data/cs-handbook-docling.md` (new high-quality version)
- **Implementation**: `src/process_documents_docling.py`
- **Validation**: Compare against existing `data/cs-handbook.md`
- **Requirements**: Add `docling` to `src/requirements.txt`

## Cross-Platform Development Strategy

### Mac Local Development:
- **Fast Iteration**: Process document samples for quick validation
- **Dependency Management**: Ensure Docling works with Apple Silicon and Intel Macs
- **Fallback Testing**: Validate that existing PyMuPDF approach still works as backup

### Vast.ai GPU VM Deployment:
- **Full Processing**: Complete document conversion with all tables
- **Performance Optimization**: Leverage GPU acceleration if Docling supports it
- **Memory Management**: Handle large PDF processing within VM constraints

### Platform-Specific Configuration:
```python
def get_docling_config():
    """Platform-specific Docling configuration"""
    import platform

    if platform.system() == 'Darwin':  # Mac
        return {
            'processing_mode': 'cpu',
            'chunk_size': 'medium',
            'parallel_processing': False,  # Avoid Mac-specific issues
        }
    else:  # Vast.ai Ubuntu
        return {
            'processing_mode': 'gpu' if torch.cuda.is_available() else 'cpu',
            'chunk_size': 'large',
            'parallel_processing': True,
        }
```

## Migration Note
Keep existing files during development for A/B testing:
- `data/cs-handbook.md` (current, with missing tables)
- `data/cs-handbook-docling.md` (new, complete version)
- Use environment variable to switch between versions in `build_index.py`
- Test on Mac first, then validate on Vast.ai VM
