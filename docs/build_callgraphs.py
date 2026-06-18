"""Build two interactive function graphs from the jupytext-exported notebook module:

1. callgraph.html      -- which defined functions call which other defined functions.
2. execution_order.html -- the order functions are actually invoked in the
   notebook's driver code (module-level statements, outside function bodies).

Both are rendered with pyvis (vis.js) as standalone, self-contained HTML files
so they can be embedded in the Sphinx docs via an iframe and stay interactive
(pan/zoom/drag) without needing a server.
"""
import ast
from pathlib import Path

from pyvis.network import Network

SRC = Path(__file__).parent / "source" / "_generated" / "Rud_Gallium_MFA_3.py"
OUT_DIR = Path(__file__).parent / "source" / "_static"


def docstring_summary(node):
    doc = ast.get_docstring(node)
    return doc.splitlines()[0] if doc else ""


def build_call_graph(tree, functions):
    """Edges: function A -> function B if A's body calls B (both locally defined)."""
    edges = set()
    for func in functions.values():
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id != func.name
            ):
                edges.add((func.name, node.func.id))
    return edges


def build_execution_order(tree, functions):
    """Sequence of (step, function_name) for calls made in top-level driver code."""
    sequence = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.Import, ast.ImportFrom)):
            continue
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in functions:
                    sequence.append(node.func.id)
    return list(enumerate(sequence, start=1))


def render_call_graph(functions, edges, out_path):
    net = Network(
        height="700px", width="100%", directed=True, notebook=False,
        cdn_resources="in_line", bgcolor="#ffffff",
    )
    net.barnes_hut(spring_length=180, spring_strength=0.02)
    called = {callee for _, callee in edges}
    calling = {caller for caller, _ in edges}
    for name, func in functions.items():
        net.add_node(
            name,
            label=name,
            title=docstring_summary(func) or name,
            shape="box",
            color="#8fbcd4" if name in (called | calling) else "#d9d9d9",
        )
    for caller, callee in edges:
        net.add_edge(caller, callee, arrows="to")
    net.show_buttons(filter_=["physics"])
    net.write_html(str(out_path), open_browser=False, notebook=False)


def render_execution_order(functions, sequence, out_path):
    net = Network(
        height=f"{150 + 140 * len(sequence)}px", width="100%", directed=True,
        notebook=False, cdn_resources="in_line", bgcolor="#ffffff",
    )
    net.set_options("""
    var options = {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "nodeSpacing": 160,
          "levelSeparation": 120
        }
      },
      "physics": { "enabled": false },
      "edges": { "arrows": "to", "smooth": false }
    }
    """)
    node_ids = []
    for step, name in sequence:
        node_id = f"{step}. {name}"
        node_ids.append(node_id)
        net.add_node(
            node_id,
            label=node_id,
            title=docstring_summary(functions[name]) or name,
            shape="box",
            color="#a8d8a0",
        )
    for a, b in zip(node_ids, node_ids[1:]):
        net.add_edge(a, b)
    net.write_html(str(out_path), open_browser=False, notebook=False)


def main():
    tree = ast.parse(SRC.read_text())
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    edges = build_call_graph(tree, functions)
    sequence = build_execution_order(tree, functions)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_call_graph(functions, edges, OUT_DIR / "callgraph.html")
    render_execution_order(functions, sequence, OUT_DIR / "execution_order.html")

    print(f"{len(functions)} functions, {len(edges)} call-graph edges, "
          f"{len(sequence)} execution steps")


if __name__ == "__main__":
    main()
