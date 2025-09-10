#!/usr/bin/env bash
set -euo pipefail

# Minimal VM bootstrap: install Docker Engine + Compose plugin and NVIDIA Container Toolkit.
# Usage: bash scripts/vm-bootstrap.sh

export DEBIAN_FRONTEND=noninteractive
echo "[vm-bootstrap] Installing base packages..."
apt-get update -y
apt-get install -y curl ca-certificates git gnupg lsb-release jq

if ! command -v docker >/dev/null 2>&1; then
  echo "[vm-bootstrap] Installing Docker Engine + Compose plugin..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if ! command -v nvidia-ctk >/dev/null 2>&1; then
  echo "[vm-bootstrap] Installing NVIDIA Container Toolkit..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor \
    -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -y
  apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker || true
fi

echo "[vm-bootstrap] Done. Docker: $(docker --version) | Compose: $(docker compose version)"
