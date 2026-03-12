# Custom Agent Adapter

## Contract

Inputs expected by your agent runtime:

- `scope.json` (structured map)
- `scope.md` or `agent-compact` summary

## Minimal orchestration script

```bash
reposcope analyze "$REPO_ROOT" -o "$REPO_ROOT/.reposcope/latest_scope.json" --summary-output "$REPO_ROOT/.reposcope/latest_scope.md"
reposcope export --format agent-compact --input "$REPO_ROOT/.reposcope/latest_scope.json" -o "$REPO_ROOT/.reposcope/agent-compact.md"
```

## Suggested runtime policy

- require module/dependency impact statement before write operations
- require explicit mention of touched entrypoints and critical paths
- block large refactors unless scope is refreshed in the same run
