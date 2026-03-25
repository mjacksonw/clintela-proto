#!/usr/bin/env bash
# =============================================================================
# Clintela VM: GitHub deploy key setup
#
# Generates an Ed25519 SSH key scoped to the Clintela repo and configures
# ~/.ssh/config to use it for GitHub. No agent forwarding needed.
#
# Usage:
#   ./setup-deploy-key.sh
# =============================================================================
set -euo pipefail

KEY_PATH="$HOME/.ssh/clintela_deploy"
SSH_CONFIG="$HOME/.ssh/config"

# -------------------------------------------------------------------------
# 1. Generate key if it doesn't exist
# -------------------------------------------------------------------------
if [ -f "$KEY_PATH" ]; then
  echo "Deploy key already exists: $KEY_PATH"
else
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "clintela-deploy-key"
  echo "Generated deploy key: $KEY_PATH"
fi

# -------------------------------------------------------------------------
# 2. Configure ~/.ssh/config
# -------------------------------------------------------------------------
if grep -q "# clintela-deploy-key" "$SSH_CONFIG" 2>/dev/null; then
  echo "SSH config already has clintela entry"
else
  cat >> "$SSH_CONFIG" <<EOF

# clintela-deploy-key
Host github.com
  HostName github.com
  User git
  IdentityFile $KEY_PATH
  IdentitiesOnly yes
EOF
  chmod 600 "$SSH_CONFIG"
  echo "Updated ~/.ssh/config"
fi

# -------------------------------------------------------------------------
# 3. Print the public key + instructions
# -------------------------------------------------------------------------
echo ""
echo "================================================"
echo "  Add this deploy key to your GitHub repo:"
echo "================================================"
echo ""
echo "  1. Go to: https://github.com/mjacksonw/clintela-proto/settings/keys"
echo "  2. Click 'Add deploy key'"
echo "  3. Title: $(hostname) VM"
echo "  4. Paste this key:"
echo ""
cat "$KEY_PATH.pub"
echo ""
echo "  5. Check 'Allow write access' if you want to push from the VM"
echo "  6. Click 'Add key'"
echo ""
echo "  Then test with: ssh -T git@github.com"
echo ""
