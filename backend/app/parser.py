from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import re


TIMESTAMP_RE = re.compile(
    r"(?P<ts>"
    r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
    r"|[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"
    r")"
)
LEVEL_RE = re.compile(r"\b(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b", re.IGNORECASE)
SERVICE_RE = re.compile(
    r"(?:service|svc|app|component|logger)=['\"]?(?P<kv>[A-Za-z0-9_.:-]+)['\"]?"
    r"|\[(?P<bracket>[A-Za-z][A-Za-z0-9_.:-]{1,48})\]"
)
NOISE_RE = re.compile(r"\b[0-9a-f]{8,}\b|\b\d+\b|/[A-Za-z0-9_./-]+|0x[0-9a-f]+", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedLine:
    line_number: int
    timestamp: datetime | None
    level: str | None
    service: str | None
    message: str
    raw: str
    fingerprint: str


def parse_logs(raw_text: str) -> tuple[list[ParsedLine], Counter[str]]:
    entries: list[ParsedLine] = []
    current: dict[str, object] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        message = str(current["message"]).strip()
        raw = str(current["raw"]).rstrip()
        entries.append(
            ParsedLine(
                line_number=int(current["line_number"]),
                timestamp=current["timestamp"] if isinstance(current["timestamp"], datetime) else None,
                level=current["level"] if isinstance(current["level"], str) else None,
                service=current["service"] if isinstance(current["service"], str) else None,
                message=message,
                raw=raw,
                fingerprint=fingerprint(message),
            )
        )
        current = None

    for number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue

        timestamp = parse_timestamp(line)
        level = parse_level(line)
        service = parse_service(line)
        starts_entry = timestamp is not None or level is not None or service is not None

        if starts_entry or current is None:
            flush()
            current = {
                "line_number": number,
                "timestamp": timestamp,
                "level": level,
                "service": service,
                "message": clean_message(line),
                "raw": line,
            }
        else:
            current["message"] = f"{current['message']}\n{line.strip()}"
            current["raw"] = f"{current['raw']}\n{line}"

    flush()
    patterns = Counter(entry.fingerprint for entry in entries)
    return entries, patterns


def parse_timestamp(line: str) -> datetime | None:
    match = TIMESTAMP_RE.search(line)
    if not match:
        return None
    value = match.group("ts").replace(",", ".")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass

    for fmt in ("%b %d %H:%M:%S",):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(year=datetime.now(timezone.utc).year, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def parse_level(line: str) -> str | None:
    match = LEVEL_RE.search(line)
    if not match:
        return None
    level = match.group("level").upper()
    if level == "WARNING":
        return "WARN"
    return level


def parse_service(line: str) -> str | None:
    for match in SERVICE_RE.finditer(line):
        candidate = match.group("kv") or match.group("bracket")
        if not candidate:
            continue
        if candidate.upper() in {"INFO", "WARN", "WARNING", "ERROR", "DEBUG", "TRACE", "CRITICAL", "FATAL"}:
            continue
        return candidate
    return None


def clean_message(line: str) -> str:
    line = TIMESTAMP_RE.sub("", line, count=1)
    line = LEVEL_RE.sub("", line, count=1)
    return re.sub(r"\s+", " ", line).strip(" -|")


def fingerprint(message: str) -> str:
    normalized = NOISE_RE.sub("<var>", message.lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()[:240]
