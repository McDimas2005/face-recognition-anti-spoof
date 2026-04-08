#!/usr/bin/env bash
set -euo pipefail

cp -n .env.example .env || true
python3 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install -U pip
pip install -e "apps/api[dev]"
npm install

echo "Bootstrap complete."

