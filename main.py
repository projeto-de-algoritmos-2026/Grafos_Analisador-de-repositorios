import argparse
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pygrapher.fetcher import cleanup_repository, fetch_repository
from pygrapher.graph import build_graph
from pygrapher.parser import parse_repository
from pygrapher.scc import find_import_sccs, kosaraju_scc, build_import_subgraph
from pygrapher.topological_sort import find_topological_order
from pygrapher.visualizer import draw_graph

StatusCallback = Optional[Callable[[str], None]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera um grafo de dependências Python a partir de um repositório local ou GitHub."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="URL do repositório GitHub")
    group.add_argument("--local", help="Caminho para pasta local do projeto")
    parser.add_argument("--output", default="dependency_graph.html", help="Caminho do arquivo HTML de saída")
    parser.add_argument(
        "--mode",
        choices=["imports", "packages", "package", "class-imports", "class_imports", "classes", "full"],
        default="imports",
        help="Modo de visualização do grafo",
    )
    args = parser.parse_args()

    source = args.repo or args.local
    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("[1/6] Baixando repositório...", total=None)

        def status_callback(message: str) -> None:
            progress.update(task_id, description=message)

        try:
            root_dir, temp_dir = fetch_repository(source, status_callback=status_callback)
        except Exception as exc:
            console.print(f"[red]Erro ao obter o repositório:[/red] {exc}")
            return 1

        try:
            parsed = parse_repository(root_dir, status_callback=status_callback)
            if not parsed:
                console.print("[yellow]Nenhum arquivo Python encontrado no diretório.[/yellow]")
                return 1

            graph = build_graph(parsed, status_callback=status_callback)
            sccs = find_import_sccs(graph, status_callback=status_callback)
            import_graph = build_import_subgraph(graph)
            all_sccs = kosaraju_scc(import_graph)
            all_nodes = sorted(graph.nodes())
            node_num = {node: i + 1 for i, node in enumerate(all_nodes)}
            topo_order = find_topological_order(import_graph, all_sccs, node_num, status_callback=status_callback)
            draw_graph(
                graph,
                Path(args.output),
                mode=args.mode,
                sccs=all_sccs,
                topo_order=topo_order,
                status_callback=status_callback,
            )
        finally:
            if temp_dir is not None:
                cleanup_repository(temp_dir)

    total_nodes = graph.number_of_nodes()
    total_edges = graph.number_of_edges()
    import_count = sum(1 for _, _, data in graph.edges(data=True) if data.get("type") == "import")
    inherit_count = sum(1 for _, _, data in graph.edges(data=True) if data.get("type") == "inherits")

    console.print(f"[bold green]Grafo gerado em:[/bold green] {args.output}")
    console.print(f"[bold]Fonte analisada:[/bold] {root_dir}")
    console.print(
        f"[bold blue]Resumo:[/bold blue] {total_nodes} nós, {total_edges} arestas — "
        f"{import_count} imports, {inherit_count} heranças"
    )
    console.print(f"[bold magenta]Ciclos de import detectados:[/bold magenta] {len(sccs)}")

    if sccs:
        all_nodes = sorted(graph.nodes())
        node_num = {node: i + 1 for i, node in enumerate(all_nodes)}
        for index, component in enumerate(sccs, start=1):
            nums = sorted([node_num[n] for n in component])
            num_str = ", ".join(str(n) for n in nums)
            files_str = " -> ".join(Path(n).name for n in component)
            console.print(f"[magenta]Ciclo {index} (nós: {num_str}):[/magenta] {files_str}")

    console.print()
    console.print(f"[bold cyan]Ordenação Topológica (grafo condensado):[/bold cyan]")
    for item in topo_order:
        nums_str = ", ".join(str(n) for n in item["nums"])
        names_str = ", ".join(item["nodes"])
        layer_str = f"camada {item['layer']}"
        console.print(f"  [cyan]{item['order']:>3}.[/cyan] [{layer_str}] nós ({nums_str}) — {names_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())