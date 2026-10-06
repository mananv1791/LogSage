from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    incident_type: str = Field(default="general", index=True)
    service: Optional[str] = Field(default=None, index=True)
    severity: str = Field(default="unknown", index=True)
    status: str = Field(default="processing", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

    log_files: list["LogFile"] = Relationship(back_populates="incident")
    log_lines: list["LogLine"] = Relationship(back_populates="incident")
    analyses: list["Analysis"] = Relationship(back_populates="incident")


class LogFile(SQLModel, table=True):
    __tablename__ = "log_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incidents.id", index=True)
    filename: str
    raw_text: str
    uploaded_at: datetime = Field(default_factory=utc_now, index=True)

    incident: Incident = Relationship(back_populates="log_files")


class LogLine(SQLModel, table=True):
    __tablename__ = "log_lines"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incidents.id", index=True)
    line_number: int = Field(index=True)
    timestamp: Optional[datetime] = Field(default=None, index=True)
    level: Optional[str] = Field(default=None, index=True)
    service: Optional[str] = Field(default=None, index=True)
    message: str
    raw: str
    fingerprint: str = Field(index=True)

    incident: Incident = Relationship(back_populates="log_lines")


class Analysis(SQLModel, table=True):
    __tablename__ = "analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incidents.id", index=True)
    summary: str
    root_cause: str
    suggested_fix: str
    model_used: str
    severity: str = Field(default="unknown", index=True)
    suspicious_lines_json: str = Field(default="[]")
    commands_json: str = Field(default="[]")
    handoff_report: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now, index=True)

    incident: Incident = Relationship(back_populates="analyses")


class Runbook(SQLModel, table=True):
    __tablename__ = "runbooks"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    service: str = Field(index=True)
    symptoms: str
    fix_steps: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
