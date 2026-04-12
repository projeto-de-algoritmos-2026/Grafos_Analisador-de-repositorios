import json
import math
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import quote

import networkx as nx
from pyvis.network import Network

# Paleta de cores para SCCs (até 12 ciclos distintos)
SCC_PALETTE = [
    "#ff1744", "#ff6d00", "#ffd600", "#00e676", "#00e5ff",
    "#2979ff", "#d500f9", "#ff4081", "#76ff03", "#ffab00",
    "#f50057", "#1de9b6",
]


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


def _inject_scc_controls(html_path: Path, node_scc_map: dict, node_default_svgs: dict, node_scc_svgs: dict, scc_info: list, sink_nodes: set, node_index_map: dict, topo_order: list, original_positions: dict) -> None:
    """Injeta botões e script JS para visualização de SCCs e Topologia no HTML."""
    html = html_path.read_text(encoding="utf-8")

    node_scc_js = json.dumps(node_scc_map)
    default_svgs_js = json.dumps(node_default_svgs)
    scc_svgs_js = json.dumps(node_scc_svgs)
    scc_info_js = json.dumps(scc_info)
    sink_nodes_js = json.dumps(list(sink_nodes))
    sink_nodes_nums_js = json.dumps(sorted([node_index_map[n] for n in sink_nodes if n in node_index_map]))

    # Preparação das posições topológicas
    layer_map: dict = {}
    for item in topo_order:
        layer = item["layer"]
        for node in item["full_paths"]:
            layer_map[node] = layer

    layer_counts: dict = {}
    layer_cursors: dict = {}
    for node, layer in layer_map.items():
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    for layer in layer_counts:
        layer_cursors[layer] = 0

    topo_positions: dict = {}
    H_SPACING = 320
    V_SPACING = 100
    for node, layer in layer_map.items():
        idx = layer_cursors[layer]
        count = layer_counts[layer]
        x = layer * H_SPACING
        y = (idx - count / 2) * V_SPACING
        topo_positions[node] = {"x": x, "y": y}
        layer_cursors[layer] += 1

    topo_positions_js = json.dumps(topo_positions)
    original_pos_js = json.dumps({node: {"x": float(xy[0]), "y": float(xy[1])} for node, xy in original_positions.items()})

    inject = f"""
<style>
  #scc-controls {{
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  }}
  #scc-controls button {{
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    box-shadow: 0 4px 6px rgba(0,0,0,0.15);
    transition: all 0.2s ease;
    color: white;
  }}
  #btn-show-scc  {{ background: #ef4444; }}
  #btn-reset-scc {{ background: #3b82f6; display: none; }}
  #btn-show-topo {{ background: #8b5cf6; }}
  #btn-reset-topo {{ background: #3b82f6; display: none; }}
  
  #scc-controls button:hover {{ transform: translateY(-1px); opacity: 0.9; }}
  
  #scc-legend {{
    background: rgba(255,255,255,0.98);
    border-radius: 12px;
    padding: 15px;
    display: none;
    font-size: 13px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.1);
    max-width: 320px;
    max-height: 60vh;
    overflow-y: auto;
    border: 1px solid #e5e7eb;
  }}
  .scc-group {{ margin-bottom: 8px; border-bottom: 1px solid #f3f4f6; padding-bottom: 6px; }}
  .scc-group:last-child {{ border-bottom: none; }}
  
  .scc-header {{ 
    display: flex; 
    align-items: center; 
    gap: 8px; 
    cursor: pointer; 
    user-select: none;
    padding: 4px;
    border-radius: 4px;
  }}
  .scc-header:hover {{ background: #f9fafb; }}
  
  .scc-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
  .scc-arrow {{ font-size: 10px; color: #6b7280; transition: transform 0.2s; }}
  .scc-details {{ 
    display: none; 
    padding: 5px 0 5px 24px; 
    font-size: 12px; 
    color: #4b5563; 
    line-height: 1.4;
    word-break: break-all;
  }}
  
  body, #mynetwork, canvas {{ background-color: #f3f4f6 !important; }}
</style>

<div id="scc-controls">
  <button id="btn-show-scc">🔍 Ver SCCs</button>
  <button id="btn-reset-scc">↩️ Resetar SCCs</button>
  <button id="btn-show-topo">📊 Ver Topologia</button>
  <button id="btn-reset-topo">↩️ Resetar Topo</button>
  <div id="scc-legend"></div>
</div>

<script type="text/javascript">
(function() {{
  var NODE_SCC      = {node_scc_js};
  var DEFAULT_SVGS  = {default_svgs_js};
  var SCC_SVGS      = {scc_svgs_js};
  var SCC_INFO      = {scc_info_js};
  var SINK_NODES    = {sink_nodes_js};
  var SINK_NODES_NUMS = {sink_nodes_nums_js};
  var TOPO_POS      = {topo_positions_js};
  var ORIGINAL_POS  = {original_pos_js};

  function waitForNetwork(cb) {{
    for (var key in window) {{
      try {{
        if (window[key] && window[key].body && window[key].canvas) {{
          cb(window[key]); return;
        }}
      }} catch(e) {{}}
    }}
    setTimeout(function() {{ waitForNetwork(cb); }}, 150);
  }}

  window.addEventListener("load", function() {{
    waitForNetwork(function(network) {{

      // Lógica SCC
      document.getElementById("btn-show-scc").addEventListener("click", function() {{
        var updates = [];
        for (var nodeId in NODE_SCC) {{
          var newSvg = SCC_SVGS[nodeId];
          if (newSvg) updates.push({{ id: nodeId, image: newSvg }});
        }}
        var sinkUpdates = SINK_NODES.map(function(n) {{
          return {{ id: n, borderWidth: 6, color: {{ border: "#111827" }} }};
        }});
        if (sinkUpdates.length > 0) network.body.data.nodes.update(sinkUpdates);
        network.body.data.nodes.update(updates);

        var legend = document.getElementById("scc-legend");
        legend.innerHTML = "<div style='font-weight:bold; margin-bottom:10px; color:#111827'>Componentes Conexos (" + SCC_INFO.length + ")</div>";
        
        SCC_INFO.forEach(function(scc, i) {{
          var group = document.createElement("div");
          group.className = "scc-group";

          var header = document.createElement("div");
          header.className = "scc-header";
          
          var dot = document.createElement("div");
          dot.className = "scc-dot";
          dot.style.background = scc.color;
          
          var arrow = document.createElement("span");
          arrow.className = "scc-arrow";
          arrow.textContent = "▶";
          
          var label = document.createElement("span");
          label.innerHTML = "<b>Ciclo " + (i+1) + "</b> (" + scc.nodes.length + " arquivos)";

          header.appendChild(dot);
          header.appendChild(arrow);
          header.appendChild(label);

          var details = document.createElement("div");
          details.className = "scc-details";
          details.textContent = "Nós: " + scc.nums.join(", ");

          header.onclick = function() {{
            var isHidden = details.style.display === "none" || details.style.display === "";
            details.style.display = isHidden ? "block" : "none";
            arrow.textContent = isHidden ? "▼" : "▶";
          }};

          group.appendChild(header);
          group.appendChild(details);
          legend.appendChild(group);
        }});

        legend.style.display = "block";
        document.getElementById("btn-show-scc").style.display = "none";
        document.getElementById("btn-reset-scc").style.display = "block";
      }});

      document.getElementById("btn-reset-scc").addEventListener("click", function() {{
        var updates = [];
        for (var nodeId in DEFAULT_SVGS) {{
          updates.push({{ id: nodeId, image: DEFAULT_SVGS[nodeId] }});
        }}
        network.body.data.nodes.update(updates);
        document.getElementById("scc-legend").style.display = "none";
        document.getElementById("btn-show-scc").style.display = "block";
        document.getElementById("btn-reset-scc").style.display = "none";
      }});

      // Lógica Topologia
      document.getElementById("btn-show-topo").addEventListener("click", function() {{
        var moveUpdates = [];
        for (var nodeId in TOPO_POS) {{
          moveUpdates.push({{ id: nodeId, x: TOPO_POS[nodeId].x, y: TOPO_POS[nodeId].y }});
        }}
        network.body.data.nodes.update(moveUpdates);
        network.fit({{ animation: {{ duration: 1000, easingFunction: "easeInOutQuad" }} }});
        document.getElementById("btn-show-topo").style.display = "none";
        document.getElementById("btn-reset-topo").style.display = "block";
      }});

      document.getElementById("btn-reset-topo").addEventListener("click", function() {{
        var moveUpdates = [];
        for (var nodeId in ORIGINAL_POS) {{
          moveUpdates.push({{ id: nodeId, x: ORIGINAL_POS[nodeId].x, y: ORIGINAL_POS[nodeId].y }});
        }}
        network.body.data.nodes.update(moveUpdates);
        network.fit({{ animation: {{ duration: 1000, easingFunction: "easeInOutQuad" }} }});
        document.getElementById("btn-show-topo").style.display = "block";
        document.getElementById("btn-reset-topo").style.display = "none";
      }});
    }});
  }});
}})();
</script>
"""

    if "</body>" in html:
        html = html.replace("</body>", inject + "\n</body>")
    else:
        html += inject

    html_path.write_text(html, encoding="utf-8")


