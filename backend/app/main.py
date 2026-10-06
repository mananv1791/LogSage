from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import json
import os
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_
from sqlmodel import Session, delete, select

from .analyzer import build_analysis
from .database import engine, get_session, init_db
from .models import Analysis, Incident, LogFile, LogLine, Runbook
from .parser import parse_logs
from .schemas import (
    AnalysisRead,
    IncidentDetail,
    IncidentSummary,
    IncidentUpdate,
    LogLineRead,
    RunbookCreate,
    RunbookRead,
)


ALLOWED_UPLOAD_EXTENSIONS = {".log", ".txt", ""}
ALLOWED_STATUSES = {"processing", "unresolved", "resolved", "failed"}
ALLOWED_SEVERITIES = {"unknown", "informational", "low", "medium", "high", "critical"}

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="LogSage API",
    description="AI-assisted log triage and incident tracking API.",
    version="0.1.0",
    lifespan=lifespan,
)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/incidents", response_model=IncidentSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_incident(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    incident_type: str = Form("general"),
    service: str | None = Form(None),
    logs_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
) -> IncidentSummary:
    filename = "pasted-logs.txt"
    raw_text = (logs_text or "").strip()

    if file and file.filename:
        extension = Path(file.filename).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only .log or .txt uploads are supported.")
        raw_bytes = await file.read()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        filename = file.filename

    if not raw_text:
        raise HTTPException(status_code=400, detail="Provide a log file or pasted logs.")

    incident = Incident(
        title=title.strip(),
        incident_type=incident_type.strip() or "general",
        service=service.strip() if service else None,
        status="processing",
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)

    session.add(LogFile(incident_id=incident.id, filename=filename, raw_text=raw_text))
    session.commit()

    if os.getenv("VERCEL") or os.getenv("LOGSAGE_SYNC_ANALYSIS") == "1":
        process_incident(incident.id)
        session.expire_all()
        incident = session.get(Incident, incident.id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found after processing.")
    else:
        background_tasks.add_task(process_incident, incident.id)
    return incident_summary(session, incident)


@app.get("/api/incidents", response_model=list[IncidentSummary])
def list_incidents(
    service: str | None = None,
    severity: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: Session = Depends(get_session),
) -> list[IncidentSummary]:
    statement = select(Incident)
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.join(LogLine, isouter=True).where(
            or_(
                Incident.title.ilike(pattern),
                Incident.incident_type.ilike(pattern),
                LogLine.message.ilike(pattern),
            )
        )
    if service:
        statement = statement.where(Incident.service.ilike(f"%{service}%"))
    if severity:
        statement = statement.where(Incident.severity == severity)
    if status_filter:
        statement = statement.where(Incident.status == status_filter)
    if date_from:
        statement = statement.where(Incident.created_at >= date_from)
    if date_to:
        statement = statement.where(Incident.created_at <= date_to)

    statement = statement.distinct().order_by(Incident.created_at.desc())
    incidents = session.exec(statement).all()
    return [incident_summary(session, incident) for incident in incidents]


@app.get("/api/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, session: Session = Depends(get_session)) -> IncidentDetail:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    lines = session.exec(
        select(LogLine).where(LogLine.incident_id == incident_id).order_by(LogLine.line_number).limit(300)
    ).all()
    analysis = latest_analysis(session, incident_id)
    log_file = session.exec(select(LogFile).where(LogFile.incident_id == incident_id)).first()
    summary = incident_summary(session, incident)
    return IncidentDetail(
        **summary.model_dump(),
        raw_preview=log_file.raw_text[:4000] if log_file else None,
        log_lines=[LogLineRead.model_validate(line) for line in lines],
        analysis=analysis_read(analysis) if analysis else None,
    )


@app.patch("/api/incidents/{incident_id}", response_model=IncidentSummary)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    session: Session = Depends(get_session),
) -> IncidentSummary:
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid incident status.")
    if "severity" in updates and updates["severity"] not in ALLOWED_SEVERITIES:
        raise HTTPException(status_code=400, detail="Invalid severity.")

    for key, value in updates.items():
        setattr(incident, key, value)
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident_summary(session, incident)


@app.get("/api/runbooks", response_model=list[RunbookRead])
def list_runbooks(
    service: str | None = None,
    keyword: str | None = None,
    session: Session = Depends(get_session),
) -> list[RunbookRead]:
    statement = select(Runbook).order_by(Runbook.created_at.desc())
    if service:
        statement = statement.where(Runbook.service.ilike(f"%{service}%"))
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                Runbook.title.ilike(pattern),
                Runbook.symptoms.ilike(pattern),
                Runbook.fix_steps.ilike(pattern),
            )
        )
    return [RunbookRead.model_validate(runbook) for runbook in session.exec(statement).all()]


