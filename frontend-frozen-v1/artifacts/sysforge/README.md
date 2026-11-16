# SYSFORGE

SYSFORGE is an interactive System Programming Laboratory. It is designed to
make the transformation visible: educational assembly source moves through
lexical analysis, syntax analysis, assembly tables, intermediate code, object
code, loading, memory, AI explanation, and execution.

## Install

From the repository root:

```bash
pnpm install
```

## Run

Run the app through the managed Replit workflow, or from this package with the
required environment values:

```bash
PORT=5173 BASE_PATH=/ pnpm --filter @workspace/sysforge run dev
```

## Project structure

- `src/App.tsx` — routing and shared application state
- `src/components/sysforge-components.tsx` — shell, editor, pipeline, stage
  views, guided controls, and execution surface
- `src/lib/sysforge-data.ts` — isolated canonical demo source and navigation
  metadata
- `src/services/compiler-api.ts` — typed compiler API boundary
- `src/index.css` — graphite/electric visual system and responsive styles
- `public/` — static browser assets

## Connecting the FastAPI backend

Set `VITE_API_BASE_URL` to the backend base URL, then replace the unavailable
methods in `src/services/compiler-api.ts` with calls to the backend routes.
The frontend intentionally does not recreate assembler algorithms or infer
results. Until the service is connected, analysis-derived views show an
explicit unavailable state.

The planned service surface includes:

- `/api/analyze`
- `/api/lex`
- `/api/parse`
- `/api/macro`
- `/api/assemble/pass1`
- `/api/assemble/pass2`
- `/api/link`
- `/api/load`
- `/api/memory`
- `/api/execute`
- `/api/ai/explain`
- `/api/ai/optimize`

## Environment variables

Copy `.env.example` to `.env` when running the frontend outside the managed
workflow:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

The frontend does not require a compiler API to render the laboratory shell.