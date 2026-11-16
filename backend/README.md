# SysForge Backend

**Intelligent Integrated System Programming Toolchain — Python / FastAPI service**

This directory contains the deterministic SysForge engine and its FastAPI HTTP
wrapper.  It is completely independent of the Node.js / pnpm monorepo in the
parent directory.

---

## Requirements

| Dependency | Version |
|------------|---------|
| Python     | ≥ 3.11  |
| pip        | ≥ 23    |

Python 3.13 is the version used during development.

---

## Quick start

```bash
# 1 — enter the backend directory
cd backend

# 2 — create and activate a virtual environment
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3 — install runtime + dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 4 — copy the example env file and adjust if needed
cp .env.example .env

# 5 — start the development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is now reachable at **http://127.0.0.1:8000**.

Alternatively use the convenience entry point:

```bash
python run.py
```

---

## Verify the server is running

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "sysforge-backend",
  "version": "1.0.0"
}
```

A bare health probe (for infrastructure / load balancers) is also available:

```bash
curl http://127.0.0.1:8000/health
```

---

## Run the test suite

```bash
# from the backend/ directory, with the virtualenv active
pytest
```

Pytest is configured in `pyproject.toml`:

- test root: `tests/`
- output: verbose, short tracebacks
- async mode: `auto` (pytest-asyncio)

Run only unit tests:

```bash
pytest tests/unit/
```

Run only integration tests:

```bash
pytest tests/integration/
```

Run with coverage (requires `pytest-cov`):

```bash
pip install pytest-cov
pytest --cov=app --cov=engine --cov-report=term-missing
```

---

## Environment variables

Copy `.env.example` to `.env` and edit as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | `development` \| `production` \| `test` |
| `HOST` | `127.0.0.1` | Bind address for uvicorn |
| `PORT` | `8000` | TCP port |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `LOG_LEVEL` | `info` | `debug` \| `info` \| `warning` \| `error` |
| `VM_MAX_INSTRUCTIONS` | `100000` | Maximum instructions per VM run |
| `VM_MAX_MEMORY_WORDS` | `65536` | Maximum VM memory words |
| `VM_MAX_OUTPUT_LINES` | `1000` | Maximum PRINT output lines |
| `VM_EXECUTION_TIMEOUT_SECONDS` | `10` | Wall-clock VM timeout |
| `OPENAI_API_KEY` | _(unset)_ | Required only for the AI phase |

> **Never commit `.env`.**  It is listed in `.gitignore`.

---

## API reference

Interactive docs are served by FastAPI at runtime:

- **Swagger UI:** http://127.0.0.1:8000/api/v1/docs
- **ReDoc:**      http://127.0.0.1:8000/api/v1/redoc
- **OpenAPI JSON:** http://127.0.0.1:8000/api/v1/openapi.json

### Implemented endpoints (Phase 2)

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET`  | `/health` | ✅ Live | Infrastructure health probe |
| `GET`  | `/api/v1/health` | ✅ Live | Versioned health check |
| `POST` | `/api/v1/analyze` | ✅ Live (stub) | Full pipeline — all stages NOT_IMPLEMENTED |
| `POST` | `/api/v1/lex` | ⏳ NOT_IMPLEMENTED | Lexical analysis only |
| `POST` | `/api/v1/parse` | ⏳ NOT_IMPLEMENTED | Syntax analysis only |
| `POST` | `/api/v1/macro/process` | ⏳ NOT_IMPLEMENTED | Macro processor only |
| `POST` | `/api/v1/assemble/pass1` | ⏳ NOT_IMPLEMENTED | Assembler Pass-I |
| `POST` | `/api/v1/assemble/pass2` | ⏳ NOT_IMPLEMENTED | Assembler Pass-II |
| `POST` | `/api/v1/link` | ⏳ NOT_IMPLEMENTED | Linker |
| `POST` | `/api/v1/load` | ⏳ NOT_IMPLEMENTED | Loader |
| `POST` | `/api/v1/execute` | ⏳ NOT_IMPLEMENTED | VM execution |
| `GET`  | `/api/v1/session/{id}/{stage}` | ✅ Live | Retrieve cached stage result |

### Request / response shape

**POST `/api/v1/analyze`**

```json
{
  "source_code": "START 100\nMOVER AREG ='5'\nEND",
  "stages": null,
  "options": {
    "run_macro_processor": true,
    "load_address": 0
  }
}
```

Response (Phase 2 — all stages NOT_IMPLEMENTED):

```json
{
  "session_id": "abc123def456",
  "source_code": "START 100\nMOVER AREG ='5'\nEND",
  "completed_stages": [],
  "stage_statuses": [
    { "stage": "lexical", "status": "NOT_IMPLEMENTED", "error_count": 0, "warning_count": 0 },
    ...
  ],
  "results": {}
}
```

**Error envelope** (all 4xx / 5xx responses):

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "source_code must not be empty.",
    "severity": "ERROR",
    "stage": null,
    "line": null,
    "column": null,
    "details": null
  }
}
```

