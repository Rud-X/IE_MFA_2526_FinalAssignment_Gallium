#!/usr/bin/env bash
# Regenerate the call graph + API stub from the notebook, then build the Sphinx docs.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=.venv_MFA/bin

mkdir -p docs/source/_generated

"$VENV/jupytext" --to py:percent Rud_Gallium_MFA.ipynb \
    --output docs/source/_generated/Rud_Gallium_MFA.py

# Copy the notebook into the docs tree so nbsphinx can render it (referenced
# by the toctree in index.rst). Outputs are reused, not re-executed.
cp Rud_Gallium_MFA.ipynb docs/source/_generated/Rud_Gallium_MFA.ipynb

"$VENV/python" docs/extract_api.py

"$VENV/python" -m sphinx -b html docs/source docs/build "$@"

echo "Docs built at docs/build/index.html"
