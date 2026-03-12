from __future__ import annotations

from collections import Counter

from reposcope.models import RepositoryMap


def generate_markdown_summary(repo_map: RepositoryMap) -> str:
    module_langs = Counter(module.language for module in repo_map.module_map)
    lines: list[str] = []

    lines.append(f"# RepoScope Summary: {repo_map.repository_name}")
    lines.append("")
    lines.append("## Snapshot")
    lines.append(f"- Generated: `{repo_map.generated_at}`")
    lines.append(f"- Repository: `{repo_map.repository_path}`")
    lines.append(
        f"- Files scanned: `{repo_map.stats.get('files_scanned', 0)}`"
    )
    lines.append(
        f"- Languages: `{', '.join(repo_map.detected_languages) if repo_map.detected_languages else 'none'}`"
    )
    lines.append(
        f"- Modules: `{len(repo_map.module_map)}` ({', '.join(f'{lang}:{count}' for lang, count in sorted(module_langs.items())) or 'none'})"
    )
    lines.append("")

    lines.append("## Entrypoints")
    if repo_map.entrypoints:
        for entrypoint in repo_map.entrypoints[:20]:
            framework = f" ({entrypoint.framework})" if entrypoint.framework else ""
            lines.append(f"- `{entrypoint.path}`{framework}: {entrypoint.reason}")
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## Module Map")
    if repo_map.module_map:
        for module in sorted(repo_map.module_map, key=lambda x: (x.language, x.name))[:40]:
            deps = ", ".join(module.internal_dependencies[:8]) or "none"
            exts = ", ".join(module.external_dependencies[:8]) or "none"
            lines.append(
                f"- `{module.name}` ({module.language}) at `{module.path}` | internal deps: {deps} | external deps: {exts}"
            )
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## Dependency Graph")
    if repo_map.dependency_graph:
        for edge in repo_map.dependency_graph[:60]:
            lines.append(f"- `{edge.source}` -> `{edge.target}` ({edge.kind})")
    else:
        lines.append("- No internal dependency edges")
    lines.append("")

    lines.append("## Service Boundaries")
    if repo_map.service_boundaries:
        for boundary in repo_map.service_boundaries[:30]:
            signal = ", ".join(boundary.signals) or "none"
            lines.append(f"- `{boundary.name}` at `{boundary.path}` | signals: {signal}")
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## API Surfaces")
    if repo_map.api_surfaces:
        for surface in repo_map.api_surfaces[:50]:
            lines.append(
                f"- `{surface.name}` ({surface.surface_type}) in `{surface.path}`: {surface.details}"
            )
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## Critical Paths")
    if repo_map.critical_paths:
        for critical in repo_map.critical_paths[:40]:
            lines.append(
                f"- `{critical.path}` (priority {critical.priority}): {critical.reason}"
            )
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## Configs")
    if repo_map.configs:
        for config in repo_map.configs[:40]:
            lines.append(f"- `{config}`")
    else:
        lines.append("- None detected")
    lines.append("")

    lines.append("## Tests")
    if repo_map.tests:
        for test_path in repo_map.tests[:40]:
            lines.append(f"- `{test_path}`")
    else:
        lines.append("- None detected")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"
