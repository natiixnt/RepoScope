# Codex Adapter

## Bootstrap command

```bash
reposcope analyze . -o .reposcope/latest_scope.json --summary-output .reposcope/latest_scope.md
reposcope export --format agent-compact --input .reposcope/latest_scope.json -o .reposcope/agent-compact.md
```

## Recommended prompt prelude

```text
Use RepoScope context as the source of truth for architecture.
Before editing code:
1) identify touched modules from module_map
2) list direct + transitive dependencies
3) check entrypoint_reachability for blast radius
4) avoid edits in critical_paths unless required
```

## Typical loop

1. Attach `.reposcope/agent-compact.md` and `.reposcope/latest_scope.json`.
2. Ask for plan constrained by dependencies and entrypoints.
3. Execute edits.
4. Re-run `reposcope analyze` and verify no unintended graph regressions.
