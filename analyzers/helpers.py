from __future__ import annotations

from pathlib import Path

SOURCE_ROOT_MARKERS = {"src", "lib"}


def module_name_from_relpath(rel_path: Path) -> str:
    parts = [part for part in rel_path.parts if part not in {"."}]
    if not parts:
        return rel_path.stem

    first = parts[0]
    if first in SOURCE_ROOT_MARKERS and len(parts) > 1:
        return parts[1]

    if len(parts) == 1:
        return Path(parts[0]).stem

    return first