---

## Directory structure

```
backend/
├── app/                        # FastAPI application layer
│   ├── main.py                 # App factory, CORS, exception handlers
│   ├── core/
│   │   ├── config.py           # Settings (pydantic-settings, env vars)
│   │   └── errors.py           # Error codes, ErrorResponse, exception hierarchy
│   ├── api/
│   │   └── routes/
│   │       ├── health.py       # GET /health, GET /api/v1/health
│   │       └── analysis.py     # POST /analyze and all stage endpoints
│   ├── models/
│   │   ├── tokens.py           # Token, SourceSpan, LexerResult
│   │   ├── syntax.py           # ParsedStatement, SyntaxResult
│   │   ├── assembler.py        # SYMTAB, LITTAB, POOLTAB, IR, Pass1/2 results
│   │   ├── linking.py          # LinkerResult, LoaderResult, MemoryCell
│   │   ├── execution.py        # VMState, ExecutionStep, ExecutionResult
│   │   ├── ai.py               # AI explain/optimize request+response
│   │   ├── requests.py         # AnalysisRequest, StageRequest, VMRunRequest
│   │   ├── responses.py        # AnalysisResponse, HealthResponse, stage responses
│   │   └── sessions.py         # AnalysisSession, StageStatusEntry
│   └── services/
│       └── analysis_service.py # Pipeline orchestrator, session store
│
├── engine/                     # Deterministic SysForge compiler engine
│   ├── common/
│   │   ├── enums.py            # All language keywords, opcodes, stage enums
│   │   └── errors.py           # EngineDiagnostic, DiagnosticBag
│   ├── interfaces.py           # Protocol definitions for all engine components
│   ├── lexer/                  # Phase 3 — Lexer implementation (empty)
│   ├── parser/                 # Phase 3 — Parser implementation (empty)
│   ├── macro/                  # Future — Macro processor (empty)
│   ├── assembler/
│   │   ├── pass1/              # Phase 4 — Pass-I (empty)
│   │   └── pass2/              # Phase 4 — Pass-II (empty)
│   ├── linker/                 # Future — Linker (empty)
│   ├── loader/                 # Future — Loader (empty)
│   └── vm/                     # Future — Educational VM (empty)
│
├── tests/
│   ├── conftest.py             # Shared fixtures (app, client, canonical source)
│   ├── unit/
│   │   ├── test_config.py      # Settings tests
│   │   ├── test_enums.py       # Language keyword table tests
│   │   ├── test_errors.py      # Error model + exception hierarchy tests
│   │   ├── test_models.py      # Pydantic model validation tests
│   │   └── test_engine_errors.py # DiagnosticBag / EngineDiagnostic tests
│   └── integration/
│       ├── test_health.py      # Health endpoint integration tests
│       ├── test_analysis.py    # Analysis pipeline integration tests
│       └── test_error_handling.py # Error envelope consistency tests
│
├── run.py                      # Development entry point (uvicorn)
├── pyproject.toml              # Project metadata, pytest config
├── requirements.txt            # Runtime dependencies (pinned)
├── requirements-dev.txt        # Dev/test dependencies (pinned)
├── .env.example                # Environment variable template
├── .env                        # Local secrets — git-ignored
└── README.md                   # This file
```

