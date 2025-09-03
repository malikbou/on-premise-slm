#!/bin/bash

# Multi-Agent Competition Evaluation Script
# Compare outputs from all three document processing agents

PROJECT_ROOT="/Users/Malik/code/malikbou/ucl/thesis/on-premise-slm"
RESULTS_DIR="$PROJECT_ROOT/results/agent-competition"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "🔍 Multi-Agent Competition Evaluation"
echo "====================================="

# Create results directory
mkdir -p "$RESULTS_DIR/$TIMESTAMP"

echo "📊 Evaluation Results Directory: $RESULTS_DIR/$TIMESTAMP"
echo ""

# Function to evaluate a single agent's output
evaluate_agent() {
    local agent_num=$1
    local approach=$2
    local branch=$3
    local output_file="cs-handbook-${approach}.md"
    
    echo "🤖 Evaluating Agent ${agent_num} (${approach})"
    echo "   Branch: ${branch}"
    echo "   Expected Output: data/${output_file}"
    
    # Check if the agent has produced output
    if [ -f "data/${output_file}" ]; then
        echo "   ✅ Output file exists"
        
        # Count tables in output
        table_count=$(grep -c "^|.*|.*|" "data/${output_file}" 2>/dev/null || echo "0")
        echo "   📊 Tables found: ${table_count}"
        
        # Check file size
        file_size=$(ls -lh "data/${output_file}" | awk '{print $5}')
        echo "   📁 File size: ${file_size}"
        
        # Check for missing table markers
        missing_tables=$(grep -c "\[SKIPPING TABLE SECTION" "data/${output_file}" 2>/dev/null || echo "0")
        echo "   ❌ Missing table sections: ${missing_tables}"
        
        # Save detailed analysis
        cat > "$RESULTS_DIR/$TIMESTAMP/agent${agent_num}_${approach}_analysis.txt" << EOF
Agent ${agent_num} (${approach}) - Detailed Analysis
====================================================
Branch: ${branch}
Output File: data/${output_file}
Evaluation Time: $(date)

Metrics:
--------
Tables Extracted: ${table_count}
Missing Table Sections: ${missing_tables}
File Size: ${file_size}
Table Recovery Rate: $(echo "scale=2; (15 - ${missing_tables}) / 15 * 100" | bc -l)%

File Statistics:
---------------
$(wc -l "data/${output_file}")
$(wc -w "data/${output_file}")
$(wc -c "data/${output_file}")

First 10 Lines:
--------------
$(head -10 "data/${output_file}")

Last 10 Lines:
-------------
$(tail -10 "data/${output_file}")

Table Detection:
---------------
$(grep -n "^|.*|.*|" "data/${output_file}" | head -5)

Missing Table Markers:
--------------------
$(grep -n "\[SKIPPING TABLE SECTION" "data/${output_file}")
EOF
        
    else
        echo "   ❌ Output file not found"
        cat > "$RESULTS_DIR/$TIMESTAMP/agent${agent_num}_${approach}_analysis.txt" << EOF
Agent ${agent_num} (${approach}) - Analysis
===========================================
Branch: ${branch}
Status: NO OUTPUT PRODUCED
Evaluation Time: $(date)

Error: Expected output file data/${output_file} was not found.
This agent may not have completed the task or encountered errors.
EOF
    fi
    
    echo ""
}

# Function to check if implementation files exist
check_implementation() {
    local agent_num=$1
    local approach=$2
    local impl_file="src/process_documents_${approach}.py"
    
    echo "🔧 Checking Agent ${agent_num} Implementation"
    
    if [ -f "${impl_file}" ]; then
        echo "   ✅ Implementation file exists: ${impl_file}"
        lines=$(wc -l < "${impl_file}")
        echo "   📝 Lines of code: ${lines}"
    else
        echo "   ❌ Implementation file missing: ${impl_file}"
    fi
    echo ""
}

# Evaluate all three agents
echo "Starting evaluation of all agents..."
echo ""

evaluate_agent 1 "conservative" "agent-1-conservative-docprocessing"
evaluate_agent 2 "aggressive" "agent-2-aggressive-docprocessing"
evaluate_agent 3 "hybrid" "agent-3-hybrid-docprocessing"

echo "🔧 Implementation Check"
echo "======================"
check_implementation 1 "conservative"
check_implementation 2 "aggressive"
check_implementation 3 "hybrid"

# Generate comparison report
echo "📋 Generating Comparison Report"
echo "==============================="

cat > "$RESULTS_DIR/$TIMESTAMP/competition_summary.md" << 'EOF'
# Multi-Agent Document Processing Competition Results

## Competition Overview
Three agents implemented different approaches to PDF-to-Markdown conversion using Docling:
- **Agent 1**: Conservative (reliability-focused)
- **Agent 2**: Aggressive (performance-focused)  
- **Agent 3**: Hybrid (balanced approach)

## Evaluation Criteria
- **Table Recovery**: Number of tables successfully extracted (target: 15+)
- **Processing Time**: Speed of document conversion
- **Code Quality**: Maintainability and documentation
- **Integration**: Compatibility with existing pipeline
- **Cross-Platform**: Mac + Vast.ai performance

## Results Summary

### Agent 1 (Conservative)
- **Output**: [Check analysis file]
- **Tables Extracted**: [Check analysis file]
- **Implementation**: [Check if process_documents_conservative.py exists]
- **Approach**: Focused on reliability and backward compatibility

### Agent 2 (Aggressive)
- **Output**: [Check analysis file]
- **Tables Extracted**: [Check analysis file]
- **Implementation**: [Check if process_documents_aggressive.py exists]
- **Approach**: Focused on performance and cutting-edge features

### Agent 3 (Hybrid)
- **Output**: [Check analysis file]
- **Tables Extracted**: [Check analysis file]
- **Implementation**: [Check if process_documents_hybrid.py exists]
- **Approach**: Balanced reliability with performance

## Winner Selection
**To be determined based on detailed analysis**

## Next Steps
1. Review individual agent analysis files
2. Test implementations with sample queries
3. Measure processing time and memory usage
4. Select winning approach for integration
EOF

echo "✅ Competition evaluation complete!"
echo ""
echo "📊 Results saved to: $RESULTS_DIR/$TIMESTAMP/"
echo ""
echo "📁 Generated files:"
echo "   - competition_summary.md (overview)"
echo "   - agent1_conservative_analysis.txt"
echo "   - agent2_aggressive_analysis.txt" 
echo "   - agent3_hybrid_analysis.txt"
echo ""
echo "🔍 Review the analysis files to determine the winning approach!"
