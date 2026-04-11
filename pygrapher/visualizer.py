from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import networkx as nx


def draw_graph(graph: nx.DiGraph, output_path: Path, figsize=(14, 10)) -> None:
    output_path = Path(output_path)
    plt.figure(figsize=figsize)
    pos = nx.spring_layout(graph, seed=42)

    edge_colors = []
    for _, _, data in graph.edges(data=True):
        edge_colors.append("tab:blue" if data.get("type") == "import" else "tab:orange")

    nx.draw_networkx_nodes(graph, pos, node_size=1200, node_color="lightgray", edgecolors="black")
    nx.draw_networkx_labels(graph, pos, font_size=9)
    nx.draw_networkx_edges(graph, pos, edge_color=edge_colors, arrowsize=18, arrowstyle="-|>")

    legend_elements = [
        plt.Line2D([0], [0], color="tab:blue", lw=2, label="import"),
        plt.Line2D([0], [0], color="tab:orange", lw=2, label="inherits"),
    ]
    plt.legend(handles=legend_elements)
    plt.axis("off")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()
