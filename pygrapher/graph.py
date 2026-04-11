from pathlib import Path
from typing import Dict, List

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


def build_graph(parsed: Dict[str, Dict[str, List[str]]]) -> nx.DiGraph:
    graph = nx.DiGraph()
    module_index = _build_module_index(parsed)

    for file_path, metadata in parsed.items():
        graph.add_node(file_path)

    for file_path, metadata in parsed.items():
        imports = metadata.get("imports", [])
        for target in imports:
            target_file = module_index.get(target)
            if target_file and target_file != file_path:
                graph.add_edge(file_path, target_file, type="import")

    class_definitions = {}
    for file_path, metadata in parsed.items():
        for module_name in _module_name_from_path(file_path).split("."):
            pass
        class_definitions[file_path] = metadata.get("classes", [])

    for file_path, metadata in parsed.items():
        for base in metadata.get("classes", []):
            for candidate_path, classes in class_definitions.items():
                if candidate_path != file_path and base in classes:
                    graph.add_edge(file_path, candidate_path, type="inherits")
                    break

    return graph
