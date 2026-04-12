from typing import Callable, List, Optional, Set

import networkx as nx


def build_import_subgraph(graph: nx.DiGraph) -> nx.DiGraph:
    import_graph = nx.DiGraph()
    import_graph.add_nodes_from(graph.nodes(data=True))

    for source, target, data in graph.edges(data=True):
        if data.get("type") == "import":
            import_graph.add_edge(source, target, **data)

    return import_graph


def reverse_graph(graph: nx.DiGraph) -> nx.DiGraph:
    reversed_g = nx.DiGraph()
    reversed_g.add_nodes_from(graph.nodes(data=True))

    for source, target, data in graph.edges(data=True):
        reversed_g.add_edge(target, source, **data)

    return reversed_g


def dfs_post_order(graph: nx.DiGraph) -> List[str]:
    visited: Set[str] = set()
    post_order: List[str] = []

    def visit(vertex: str) -> None:
        visited.add(vertex)

        for neighbor in graph.successors(vertex):
            if neighbor not in visited:
                visit(neighbor)

        post_order.append(vertex)

    for vertex in graph.nodes():
        if vertex not in visited:
            visit(vertex)

    return post_order


def collect_component(
    graph: nx.DiGraph,
    start: str,
    visited: Set[str],
    component: List[str],
) -> None:
    visited.add(start)
    component.append(start)

    for neighbor in graph.successors(start):
        if neighbor not in visited:
            collect_component(graph, neighbor, visited, component)


def kosaraju_scc(graph: nx.DiGraph) -> List[List[str]]:
    post_order = dfs_post_order(graph)
    reversed_g = reverse_graph(graph)

    visited: Set[str] = set()
    components: List[List[str]] = []

    for vertex in reversed(post_order):
        if vertex not in visited:
            component: List[str] = []
            collect_component(reversed_g, vertex, visited, component)
            components.append(component)

    return components


def find_import_sccs(
    graph: nx.DiGraph,
    status_callback: Optional[Callable[[str], None]] = None,
) -> List[List[str]]:
    if status_callback:
        status_callback("[4/5] Detectando SCCs de import...")

    import_graph = build_import_subgraph(graph)
    components = kosaraju_scc(import_graph)

    cyclic_components: List[List[str]] = []

    for component in components:
        if len(component) > 1:
            cyclic_components.append(sorted(component))
            continue

        node = component[0]
        if import_graph.has_edge(node, node):
            cyclic_components.append(component)

    return cyclic_components
