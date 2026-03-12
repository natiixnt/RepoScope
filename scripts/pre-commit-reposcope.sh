#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

json_out=".reposcope/latest_scope.json"
md_out=".reposcope/latest_scope.md"

if command -v reposcope >/dev/null 2>&1; then
  reposcope analyze . -o "$json_out" --summary-output "$md_out" >/dev/null
else
  python3 -m reposcope analyze . -o "$json_out" --summary-output "$md_out" >/dev/null
fi

echo "RepoScope refreshed: $json_out and $md_out"
