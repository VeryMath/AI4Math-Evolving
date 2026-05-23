# Installation

## Requirements

- Node.js 20
- Python 3.10+
- opencode CLI configured locally
- OpenEvolve installed and importable in the runtime used by opencode
- A provider API key exposed through environment variables

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

By default the backend listens on `127.0.0.1:8001` and Vite listens on `127.0.0.1:5173`.
