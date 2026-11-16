# SYSFORGE

An interactive system programming laboratory that makes educational assembly transformations visible from source through execution.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/sysforge/src/App.tsx` — routed shell and shared analysis session state
- `artifacts/sysforge/src/components/sysforge-components.tsx` — laboratory UI
- `artifacts/sysforge/src/lib/sysforge-data.ts` — canonical demo source and stage metadata
- `artifacts/sysforge/src/services/compiler-api.ts` — typed backend boundary
- `artifacts/sysforge/src/index.css` — SYSFORGE theme tokens and layout styles

## Architecture decisions

- The first frontend build is intentionally backend-honest: compiler-derived values are never fabricated in the UI.
- The canonical assembly demo is isolated from view components so the future API response can replace it cleanly.
- All compiler integration is routed through a typed service boundary in the frontend.

## Product

SYSFORGE provides a source editor, guided laboratory mode, explorer navigation for each toolchain stage, and backend-ready views for tokens, syntax, tables, intermediate code, object code, memory, AI explanations, and virtual-machine execution.

## User preferences

No additional preferences recorded.

## Gotchas

- The web artifact workflow supplies `PORT` and `BASE_PATH`; use the managed workflow rather than starting the app from the workspace root.
- Compiler output views should remain unavailable until a real backend response exists.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