---

## Architecture

```
React / Vite frontend
        │
        │  POST /api/v1/analyze
        │  { source_code, stages?, options? }
        ▼
compiler-api.ts  (frozen frontend boundary)
        │
        ▼
FastAPI  (this backend)
        │
        ▼
AnalysisService
        │  orchestrates stages in order
        ▼
SysForge Deterministic Engine
        ├── Lexer            (Phase 3)
        ├── Parser           (Phase 3)
        ├── MacroProcessor   (future)
        ├── AssemblerPass1   (Phase 4)
        ├── AssemblerPass2   (Phase 4)
        ├── Linker           (future)
        └── Loader           (future)
                │
                ▼
        Educational Virtual Machine  (future)
                │
                ▼
        ExecutionResult  →  frontend /execution view

        AI is a separate explanation layer:
        Engine results  →  AI service  →  explanations / suggestions
        AI never produces compiler output.
```

### Key design rules

1. **Deterministic engine is the source of truth.** AI may only explain or
   suggest based on engine results. It never assembles, links, or executes.

2. **No fake data.** A stage returns `NOT_IMPLEMENTED` until the real
   algorithm is built. Hard-coded output tables are forbidden.

3. **Frontend is frozen.** The only integration point is
   `artifacts/sysforge/src/services/compiler-api.ts`. Backend API shapes
   must match the TypeScript types already declared there.

4. **No database required.** The engine operates in memory. Sessions are
   stored in a module-level dict (max 500, LRU eviction).

5. **The Express server (`artifacts/api-server/`) is separate.** It serves
   only a health check for the Replit workflow. Do not merge it with this
   FastAPI backend.

---

## Why the Express server remains separate

The pnpm workspace includes `artifacts/api-server/` — a minimal Express 5
skeleton with a single `GET /api/healthz` route.  It exists because the
Replit deployment workflow requires a Node.js server entry point.

The SysForge compiler engine is Python-only.  Merging it into Node.js would
require either a Python subprocess call (security risk) or a full rewrite
in TypeScript (unnecessary complexity).  The cleanest boundary is:

- **Node.js (Express):** Replit workflow integration, health probe only
- **Python (FastAPI, this service):** all SysForge compiler logic

In production both servers can run in parallel on different ports, or the
Express server can proxy `/api/v1/*` calls to the FastAPI backend.

---

## Implementation roadmap

| Phase | Milestone | Status |
|-------|-----------|--------|
| 2 | Backend foundation, contracts, tests | ✅ Complete |
| 3 | Lexer + Parser | ⏳ Next |
| 4 | Macro Processor + Pass-I (SYMTAB, LITTAB, POOLTAB, IR) | Planned |
| 5 | Pass-II + Linker + Loader | Planned |
| 6 | Educational Virtual Machine | Planned |
| 7 | Final Result view + AI integration | Planned |
| 8 | Security hardening + full test coverage | Planned |

---

## Security notes (for future phases)

The following mitigations are planned but not yet enforced:

- **VM instruction limit:** `VM_MAX_INSTRUCTIONS` (env var, enforced in VM phase)
- **VM timeout:** `VM_EXECUTION_TIMEOUT_SECONDS` (wall-clock, enforced in VM phase)
- **Input size limits:** `source_code` capped at 64 000 chars / 500 lines (enforced now via Pydantic)
- **AI prompt injection:** source code will be quoted/escaped before LLM calls
- **No subprocess execution:** the engine is pure Python; no shell commands
- **No filesystem access:** engine operates entirely in memory

---

*SysForge — Don't just show the final output. Show the transformation that produced it.*
