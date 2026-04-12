from pathlib import Path
from typing import Callable, Dict, List, Optional

import networkx as nx


def build_condensed_graph(
    graph: nx.DiGraph,
    sccs: List[List[str]],
) -> tuple:
    """
    Constrói o grafo condensado: cada SCC vira um super-nó.
    Retorna (condensed_graph, node_to_scc_idx).
    """
    node_to_scc: Dict[str, int] = {}
    for scc_idx, component in enumerate(sccs):
        for node in component:
            node_to_scc[node] = scc_idx

    condensed = nx.DiGraph()
    for scc_idx in range(len(sccs)):
        condensed.add_node(scc_idx)

    for source, target in graph.edges():
        src_scc = node_to_scc.get(source)
        tgt_scc = node_to_scc.get(target)
        if src_scc is not None and tgt_scc is not None and src_scc != tgt_scc:
            condensed.add_edge(src_scc, tgt_scc)

    return condensed, node_to_scc


def topological_sort_sccs(
    sccs: List[List[str]],
    graph: nx.DiGraph,
    status_callback: Optional[Callable[[str], None]] = None,
) -> List[int]:
    """
    Realiza ordenação topológica no grafo condensado dos SCCs.
    Retorna lista de índices de SCCs em ordem topológica.
    """
    if status_callback:
        status_callback("[5/5] Calculando ordenação topológica...")

    condensed, _ = build_condensed_graph(graph, sccs)
    order = list(nx.topological_sort(condensed))
    return order


def compute_topo_layers(
    sccs: List[List[str]],
    graph: nx.DiGraph,
) -> Dict[int, int]:
    """
    Calcula a camada (profundidade) de cada SCC no grafo condensado.
    Camada 0 = sem dependências (source nodes).
    Retorna dict: scc_idx → layer.
    """
    condensed, _ = build_condensed_graph(graph, sccs)

    layers: Dict[int, int] = {}
    for node in nx.topological_sort(condensed):
        preds = list(condensed.predecessors(node))
        if not preds:
            layers[node] = 0
        else:
            layers[node] = max(layers[p] for p in preds) + 1

    return layers


def find_topological_order(
    graph: nx.DiGraph,
    sccs: List[List[str]],
    node_index: Dict[str, int],
    status_callback: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    """
    Retorna a ordem topológica como lista de dicts com info de cada SCC.
    Cada item: { order, scc_idx, nodes, nums, layer }
    """
    if status_callback:
        status_callback("[5/5] Calculando ordenação topológica...")

    topo_order = topological_sort_sccs(sccs, graph)
    layers = compute_topo_layers(sccs, graph)

    result = []
    for order_idx, scc_idx in enumerate(topo_order):
        component = sccs[scc_idx]
        nums = sorted([node_index[n] for n in component if n in node_index])
        result.append({
            "order": order_idx + 1,
            "scc_idx": scc_idx,
            "nodes": [Path(n).name for n in component],
            "full_paths": component,
            "nums": nums,
            "layer": layers.get(scc_idx, 0),
        })

    return result
