# LogSage: AI Log Triage & Incident Tracker

LogSage is a practical full-stack incident triage app for developers. Upload or paste logs, let the backend parse error patterns and runbooks, and get a structured diagnosis with suspicious lines, likely root cause, severity, commands to inspect next, and a handoff-ready incident report.

## Tech Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI, SQLModel, PostgreSQL
- AI: OpenAI API or Ollama, with a deterministic heuristic fallback
- DevOps: Docker Compose, GitHub Actions, `.env` config
- Testing: pytest, React Testing Library/Vitest

## Quick Start

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs
- PostgreSQL: localhost:5432

The app works without an AI key by using a local heuristic analyzer. Copy `.env.example` to `.env` when you want hosted LLM analysis via `OPENAI_API_KEY`, or local analysis with Ollama via `OLLAMA_BASE_URL`.

## Local Development

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## API Highlights

- `POST /api/incidents`: upload `.log`/`.txt` files or paste logs; analysis runs in a background task
- `GET /api/incidents`: search/filter by service, severity, date, keyword, and status
- `GET /api/incidents/{id}`: incident detail with parsed lines and analysis
- `PATCH /api/incidents/{id}`: update status or core metadata
- `GET/POST/DELETE /api/runbooks`: manage reusable fixes that are referenced by analysis

## Tests

```bash
cd backend && pytest
cd frontend && npm test -- --run
```

## Deploy To Vercel

This repo is Vercel-ready:

- `pyproject.toml` points Vercel at the FastAPI app in `backend.app.main:app`
- Vercel runs `cd frontend && npm ci && npm run build`
- FastAPI serves the built React app from `frontend/dist`
- `/api/*` routes stay on FastAPI

Deploy with the Vercel dashboard, Vercel CLI, or the Codex Vercel connector. Without `DATABASE_URL`, Vercel uses an ephemeral SQLite database in `/tmp` for demo purposes. For persistent incidents and runbooks, add a hosted PostgreSQL URL as `DATABASE_URL` in Vercel environment variables.

## Build From Scratch

See [docs/build-from-scratch.md](docs/build-from-scratch.md) for a guided learning document that explains how to rebuild the project step by step.

## Resume Summary

Built an AI-powered log triage platform using React, FastAPI, PostgreSQL, and LLM APIs to parse uploaded logs, detect error patterns, classify incident severity, and generate structured debugging reports. Designed relational schemas for incidents, log lines, AI analysis, and runbooks, with background processing for large uploads and searchable incident history. Added automated tests and CI workflows to validate parsing logic, API behavior, and core user flows.