def draw_graph(
    graph: nx.DiGraph,
    output_path: Path,
    mode: str = "imports",
    figsize=(24, 18),
    dpi=300,
    sccs: Optional[List[List[str]]] = None,
    topo_order: Optional[List[dict]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    if status_callback:
        status_callback("[6/6] Gerando visualização interativa...")

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

    node_scc_map = {}
    scc_info = []
    sink_nodes = {n for n in graph.nodes() if graph.out_degree(n) == 0}

    if sccs:
        for scc_idx, component in enumerate(sccs):
            color = SCC_PALETTE[scc_idx % len(SCC_PALETTE)]
            short_names = [Path(n).name for n in component]
            node_nums = sorted([node_index[n] for n in component])
            is_cyclic = len(component) > 1 or graph.has_edge(component[0], component[0])
            scc_info.append({
                "color": color, 
                "nodes": short_names, 
                "nums": node_nums, 
                "cyclic": is_cyclic, 
                "size": len(component)
            })
            for node in component:
                node_scc_map[node] = color

    node_default_svgs = {}
    node_scc_svgs = {}

    for node in graph.nodes():
        node_color = _node_color(node)
        border_color = _node_border_color(node_color)
        label = str(node_index[node])
        size = _node_size(degrees[node], max_degree)
        x, y = positions.get(node, (0, 0))

        is_sink = node in sink_nodes
        sink_marker = "\n⬇ sink node" if is_sink else ""
        tooltip = f"#{node_index[node]}  {node}\nGrau: {degrees[node]}{sink_marker}"

        default_svg = _make_svg_url(label, node_color, size)
        node_default_svgs[node] = default_svg

        if node in node_scc_map:
            scc_color = node_scc_map[node]
            node_scc_svgs[node] = _make_svg_url(label, scc_color, size)

        sink_border = "#111827" if is_sink else border_color
        sink_border_width = 5 if is_sink else 2

        net.add_node(
            node,
            label=" ",
            title=tooltip,
            shape="circularImage",
            image=default_svg,
            color={"border": sink_border, "highlight": {"border": "#000000"}},
            borderWidth=sink_border_width,
            font={"size": 1, "color": "#00000000"},
            size=size,
            x=x,
            y=y,
            physics=False,
        )

    # Filtragem de arestas
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
        edge_color = "#6b7280" if is_import else "#f97316"
        tooltip = _edge_tooltip(source, target, data, node_index)

        net.add_edge(
            source,
            target,
            color={"color": edge_color, "highlight": "#111827"},
            title=tooltip,
            arrows="to",
            physics=False,
            width=1.5,
            smooth={"enabled": True, "type": "curvedCW", "roundness": 0.2},
        )

    net.set_options(json.dumps({
        "physics": {"enabled": False},
        "interaction": {"hover": True, "multiselect": True, "dragNodes": True, "zoomView": True},
        "edges": {"smooth": {"enabled": True, "type": "curvedCW"}},
    }))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.show(str(output_path), notebook=False)

    _inject_scc_controls(output_path, node_scc_map, node_default_svgs, node_scc_svgs, scc_info, sink_nodes, node_index, topo_order or [], positions)