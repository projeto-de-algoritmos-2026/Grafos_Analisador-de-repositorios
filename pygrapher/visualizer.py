import json
import math
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

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


def _node_border_color(bg_color: str) -> str:
    color_map = {
        "#1f77b4": "#155080",
        "#b0b0b0": "#808080",
        "#2ca02c": "#1a6b1a",
    }
    return color_map.get(bg_color, "#333333")


def _node_size(degree: int, max_degree: int, min_size: int = 20, max_size: int = 60) -> int:
    if max_degree == 0:
        return min_size
    ratio = degree / max_degree
    return int(min_size + ratio * (max_size - min_size))


def _ring_radius(num_nodes: int) -> int:
    base = 80
    scale = math.sqrt(num_nodes) * 18
    return int(base + scale)


def _make_svg_url(label: str, bg_color: str, size: int) -> str:
    """Gera um data URL com SVG de círculo colorido + número centralizado."""
    dim = size * 2
    font_size = max(10, min(int(size * 0.7), 28))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}">'
        f'<circle cx="{size}" cy="{size}" r="{size - 1}" fill="{bg_color}"/>'
        f'<text x="{size}" y="{size}" dominant-baseline="central" text-anchor="middle" '
        f'font-family="Tahoma,Arial,sans-serif" font-size="{font_size}" '
        f'font-weight="bold" fill="#ffffff">{label}</text>'
        f'</svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def _compute_positions(nodes_by_degree: list, num_nodes: int, center_x: float = 0, center_y: float = 0) -> dict:
    positions = {}
    if not nodes_by_degree:
        return positions

    radius_step = _ring_radius(num_nodes)
    remaining = list(nodes_by_degree)
    ring_capacities = [1, 6, 12, 20, 30, 42, 56, 72]
    rings = []
    for cap in ring_capacities:
        if not remaining:
            break
        rings.append(remaining[:cap])
        remaining = remaining[cap:]
    if remaining:
        rings.append(remaining)

    for ring_idx, ring_nodes in enumerate(rings):
        radius = ring_idx * radius_step
        count = len(ring_nodes)

        if count == 1 and ring_idx == 0:
            positions[ring_nodes[0]] = (center_x, center_y)
            continue

        for i, node in enumerate(ring_nodes):
            angle = (2 * math.pi * i / count) - (math.pi / 2)
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            positions[node] = (x, y)

    return positions


def _edge_tooltip(source: str, target: str, data: dict, node_index: dict) -> str:
    src_label = f"#{node_index.get(source, '?')} {Path(source).name}"
    tgt_label = f"#{node_index.get(target, '?')} {Path(target).name}"
    edge_type = data.get("type", "import")
    kind = data.get("import_kind", "")

    if edge_type == "import":
        kind_str = f" ({kind})" if kind else ""
        return f"import{kind_str}\n{src_label} → {tgt_label}"
    else:
        return f"inherits\n{src_label} → {tgt_label}"


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

    degrees = dict(graph.degree())
    max_degree = max(degrees.values()) if degrees else 1
    num_nodes = graph.number_of_nodes()

    node_list = sorted(graph.nodes(), key=lambda n: degrees[n])
    node_index = {node: i + 1 for i, node in enumerate(sorted(graph.nodes()))}

    positions = _compute_positions(node_list, num_nodes)

    for node in graph.nodes():
        node_color = _node_color(node)
        border_color = _node_border_color(node_color)
        label = str(node_index[node])
        tooltip = f"#{node_index[node]}  {node}\nGrau: {degrees[node]}"
        size = _node_size(degrees[node], max_degree)
        x, y = positions.get(node, (0, 0))
        svg_url = _make_svg_url(label, node_color, size)

        net.add_node(
            node,
            label=" ",
            title=tooltip,
            shape="circularImage",
            image=svg_url,
            color={
                "border": border_color,
                "highlight": {"border": "#000000"},
                "hover": {"border": "#000000"},
            },
            font={"size": 1, "color": "#00000000"},
            size=size,
            x=x,
            y=y,
            physics=False,
        )

    if mode == "full":
        edges_to_draw = list(graph.edges(data=True))
    elif mode == "imports":
        edges_to_draw = [e for e in graph.edges(data=True) if e[2].get("type") == "import"]
    elif mode == "packages":
        edges_to_draw = [e for e in graph.edges(data=True) if e[2].get("type") == "import" and e[2].get("import_kind") == "package"]
    elif mode == "class-imports":
        edges_to_draw = [e for e in graph.edges(data=True) if e[2].get("type") == "import" and e[2].get("import_kind") == "class"]
    else:
        edges_to_draw = [e for e in graph.edges(data=True) if e[2].get("type") == "inherits"]

    for source, target, data in edges_to_draw:
        is_import = data.get("type") == "import"
        edge_color = "#444444" if is_import else "#ff7f0e"
        tooltip = _edge_tooltip(source, target, data, node_index)

        net.add_edge(
            source,
            target,
            color={"color": edge_color, "highlight": "#000000", "hover": "#000000"},
            title=tooltip,
            arrows="to",
            physics=False,
            width=1.2,
            smooth={"enabled": True, "type": "dynamic", "roundness": 0.15},
        )

    net.set_options(json.dumps({
        "nodes": {"borderWidth": 2, "borderWidthSelected": 4},
        "edges": {
            "smooth": {"enabled": True, "type": "dynamic", "roundness": 0.15},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
            "color": {"inherit": False},
            "selectionWidth": 2,
        },
        "physics": {"enabled": False},
        "interaction": {
            "hover": True,
            "multiselect": True,
            "dragNodes": True,
            "tooltipDelay": 60,
            "zoomView": True,
            "dragView": True,
        },
        "manipulation": {"enabled": False},
    }))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.show(str(output_path), notebook=False)