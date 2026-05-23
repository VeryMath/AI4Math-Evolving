# Security

- Never commit `.env` or `opencode.json` with real API keys.
- Keep the backend bound to `127.0.0.1` unless you intentionally expose it.
- Set `EVOLVE_API_TOKEN` before using public tunnels.
- Treat uploaded evolve objects as executable code. Review them before running.
- Public tunnels expose the UI and API to the internet; use them only for trusted demos.
- Keep migration archives, runtime logs, PID files, and historical run outputs out of public releases.
