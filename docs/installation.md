# Installation

## Requirements

- Node.js 20
- Python 3.10+
- OpenEvolve installed with `openevolve-run` available on `PATH`
- A provider API key exposed through environment variables
- Optional: opencode CLI configured locally for `AI4MATH_EVOLVE_RUN_MODE=opencode`

## Install Frontend Dependencies

```bash
npm install
```

## Start Locally

```bash
cp .env.example .env
# edit .env with your provider key
./start_all.sh
```

By default the backend listens on `127.0.0.1:8001` and Vite is available at `http://localhost:5173/`.
