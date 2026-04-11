import ast
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set


def _normalize_module_path(path: Path, root_dir: Path) -> str:
    relative = path.relative_to(root_dir)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_test_module(path: Path) -> bool:
    lower_name = path.name.lower()
    if "tests" in path.parts or "test" in path.parts:
        return True
    return lower_name.startswith("test_") or lower_name.endswith("_test.py") or lower_name == "tests.py"


def _extract_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value = _extract_name(node.value)
        if value:
            return f"{value}.{node.attr}"
    return None


def _resolve_import_from(module: Optional[str], level: int, alias: str, current_module: str) -> str:
    if level == 0:
        if module:
            return f"{module}.{alias}" if alias != "*" else module
        return alias

    parts = current_module.split(".") if current_module else []
    base = parts[: max(0, len(parts) - level)]
    if module:
        base.append(module)
    if alias and alias != "*":
        base.append(alias)
    return ".".join(base)


def _parse_imports(node: ast.AST, current_module: str) -> Set[str]:
    imports: Set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name)
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            imports.add(_resolve_import_from(node.module, node.level, alias.name, current_module))
    return imports


def _parse_classes(node: ast.AST) -> Set[str]:
    classes: Set[str] = set()
    if isinstance(node, ast.ClassDef):
        for base in node.bases:
            base_name = _extract_name(base)
            if base_name:
                classes.add(base_name)
    return classes


def parse_repository(
    root_dir: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Dict[str, List[str]]]:
    if status_callback:
        status_callback("[2/4] Analisando arquivos .py...")

    root_dir = Path(root_dir).resolve()
    result: Dict[str, Dict[str, List[str]]] = {}

    for path in sorted(root_dir.rglob("*.py")):
        if path.name == "__init__.py" or _is_test_module(path):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        current_module = _normalize_module_path(path, root_dir)
        tree = ast.parse(text, filename=str(path))

        imports: Set[str] = set()
        classes: Set[str] = set()
        for node in ast.walk(tree):
            imports.update(_parse_imports(node, current_module))
            classes.update(_parse_classes(node))

        relative_path = path.relative_to(root_dir).as_posix()
        result[relative_path] = {
            "imports": sorted(imports),
            "classes": sorted(classes),
        }

    return result