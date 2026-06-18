#!/usr/bin/env bash
# Regenerate the call graph + API stub from the notebook, then build the Sphinx docs.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=.venv_MFA/bin

mkdir -p docs/source/_generated docs/source/_static

"$VENV/jupytext" --to py:percent Rud_Gallium_MFA_3.ipynb \
    --output docs/source/_generated/Rud_Gallium_MFA_3.py

"$VENV/python" docs/build_callgraphs.py

"$VENV/python" docs/extract_api.py

"$VENV/python" -m sphinx -b html docs/source docs/build "$@"

echo "Docs built at docs/build/index.html"
