#!/usr/bin/env bash
set -euo pipefail

# Fetch results from a remote VM to the local machine using rsync over SSH.
# Usage: scripts/fetch-results.sh <ssh_user>@<vm_ip> [remote_project_dir] [local_out_dir] [ssh_port]
# Example: scripts/fetch-results.sh root@77.104.167.149 /root/on-premise-slm ./results_remote 53295

REMOTE="${1:?Usage: $0 <ssh_user>@<vm_ip> [remote_project_dir] [local_out_dir] [ssh_port]}"
REMOTE_DIR="${2:-/root/on-premise-slm}"
LOCAL_OUT="${3:-./results_remote}"
SSH_PORT="${4:-22}"

mkdir -p "$LOCAL_OUT"

echo "[fetch-results] Sync benchmarking and throughput results..."
rsync -avzh -e "ssh -p $SSH_PORT" \
  "$REMOTE:$REMOTE_DIR/results/" "$LOCAL_OUT/"

echo "[fetch-results] Copied to: $LOCAL_OUT"
