# Cursor Adapter

## Bootstrap command

```bash
reposcope analyze . -o scope.json --summary-output scope.md
reposcope export --format agent-compact --input scope.json -o scope-agent.md
```

## Workspace notes snippet

```text
RepoScope files:
- scope.json (full semantic map)
- scope-agent.md (compact context)
Use these before generating multi-file edits.
Prioritize modules with high criticality and entrypoint reachability.
```

## Typical loop

1. Add `scope-agent.md` to Cursor context.
2. Ask for bounded plan per module.
3. Execute edits and tests.
4. Refresh `scope.json` after refactors.
