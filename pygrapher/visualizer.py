import json
from pathlib import Path
from typing import Callable, Optional

import networkx as nx
from pyvis.network import Network


def _node_color(path: str) -> str:
    path_obj = Path(path)
    parts = [part.lower() for part in path_obj.parts]
    lower_name = path_obj.name.lower()

    if "tests" in parts or lower_name.startswith("test_") or lower_name.endswith("_test.py"):
        return "#b0b0b0"
    if "src" in parts:
        return "#1f77b4"
    if any(part in {"doc", "docs", "documentation"} for part in parts) or lower_name in {"setup.py", "pyproject.toml", "requirements.txt"}:
        return "#2ca02c"
    return "#1f77b4"


def _label_color(node_color: str) -> str:
    return "#000000" if node_color != "#b0b0b0" else "#444444"


def _normalize_label(node: str, graph: nx.DiGraph) -> str:
    short_name = Path(node).name
    if sum(1 for candidate in graph.nodes() if Path(candidate).name == short_name) > 1:
        return node
    return short_name


def draw_graph(
    graph: nx.DiGraph,
    output_path: Path,
    mode: str = "imports",
    figsize=(24, 18),
    dpi=300,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    if status_callback:
        status_callback("[4/4] Gerando visualização interativa...")

    mode_aliases = {
        "package": "packages",
        "packages": "packages",
        "class_imports": "class-imports",
        "class-imports": "class-imports",
        "imports": "imports",
        "classes": "classes",
        "full": "full",
    }
    mode = mode_aliases.get(mode, mode)
    if mode not in mode_aliases.values():
        raise ValueError("mode deve ser 'imports', 'packages', 'class-imports', 'classes' ou 'full'.")

    output_path = Path(output_path)
    if output_path.suffix.lower() != ".html":
        output_path = output_path.with_suffix(".html")

    net = Network(height="1000px", width="100%", directed=True)
    net.barnes_hut()

    label_map = {}
    for node in graph.nodes():
        label_map[node] = _normalize_label(node, graph)

    for node in graph.nodes():
        node_color = _node_color(node)
        net.add_node(
            node,
            label=label_map[node],
            title=node,
            color=node_color,
            font={"color": _label_color(node_color), "size": 14},
            shape="dot",
            size=22,
        )

    if mode == "full":
        edges_to_draw = list(graph.edges(data=True))
    elif mode == "imports":
        edges_to_draw = [edge for edge in graph.edges(data=True) if edge[2].get("type") == "import"]
    elif mode == "packages":
        edges_to_draw = [edge for edge in graph.edges(data=True) if edge[2].get("type") == "import" and edge[2].get("import_kind") == "package"]
    elif mode == "class-imports":
        edges_to_draw = [edge for edge in graph.edges(data=True) if edge[2].get("type") == "import" and edge[2].get("import_kind") == "class"]
    else:
        edges_to_draw = [edge for edge in graph.edges(data=True) if edge[2].get("type") == "inherits"]

    for source, target, data in edges_to_draw:
        edge_color = "#1f77b4" if data.get("type") == "import" else "#ff7f0e"
        net.add_edge(
            source,
            target,
            color=edge_color,
            title=data.get("type"),
            arrows="to",
            physics=True,
            smooth={"enabled": True, "type": "cubicBezier"},
        )

    net.set_options(json.dumps({
        "nodes": {
            "borderWidth": 2,
            "shapeProperties": {"useBorderWithImage": True}
        },
        "edges": {
            "smooth": {"enabled": True, "type": "dynamic"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 1.2}}
        },
        "physics": {
            "barnesHut": {
                "gravitationalConstant": -2000,
                "centralGravity": 0.3,
                "springLength": 250,
                "springConstant": 0.05,
                "damping": 0.09
            }
        },
        "interaction": {"hover": True, "multiselect": True, "dragNodes": True},
        "manipulation": {"enabled": False}
    }))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.show(str(output_path), notebook=False)