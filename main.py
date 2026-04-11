import argparse
from pathlib import Path

from pygrapher.fetcher import fetch_repository
from pygrapher.graph import build_graph
from pygrapher.parser import parse_repository
from pygrapher.visualizer import draw_graph


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera um grafo de dependências Python a partir de um repositório local ou GitHub."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="URL do repositório GitHub")
    group.add_argument("--local", help="Caminho para pasta local do projeto")
    parser.add_argument("--output", default="dependency_graph.png", help="Caminho do arquivo PNG de saída")
    args = parser.parse_args()

    source = args.repo or args.local
    try:
        root_dir = fetch_repository(source)
    except Exception as exc:
        print(f"Erro ao obter o repositório: {exc}")
        return 1

    parsed = parse_repository(root_dir)
    if not parsed:
        print("Nenhum arquivo Python encontrado no diretório.")
        return 1

    graph = build_graph(parsed)
    draw_graph(graph, Path(args.output))

    print(f"Grafo gerado em: {args.output}")
    print(f"Fonte analisada: {root_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
