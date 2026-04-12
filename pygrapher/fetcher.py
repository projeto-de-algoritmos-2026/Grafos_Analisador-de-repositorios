import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests

GITHUB_REPO_REGEX = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?(?:/.*)?$")


def _get_default_branch(owner: str, repo: str) -> str:
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(api_url, timeout=15)
    response.raise_for_status()
    data = response.json()
    return data.get("default_branch", "main")


def _download_zip(url: str, dest: Path) -> None:
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with dest.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                handle.write(chunk)


def _cleanup_old_temporary_repos(prefix: str = "pygrapher_") -> None:
    temp_root = Path(tempfile.gettempdir())
    for candidate in temp_root.iterdir():
        if candidate.is_dir() and candidate.name.startswith(prefix):
            try:
                shutil.rmtree(candidate)
            except OSError:
                continue


def cleanup_repository(temp_dir: Path) -> None:
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir)


def fetch_repository(
    source: str,
    dest_dir: Optional[Path] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, Optional[Path]]:
    """Fetch a GitHub repository zip or return a local directory path."""
    if status_callback:
        status_callback("[1/6] Baixando repositório...")

    if dest_dir is None:
        _cleanup_old_temporary_repos()
        dest_dir = Path(tempfile.mkdtemp(prefix="pygrapher_"))
    else:
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source)
    if source_path.exists():
        if not source_path.is_dir():
            raise ValueError(f"Local path is not a directory: {source}")
        return source_path.resolve(), None

    match = GITHUB_REPO_REGEX.search(source)
    if not match:
        raise ValueError(f"URL não é um repositório GitHub válido: {source}")

    owner = match.group("owner")
    repo = match.group("repo")
    default_branch = _get_default_branch(owner, repo)
    archive_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"
    zip_path = dest_dir / f"{repo}.zip"
    _download_zip(archive_url, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(dest_dir)

    extracted_dirs = [p for p in dest_dir.iterdir() if p.is_dir()]
    if not extracted_dirs:
        raise RuntimeError("Falha ao extrair o repositório GitHub.")

    return extracted_dirs[0].resolve(), dest_dir