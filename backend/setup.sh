#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
fi

# Reuse a matching environment on subsequent runs.
if ! backend/.venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' 2>/dev/null; then
    uv venv --python 3.12 backend/.venv
fi
uv pip install --python backend/.venv/bin/python -r backend/requirements.txt

printf '\nReady! From the repository root:\n'
printf '  source backend/.venv/bin/activate\n'
printf '  python -m pytest backend/tests -q\n'
printf '\nOr from backend/:\n'
printf '  source .venv/bin/activate\n'
printf '  python -m pytest tests -q\n'
