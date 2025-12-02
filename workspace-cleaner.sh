#!/bin/bash

set -euo pipefail

echo "=== STARTING SYSTEM CLEANUP ==="

# 1. Clean up Jenkins workspace leftovers
echo "Cleaning Jenkins workspaces..."
JENKINS_HOME="/var/lib/jenkins"
if [ -d "$JENKINS_HOME/workspace" ]; then
    find "$JENKINS_HOME/workspace" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
    echo "Jenkins workspaces cleaned."
fi

# 2. Remove Conda package caches
echo "Cleaning Conda package cache..."
if [ -d "$JENKINS_HOME/.conda/pkgs" ]; then
    rm -rf "$JENKINS_HOME/.conda/pkgs"/*
    echo "Conda package cache cleared."
fi

# 3. Remove old Conda environments (optional, only those not currently used)
# Uncomment if you want to aggressively remove unused envs
# echo "Removing unused Conda environments..."
# conda env list | awk '{print $1}' | grep -vE "^(#|base|clinvar_anno_env)$" | xargs -I {} conda env remove -n {}

# 4. Clean pip cache
echo "Cleaning pip cache..."
if [ -d "$JENKINS_HOME/.cache/pip" ]; then
    rm -rf "$JENKINS_HOME/.cache/pip"/*
    echo "pip cache cleared."
fi

# 5. Clean Docker system
echo "Cleaning Docker system..."
if command -v docker >/dev/null 2>&1; then
    docker system prune -af
    docker volume prune -f
    echo "Docker system cleaned."
fi

# 6. Optional: Clean apt cache (if Debian/Ubuntu)
if command -v apt-get >/dev/null 2>&1; then
    echo "Cleaning apt cache..."
    sudo apt-get clean
    echo "apt cache cleared."
fi

# 7. Optional: Clean /tmp
echo "Cleaning /tmp..."
sudo rm -rf /tmp/*
echo "/tmp cleared."

echo "=== SYSTEM CLEANUP COMPLETE ==="
