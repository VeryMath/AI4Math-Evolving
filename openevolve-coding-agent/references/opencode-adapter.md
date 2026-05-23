# opencode Adapter

The default adapter uses:

```bash
opencode run --format json --agent openevolve-unified-primary --dir <project_dir> <prompt>
```

The agent should execute OpenEvolve rather than only proposing a plan. The prompt must include:

- `project_dir`
- `iterations`
- `checkpoint_interval`
- optional `output_dir`

The UI repo can call `scripts/run_openevolve.py --mode opencode --json` to construct the same command.
