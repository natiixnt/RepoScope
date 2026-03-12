from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from analyzers.base import AnalysisContext, AnalyzerOutput
from reposcope.models import DependencyEdge, Entrypoint, ModuleNode

SECTION_RE = re.compile(r"^\s*\[(.+?)\]\s*$")
KEY_VALUE_RE = re.compile(r'^\s*([A-Za-z0-9_\-]+)\s*=\s*(.+)$')
NAME_RE = re.compile(r'^\s*name\s*=\s*"([^"]+)"\s*$')
MEMBERS_RE = re.compile(r'^\s*members\s*=\s*\[(.*?)\]\s*$')
STRING_RE = re.compile(r'"([^"]+)"')


class RustAnalyzer:
    name = "rust"

    def analyze(self, context: AnalysisContext) -> AnalyzerOutput:
        output = AnalyzerOutput()

        rust_files = [file_path for file_path in context.files if file_path.suffix == ".rs"]
        cargo_files = [
            file_path for file_path in context.files if file_path.name == "Cargo.toml"
        ]
        if not rust_files and not cargo_files:
            return output

        output.detected_languages.add("rust")

        crates = self._discover_crates(context.repo_root, cargo_files)
        if not crates:
            return output

        crate_names = {crate.name for crate in crates}

        for crate in crates:
            output.modules.append(
                ModuleNode(
                    name=crate.name,
                    path=str(crate.path),
                    language="rust",
                    files=sorted(crate.files),
                    internal_dependencies=sorted(
                        dep for dep in crate.dependencies if dep in crate_names
                    ),
                    external_dependencies=sorted(
                        dep for dep in crate.dependencies if dep not in crate_names
                    ),
                )
            )

            for dep in sorted(crate.dependencies):
                if dep in crate_names and dep != crate.name:
                    output.dependency_edges.append(
                        DependencyEdge(
                            source=crate.name,
                            target=dep,
                            kind="rust-crate-dep",
                        )
                    )

            if crate.main_entrypoint is not None:
                output.entrypoints.append(
                    Entrypoint(
                        path=crate.main_entrypoint,
                        reason="rust binary entrypoint",
                    )
                )

        return output

    def _discover_crates(
        self,
        repo_root: Path,
        cargo_files: list[Path],
    ) -> list["_RustCrate"]:
        crates_by_path: dict[Path, _RustCrate] = {}

        for cargo_file in cargo_files:
            crate_root = cargo_file.parent
            rel_root = crate_root.relative_to(repo_root)
            name, dependencies = self._parse_cargo_toml(cargo_file)
            if not name:
                name = rel_root.name if rel_root.parts else repo_root.name
            files = self._collect_rust_files(crate_root, repo_root)
            main_entrypoint = self._detect_main_entrypoint(crate_root, repo_root)
            crates_by_path[rel_root] = _RustCrate(
                name=name,
                path=rel_root,
                dependencies=dependencies,
                files=files,
                main_entrypoint=main_entrypoint,
            )

        root_cargo = repo_root / "Cargo.toml"
        if root_cargo.exists():
            workspace_members = self._parse_workspace_members(root_cargo)
            for member in workspace_members:
                for member_path in repo_root.glob(member):
                    cargo = member_path / "Cargo.toml"
                    if not cargo.exists():
                        continue
                    rel_root = member_path.relative_to(repo_root)
                    if rel_root in crates_by_path:
                        continue
                    name, dependencies = self._parse_cargo_toml(cargo)
                    if not name:
                        name = rel_root.name
                    files = self._collect_rust_files(member_path, repo_root)
                    main_entrypoint = self._detect_main_entrypoint(member_path, repo_root)
                    crates_by_path[rel_root] = _RustCrate(
                        name=name,
                        path=rel_root,
                        dependencies=dependencies,
                        files=files,
                        main_entrypoint=main_entrypoint,
                    )

        return sorted(crates_by_path.values(), key=lambda crate: (crate.path, crate.name))

    def _parse_cargo_toml(self, cargo_toml: Path) -> tuple[str | None, set[str]]:
        try:
            content = cargo_toml.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None, set()

        current_section = ""
        package_name: str | None = None
        dependencies: set[str] = set()

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            section_match = SECTION_RE.match(line)
            if section_match:
                current_section = section_match.group(1).strip()
                continue

            if current_section == "package":
                name_match = NAME_RE.match(line)
                if name_match:
                    package_name = name_match.group(1)
                continue

            if not (
                current_section == "dependencies"
                or current_section == "dev-dependencies"
                or current_section == "build-dependencies"
                or current_section.endswith(".dependencies")
            ):
                continue

            kv_match = KEY_VALUE_RE.match(line)
            if not kv_match:
                continue
            dep_name = kv_match.group(1).strip()
            if dep_name:
                dependencies.add(dep_name)

        return package_name, dependencies

    def _parse_workspace_members(self, cargo_toml: Path) -> list[str]:
        try:
            content = cargo_toml.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []

        current_section = ""
        members: list[str] = []

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            section_match = SECTION_RE.match(line)
            if section_match:
                current_section = section_match.group(1).strip()
                continue

            if current_section != "workspace":
                continue

            member_match = MEMBERS_RE.match(line)
            if not member_match:
                continue

            members_blob = member_match.group(1)
            members.extend(STRING_RE.findall(members_blob))

        return members

    def _collect_rust_files(self, crate_root: Path, repo_root: Path) -> list[str]:
        files = []
        for file_path in crate_root.rglob("*.rs"):
            if "target" in file_path.parts:
                continue
            files.append(str(file_path.relative_to(repo_root)))
        return sorted(files)

    def _detect_main_entrypoint(self, crate_root: Path, repo_root: Path) -> str | None:
        main_rs = crate_root / "src" / "main.rs"
        if main_rs.exists():
            return str(main_rs.relative_to(repo_root))

        for candidate in sorted((crate_root / "src" / "bin").glob("*.rs")):
            return str(candidate.relative_to(repo_root))

        return None


class _RustCrate:
    def __init__(
        self,
        *,
        name: str,
        path: Path,
        dependencies: set[str],
        files: list[str],
        main_entrypoint: str | None,
    ) -> None:
        self.name = name
        self.path = path
        self.dependencies = dependencies
        self.files = files
        self.main_entrypoint = main_entrypoint
