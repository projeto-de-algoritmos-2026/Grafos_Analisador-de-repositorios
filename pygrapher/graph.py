from pathlib import Path
from typing import Callable, Dict, List, Optional

import networkx as nx


def _module_name_from_path(path: str) -> str:
    path_obj = Path(path)
    parts = list(path_obj.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _build_module_index(parsed: Dict[str, Dict[str, List[str]]]) -> Dict[str, str]:
    index = {}
    for file_path in parsed:
        module_name = _module_name_from_path(file_path)
        index[module_name] = file_path
    return index


def _find_best_target_file(target: str, module_index: Dict[str, str]) -> Optional[str]:
    if target in module_index:
        return module_index[target]

    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in module_index:
            return module_index[prefix]
    return None


def _classify_import(target: str, module_index: Dict[str, str]) -> str:
    if target in module_index:
        return "package"

    parts = target.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in module_index:
            return "package" if i == len(parts) else "class"
    return "class"


def build_graph(
    parsed: Dict[str, Dict[str, List[str]]],
    status_callback: Optional[Callable[[str], None]] = None,
) -> nx.DiGraph:
    if status_callback:
        status_callback("[3/4] Construindo grafo...")

    graph = nx.DiGraph()
    module_index = _build_module_index(parsed)

    for file_path in parsed:
        graph.add_node(file_path)

    for file_path, metadata in parsed.items():
        for target in metadata.get("imports", []):
            target_file = _find_best_target_file(target, module_index)
            if target_file and target_file != file_path:
                import_kind = _classify_import(target, module_index)
                graph.add_edge(file_path, target_file, type="import", import_kind=import_kind)

    class_definitions = {file_path: metadata.get("classes", []) for file_path, metadata in parsed.items()}

    for file_path, metadata in parsed.items():
        for base in metadata.get("classes", []):
            for candidate_path, classes in class_definitions.items():
                if candidate_path != file_path and base in classes:
                    graph.add_edge(file_path, candidate_path, type="inherits")
                    break

    print("Adjacência:")
    for node in sorted(graph.nodes()):
        neighbors = sorted(target for _, target in graph.out_edges(node))
        print(f"{node} → [{', '.join(neighbors)}]")

    return graph
