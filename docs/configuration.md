# Configuration

## Environment

- `LLM_API_KEY`: OpenAI-compatible provider key used by result analysis.
- `LLM_BASE_URL`: OpenAI-compatible base URL, for example `https://chat.ecnu.edu.cn/open/api/v1`.
- `LLM_MODEL_ID`: model ID for result analysis, for example `ecnu-plus`.
- `DEEPSEEK_API_KEY`: backward-compatible provider key used by existing OpenEvolve examples.
- `DEEPSEEK_BASE_URL`: backward-compatible base URL.
- `DEEPSEEK_MODEL`: backward-compatible model ID.
- `EVOLVE_API_TOKEN`: optional write-token for POST and DELETE API calls.
- `EVOLVE_BRIDGE_HOST`: backend host, default `127.0.0.1`.
- `EVOLVE_BRIDGE_PORT`: backend port, default `8001`.
- `VITE_PORT`: frontend dev server port, default `5173`.
- `OPENEVOLVE_SKILL_REPO`: optional path to the sibling `AI4Math-Evolving-Skill` repository. Defaults to `../AI4Math-Evolving-Skill` relative to this UI repo.
- `AI4MATH_EVOLVE_RUN_MODE`: run mode for UI START requests. Defaults to `direct`; set to `opencode` to use the opencode adapter.

`LLM_*` variables take precedence over `DEEPSEEK_*` variables in backend result analysis and direct OpenEvolve command construction.

## opencode

Use `opencode.example.json` as a public template for provider configuration when running with `AI4MATH_EVOLVE_RUN_MODE=opencode`. Keep real provider credentials in a local private opencode config or environment variables.

Do not commit real API keys.

## Skill Runner

Run start requests are routed through the standalone skill repo runner:

```text
UI backend -> backend/skill_runner.py -> AI4Math-Evolving-Skill interactive_session.py -> OpenEvolve
```

The default path is direct mode:

```text
interactive_session.py -> openevolve-run initial_program.py evaluator.py --config config.yaml --output ...
```

The advanced opencode path remains available:

```text
interactive_session.py --mode opencode -> opencode -> OpenEvolve
```

For local development, keep the repositories as siblings:

```text
AI4Math-Evolving/
AI4Math-Evolving-Skill/
```

If you use a different layout, set `OPENEVOLVE_SKILL_REPO` to the absolute path of `AI4Math-Evolving-Skill`.