@app.post("/api/runbooks", response_model=RunbookRead, status_code=status.HTTP_201_CREATED)
def create_runbook(payload: RunbookCreate, session: Session = Depends(get_session)) -> RunbookRead:
    runbook = Runbook(**payload.model_dump())
    session.add(runbook)
    session.commit()
    session.refresh(runbook)
    return RunbookRead.model_validate(runbook)


@app.delete("/api/runbooks/{runbook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_runbook(runbook_id: int, session: Session = Depends(get_session)) -> None:
    runbook = session.get(Runbook, runbook_id)
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found.")
    session.delete(runbook)
    session.commit()


def process_incident(incident_id: int) -> None:
    with Session(engine) as session:
        incident = session.get(Incident, incident_id)
        if not incident:
            return
        try:
            log_files = session.exec(select(LogFile).where(LogFile.incident_id == incident_id)).all()
            raw_text = "\n".join(log_file.raw_text for log_file in log_files)
            parsed_lines, patterns = parse_logs(raw_text)

            session.exec(delete(LogLine).where(LogLine.incident_id == incident_id))
            session.exec(delete(Analysis).where(Analysis.incident_id == incident_id))

            for parsed in parsed_lines:
                session.add(
                    LogLine(
                        incident_id=incident_id,
                        line_number=parsed.line_number,
                        timestamp=parsed.timestamp,
                        level=parsed.level,
                        service=parsed.service,
                        message=parsed.message,
                        raw=parsed.raw,
                        fingerprint=parsed.fingerprint,
                    )
                )

            runbooks = session.exec(select(Runbook)).all()
            payload = build_analysis(
                title=incident.title,
                incident_type=incident.incident_type,
                requested_service=incident.service,
                lines=parsed_lines,
                patterns=patterns,
                runbooks=runbooks,
            )

            incident.service = payload.get("service") or incident.service
            incident.severity = payload.get("severity") or "unknown"
            incident.status = "unresolved"
            session.add(incident)
            session.add(
                Analysis(
                    incident_id=incident_id,
                    summary=payload["summary"],
                    root_cause=payload["root_cause"],
                    suggested_fix=payload["suggested_fix"],
                    model_used=payload["model_used"],
                    severity=payload["severity"],
                    suspicious_lines_json=json.dumps(payload.get("suspicious_lines", [])),
                    commands_json=json.dumps(payload.get("commands", [])),
                    handoff_report=payload.get("handoff_report", ""),
                )
            )
            session.commit()
        except Exception as exc:
            incident.status = "failed"
            incident.severity = "unknown"
            session.add(incident)
            session.add(
                Analysis(
                    incident_id=incident_id,
                    summary="Log analysis failed.",
                    root_cause="Processing error",
                    suggested_fix=f"Check API logs for the processing exception: {exc}",
                    model_used="system",
                    severity="unknown",
                    handoff_report=f"LogSage failed while processing incident {incident_id}: {exc}",
                )
            )
            session.commit()


def incident_summary(session: Session, incident: Incident) -> IncidentSummary:
    line_count = session.exec(
        select(func.count()).select_from(LogLine).where(LogLine.incident_id == incident.id)
    ).one()
    has_analysis = latest_analysis(session, incident.id) is not None
    return IncidentSummary(
        id=incident.id,
        title=incident.title,
        incident_type=incident.incident_type,
        service=incident.service,
        severity=incident.severity,
        status=incident.status,
        created_at=incident.created_at,
        line_count=line_count,
        has_analysis=has_analysis,
    )


def latest_analysis(session: Session, incident_id: int) -> Analysis | None:
    return session.exec(
        select(Analysis).where(Analysis.incident_id == incident_id).order_by(Analysis.created_at.desc())
    ).first()


def analysis_read(analysis: Analysis) -> AnalysisRead:
    return AnalysisRead(
        id=analysis.id,
        incident_id=analysis.incident_id,
        summary=analysis.summary,
        root_cause=analysis.root_cause,
        suggested_fix=analysis.suggested_fix,
        model_used=analysis.model_used,
        severity=analysis.severity,
        suspicious_lines=json.loads(analysis.suspicious_lines_json or "[]"),
        commands=json.loads(analysis.commands_json or "[]"),
        handoff_report=analysis.handoff_report,
        created_at=analysis.created_at,
    )


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.frontend("/", directory=str(FRONTEND_DIST), fallback="index.html")
