from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from reposcope import __version__
from reposcope.engine import analyze_repository
from reposcope.exporters import repository_map_to_mermaid, repository_map_to_yaml
from reposcope.io_utils import load_repository_map, write_markdown, write_repository_map
from reposcope.models import SCHEMA_VERSION
from reposcope.summary import generate_markdown_summary
from reposcope.validator import validate_json_file


def _default_cache_input() -> Path:
    return Path(".reposcope/latest_scope.json")


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "repository-map.schema.json"


def _write_stdout_or_file(content: str, output: str) -> None:
    if output == "-":
        print(content, end="")
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def cmd_analyze(args: argparse.Namespace) -> int:
    repo_root = Path(args.path).resolve()
    output_json = Path(args.output)
    output_md = Path(args.summary_output)

    repo_map = analyze_repository(repo_root, exclude_patterns=args.exclude)
    summary = generate_markdown_summary(repo_map)

    write_repository_map(repo_map, output_json)
    write_markdown(summary, output_md)

    cache_dir = repo_root / ".reposcope"
    cache_dir.mkdir(parents=True, exist_ok=True)
    write_repository_map(repo_map, cache_dir / "latest_scope.json")
    write_markdown(summary, cache_dir / "latest_scope.md")

    print(f"JSON semantic map: {output_json}")
    print(f"Markdown summary: {output_md}")
    print(f"Cache updated: {cache_dir / 'latest_scope.json'}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    repo_map = load_repository_map(Path(args.input))
    summary = generate_markdown_summary(repo_map)
    _write_stdout_or_file(summary, args.output)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(
            f"Input not found: {input_path}. Run 'reposcope analyze <path>' first or pass --input."
        )

    if args.format == "json":
        content = input_path.read_text(encoding="utf-8")
        _write_stdout_or_file(content, args.output)
        return 0

    repo_map = load_repository_map(input_path)
    if args.format == "markdown":
        content = generate_markdown_summary(repo_map)
    elif args.format == "yaml":
        content = repository_map_to_yaml(repo_map)
    else:
        content = repository_map_to_mermaid(repo_map)

    _write_stdout_or_file(content, args.output)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    schema_path = Path(args.schema)

    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1
    if not schema_path.exists():
        print(f"Schema not found: {schema_path}", file=sys.stderr)
        return 1

    try:
        errors = validate_json_file(input_path, schema_path)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid schema reference: {exc}", file=sys.stderr)
        return 1

    if errors:
        print(f"INVALID: {input_path}")
        for error in errors[:30]:
            print(f"- {error}")
        if len(errors) > 30:
            print(f"- ... and {len(errors) - 30} more")
        return 1

    print(f"VALID: {input_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reposcope",
        description="Analyze repositories and generate semantic maps for coding agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze a repository path")
    analyze.add_argument("path", nargs="?", default=".", help="Repository path")
    analyze.add_argument(
        "-o",
        "--output",
        default="scope.json",
        help="Output JSON semantic map path",
    )
    analyze.add_argument(
        "--summary-output",
        default="scope.md",
        help="Output markdown summary path",
    )
    analyze.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob path pattern to exclude from analysis (repeatable)",
    )
    analyze.set_defaults(func=cmd_analyze)

    summary = subparsers.add_parser("summary", help="Generate markdown summary from scope json")
    summary.add_argument("input", help="Path to semantic map JSON")
    summary.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path (default stdout)",
    )
    summary.set_defaults(func=cmd_summary)

    export = subparsers.add_parser(
        "export",
        help="Export cached analysis as JSON or markdown",
    )
    export.add_argument(
        "--format",
        choices=["json", "markdown", "md", "yaml", "yml", "mermaid", "mmd"],
        default="json",
        help="Export format",
    )
    export.add_argument(
        "--input",
        default=str(_default_cache_input()),
        help="Input scope.json (default ./.reposcope/latest_scope.json)",
    )
    export.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output path (default stdout)",
    )
    export.set_defaults(func=cmd_export)

    validate = subparsers.add_parser(
        "validate",
        help="Validate semantic map JSON against schema",
    )
    validate.add_argument("input", help="Path to semantic map JSON")
    validate.add_argument(
        "--schema",
        default=str(_default_schema_path()),
        help="Path to JSON schema (default bundled repository-map schema)",
    )
    validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    if raw_args in (["--version"], ["-V"]):
        print(f"reposcope {__version__} (schema {SCHEMA_VERSION})")
        return 0

    parser = build_parser()
    args = parser.parse_args(raw_args)
    if args.command == "export":
        if args.format == "md":
            args.format = "markdown"
        elif args.format == "yml":
            args.format = "yaml"
        elif args.format == "mmd":
            args.format = "mermaid"
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
