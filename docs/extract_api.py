"""Extract top-level function definitions from the jupytext-exported notebook
module into a side-effect-free module that Sphinx autodoc can safely import
(skips data loading, plotting, and other top-level execution).
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).parent / "source" / "_generated" / "Rud_Gallium_MFA_3.py"
DST = Path(__file__).parent / "source" / "_generated" / "api.py"


def is_literal_assign(node):
    """True for a top-level Assign/AnnAssign whose value is a plain literal
    (e.g. `use_phase_stage_number = 5`), safe to keep since it has no
    dependency on runtime data loaded elsewhere in the notebook."""
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    try:
        ast.literal_eval(node.value)
        return True
    except (ValueError, TypeError):
        return False


def main():
    tree = ast.parse(SRC.read_text())
    kept = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
        or is_literal_assign(node)
    ]
    new_tree = ast.Module(body=kept, type_ignores=[])
    DST.write_text(ast.unparse(ast.fix_missing_locations(new_tree)) + "\n")
    print(f"Wrote {DST} with {len(kept)} top-level nodes")


if __name__ == "__main__":
    sys.exit(main())
