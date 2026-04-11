import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

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


def fetch_repository(source: str, dest_dir: Optional[Path] = None) -> Path:
    """Fetch a GitHub repository zip or return a local directory path."""
    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="pygrapher_"))
    else:
        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(source)
    if source_path.exists():
        if not source_path.is_dir():
            raise ValueError(f"Local path is not a directory: {source}")
        return source_path.resolve()

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

    return extracted_dirs[0].resolve()
