# Build LogSage From Scratch

This guide walks through building LogSage as a learning project. The goal is not just to copy files, but to understand how a full-stack SDE-style tool fits together: frontend state, backend APIs, parsing, persistence, background work, AI prompting, tests, Docker, CI, and deployment.

## 1. What You Are Building

LogSage lets a developer upload or paste logs, choose an incident type, and get a structured triage result:

- likely root cause
- affected service
- severity
- suspicious log lines
- commands to inspect next
- suggested fix
- incident handoff report
- searchable incident history
- reusable runbooks

The app has three major parts:

- React frontend: the developer console
- FastAPI backend: upload, parsing, analysis, search, runbooks
- Database: incidents, files, parsed lines, analysis, runbooks

## 2. Project Shape

Start with this structure:

```text
LogSage/
  backend/
    app/
    tests/
  frontend/
    src/
  docs/
  .github/workflows/
  docker-compose.yml
  README.md
```

Keep frontend and backend separate because that mirrors how real engineering teams split ownership.

## 3. Backend Setup

Create a Python virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" sqlmodel "psycopg[binary]" python-multipart httpx openai pytest
```

Create these backend modules:

- `database.py`: database engine and sessions
- `models.py`: SQLModel tables
- `parser.py`: log parsing and pattern detection
- `analyzer.py`: heuristic plus optional LLM analysis
- `schemas.py`: API response/request models
- `main.py`: FastAPI routes

## 4. Database Models

Use these core tables:

- `incidents`: title, service, severity, status, created time
- `log_files`: uploaded filename and raw text
- `log_lines`: parsed timestamp, level, service, message
- `analysis`: summary, root cause, suggested fix, model used
- `runbooks`: reusable symptoms and fixes

The important design choice: store raw logs and parsed lines. Raw logs preserve the source of truth; parsed lines make search and triage fast.

## 5. Log Parser

Build the parser in layers:

1. Detect timestamps with regex.
2. Detect levels like `INFO`, `WARN`, `ERROR`, `CRITICAL`.
3. Detect service names from `service=api` or `[billing]`.
4. Group stack trace continuation lines into the previous log entry.
5. Create a fingerprint by replacing IDs, paths, and numbers with placeholders.

Fingerprinting helps detect repeated patterns like:

```text
job 123 failed for user 456
job 999 failed for user 888
```

Both become the same failure shape.

## 6. Analysis Logic

Start with a deterministic heuristic analyzer before using an LLM. This makes the app useful even without API keys.

Score lines higher when they include:

- `ERROR`, `CRITICAL`, or `FATAL`
- `timeout`, `exception`, `failed`, `denied`, `deadlock`
- stack traces
- repeated fingerprints

Then infer:

- severity from levels and keywords
- root cause from suspicious text
- next commands from service and failure type
- suggested fix from matching runbooks

After that, add optional LLM support. Send the LLM only the high-signal lines and matching runbooks, not the entire log file.

## 7. API Routes

Implement these routes:

```text
POST   /api/incidents
GET    /api/incidents
GET    /api/incidents/{id}
PATCH  /api/incidents/{id}
GET    /api/runbooks
POST   /api/runbooks
DELETE /api/runbooks/{id}
```

For uploads, accept both:

- multipart file uploads
- pasted log text

For filters, support:

- service
- severity
- status
- keyword
- date range

## 8. Background Processing

Locally, use FastAPI `BackgroundTasks` so the upload returns quickly while parsing and analysis continue.

For serverless deployment, prefer synchronous processing unless you add a durable queue. Serverless functions can end quickly, and true large-log processing belongs in a worker or queue-backed system.

## 9. Frontend Setup

Create a Vite React app:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install lucide-react
npm install -D tailwindcss postcss autoprefixer vitest jsdom @testing-library/react @testing-library/jest-dom
```

Build three main UI surfaces:

- New incident form: title, type, service, file, pasted logs
- Incident history: filters, severity counts, status
- Incident detail: diagnosis, suspicious lines, commands, report, parsed lines

Add a Runbooks page where users can save common symptoms and fixes.

## 10. Frontend API Client

Create `src/api.ts` with small functions:

- `listIncidents`
- `getIncident`
- `createIncident`
- `updateIncident`
- `listRunbooks`
- `createRunbook`
- `deleteRunbook`

Use `VITE_API_BASE_URL` in local development. In production on Vercel, use same-origin requests like `/api/incidents`.

## 11. Docker Compose

Use Docker Compose for the real local stack:

- PostgreSQL
- FastAPI backend
- Vite frontend

This demonstrates that you can run services together, configure environment variables, and use a real database.

## 12. Tests

Start with backend tests:

- parser extracts timestamp, level, service
- parser groups stack traces
- fingerprinting collapses variable IDs
- API creates incidents and returns analysis
- filters work

Add frontend tests for the main render path and core controls.

## 13. CI

Create a GitHub Actions workflow:

- install Python dependencies
- run `pytest`
- install frontend dependencies
- run typecheck
- run frontend tests
- build frontend

CI is what turns a portfolio project from “it worked on my machine” into an engineering artifact.

## 14. Vercel Deployment

For this repo, Vercel uses the FastAPI app as the entry point and mounts the built React app.

Important files:

- root `pyproject.toml`: tells Vercel where the FastAPI app lives and how to build the frontend
- root `requirements.txt`: Python dependencies for the serverless function
- `vercel.json`: function settings
- backend `app.frontend(...)`: serves the Vite build at `/`

For a demo deployment, SQLite in `/tmp` is enough to show the workflow. For a real production deployment, add a hosted Postgres URL as `DATABASE_URL` in Vercel environment variables.

## 15. Production Improvements

Once the basics work, improve it like a real SDE project:

- Replace serverless background work with a queue.
- Add authentication.
- Add organization/team ownership.
- Store uploaded files in object storage.
- Add embeddings for semantic runbook matching.
- Add pagination for large incident histories.
- Add log redaction for secrets and personal data.
- Add OpenTelemetry traces for analysis jobs.
- Add Playwright end-to-end tests.

## 16. Suggested Learning Order

Build in this order:

1. Database models
2. Parser
3. Heuristic analyzer
4. Incident create/detail API
5. React upload form
6. Incident history and filters
7. Runbooks
8. Optional LLM integration
9. Docker Compose
10. Tests and CI
11. Vercel deployment

That order keeps the project teachable: each layer has something visible to verify before you move on.
