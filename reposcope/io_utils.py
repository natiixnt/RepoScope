from __future__ import annotations

import json
from pathlib import Path

from reposcope.models import RepositoryMap


def write_repository_map(repo_map: RepositoryMap, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(repo_map.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_repository_map(input_path: Path) -> RepositoryMap:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return RepositoryMap.from_dict(payload)


def write_markdown(markdown: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
