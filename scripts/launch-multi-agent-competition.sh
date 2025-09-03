#!/bin/bash

# Multi-Agent Cursor Competition Launcher
# Launch multiple Cursor instances for document processing competition

PROJECT_ROOT="/Users/Malik/code/malikbou/ucl/thesis/on-premise-slm"
CURSOR_PROFILES_ROOT="$HOME/.cursor-agents"

echo "🚀 Starting Multi-Agent Document Processing Competition"
echo "=============================================="

# Create profile directories if they don't exist
mkdir -p "$CURSOR_PROFILES_ROOT/agent1-conservative"
mkdir -p "$CURSOR_PROFILES_ROOT/agent2-aggressive"
mkdir -p "$CURSOR_PROFILES_ROOT/agent3-hybrid"

echo "📁 Created isolated Cursor profile directories"

# Function to launch Cursor with specific profile and branch
launch_agent() {
    local agent_num=$1
    local approach=$2
    local branch=$3
    local profile_dir="$CURSOR_PROFILES_ROOT/agent${agent_num}-${approach}"

    echo "🔧 Launching Agent ${agent_num} (${approach}) on branch ${branch}"
    echo "   Profile: ${profile_dir}"
    echo "   Project: ${PROJECT_ROOT}"

    # Launch Cursor with isolated profile
    cursor --user-data-dir="$profile_dir" "$PROJECT_ROOT" &

    # Give it a moment to start
    sleep 2
}

echo ""
echo "🎯 Competition Branches:"
echo "   Agent 1: agent-1-conservative-docprocessing"
echo "   Agent 2: agent-2-aggressive-docprocessing"
echo "   Agent 3: agent-3-hybrid-docprocessing"
echo ""

# Launch all three agents
launch_agent 1 "conservative" "agent-1-conservative-docprocessing"
launch_agent 2 "aggressive" "agent-2-aggressive-docprocessing"
launch_agent 3 "hybrid" "agent-3-hybrid-docprocessing"

echo ""
echo "✅ All agents launched! You should now have 3 Cursor windows open."
echo ""
echo "📋 Next Steps:"
echo "   1. In each Cursor window, switch to the respective branch:"
echo "      Window 1: git checkout agent-1-conservative-docprocessing"
echo "      Window 2: git checkout agent-2-aggressive-docprocessing"
echo "      Window 3: git checkout agent-3-hybrid-docprocessing"
echo ""
echo "   2. Use the agent-specific prompts in .agent-prompts/competition/agent-prompts.md"
echo "   3. Each agent should read .agent-prompts/document-processor.md first"
echo "   4. Agents must create implementation plans and get approval before coding"
echo ""
echo "🔍 Monitor progress and use scripts/evaluate-competition.sh when ready to compare"
