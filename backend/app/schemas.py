from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    summary: str
    root_cause: str
    suggested_fix: str
    model_used: str
    severity: str
    suspicious_lines: list[dict[str, Any]]
    commands: list[str]
    handoff_report: str
    created_at: datetime


class LogLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_number: int
    timestamp: datetime | None
    level: str | None
    service: str | None
    message: str
    raw: str
    fingerprint: str


class IncidentSummary(BaseModel):
    id: int
    title: str
    incident_type: str
    service: str | None
    severity: str
    status: str
    created_at: datetime
    line_count: int = 0
    has_analysis: bool = False


class IncidentDetail(IncidentSummary):
    raw_preview: str | None = None
    log_lines: list[LogLineRead]
    analysis: AnalysisRead | None


class IncidentUpdate(BaseModel):
    title: str | None = None
    service: str | None = None
    severity: str | None = None
    status: str | None = None


class RunbookCreate(BaseModel):
    title: str
    service: str
    symptoms: str
    fix_steps: str


class RunbookRead(RunbookCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
