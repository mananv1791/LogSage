from __future__ import annotations

from collections import Counter
import json
import os
from typing import Any

import httpx
from openai import OpenAI

from .models import Runbook
from .parser import ParsedLine


ERROR_WORDS = (
    "exception",
    "traceback",
    "failed",
    "failure",
    "timeout",
    "timed out",
    "refused",
    "denied",
    "deadlock",
    "unavailable",
    "out of memory",
    "oom",
    "panic",
    "fatal",
)


def build_analysis(
    *,
    title: str,
    incident_type: str,
    requested_service: str | None,
    lines: list[ParsedLine],
    patterns: Counter[str],
    runbooks: list[Runbook],
) -> dict[str, Any]:
    heuristic = heuristic_analysis(
        title=title,
        incident_type=incident_type,
        requested_service=requested_service,
        lines=lines,
        patterns=patterns,
        runbooks=runbooks,
    )

    llm_payload = maybe_generate_with_llm(
        title=title,
        incident_type=incident_type,
        lines=lines,
        runbooks=runbooks,
        fallback=heuristic,
    )
    return llm_payload or heuristic


def heuristic_analysis(
    *,
    title: str,
    incident_type: str,
    requested_service: str | None,
    lines: list[ParsedLine],
    patterns: Counter[str],
    runbooks: list[Runbook],
) -> dict[str, Any]:
    service = requested_service or most_common_service(lines) or "unknown-service"
    suspicious = top_suspicious_lines(lines, patterns)
    severity = infer_severity(lines, suspicious)
    matched_runbooks = match_runbooks(service, lines, runbooks)
    root_cause = infer_root_cause(suspicious, incident_type)
    suggested_fix = infer_fix(root_cause, matched_runbooks)
    commands = commands_for(service, root_cause)
    summary = (
        f"{severity.upper()} incident in {service}: {root_cause}. "
        f"Parsed {len(lines)} log entries and found {len(suspicious)} high-signal lines."
    )
    handoff = build_handoff_report(
        title=title,
        service=service,
        severity=severity,
        root_cause=root_cause,
        suggested_fix=suggested_fix,
        suspicious=suspicious,
        commands=commands,
        matched_runbooks=matched_runbooks,
    )

    return {
        "summary": summary,
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "severity": severity,
        "service": service,
        "suspicious_lines": suspicious,
        "commands": commands,
        "handoff_report": handoff,
        "model_used": "heuristic-fallback",
    }


def maybe_generate_with_llm(
    *,
    title: str,
    incident_type: str,
    lines: list[ParsedLine],
    runbooks: list[Runbook],
    fallback: dict[str, Any],
) -> dict[str, Any] | None:
    if os.getenv("OPENAI_API_KEY"):
        return generate_with_openai(title, incident_type, lines, runbooks, fallback)
    if os.getenv("OLLAMA_BASE_URL"):
        return generate_with_ollama(title, incident_type, lines, runbooks, fallback)
    return None


def generate_with_openai(
    title: str,
    incident_type: str,
    lines: list[ParsedLine],
    runbooks: list[Runbook],
    fallback: dict[str, Any],
) -> dict[str, Any] | None:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_prompt(title, incident_type, lines, runbooks, fallback)},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        payload = normalize_llm_payload(json.loads(content), fallback)
        payload["model_used"] = model
        return payload
    except Exception:
        return None


def generate_with_ollama(
    title: str,
    incident_type: str,
    lines: list[ParsedLine],
    runbooks: list[Runbook],
    fallback: dict[str, Any],
) -> dict[str, Any] | None:
    base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
    if not base_url:
        return None
    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": f"{system_prompt()}\n\n{user_prompt(title, incident_type, lines, runbooks, fallback)}",
                "format": "json",
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json().get("response", "{}")
        payload = normalize_llm_payload(json.loads(content), fallback)
        payload["model_used"] = f"ollama:{model}"
        return payload
    except Exception:
        return None


def system_prompt() -> str:
    return (
        "You are LogSage, an SRE assistant. Return only JSON with keys: "
        "summary, root_cause, suggested_fix, severity, service, suspicious_lines, commands, handoff_report. "
        "Use concise, practical engineering language and never invent log lines."
    )


def user_prompt(
    title: str,
    incident_type: str,
    lines: list[ParsedLine],
    runbooks: list[Runbook],
    fallback: dict[str, Any],
) -> str:
    sample = [
        {
            "line_number": line.line_number,
            "timestamp": line.timestamp.isoformat() if line.timestamp else None,
            "level": line.level,
            "service": line.service,
            "message": line.message[:500],
        }
        for line in top_suspicious_lines(lines, Counter(line.fingerprint for line in lines))[:12]
    ]
    runbook_payload = [
        {"title": rb.title, "service": rb.service, "symptoms": rb.symptoms, "fix_steps": rb.fix_steps}
        for rb in runbooks[:8]
    ]
    return json.dumps(
        {
            "title": title,
            "incident_type": incident_type,
            "candidate_analysis": fallback,
            "suspicious_log_sample": sample,
            "runbooks": runbook_payload,
        },
        default=str,
    )


def normalize_llm_payload(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(fallback)
    for key in (
        "summary",
        "root_cause",
        "suggested_fix",
        "severity",
        "service",
        "suspicious_lines",
        "commands",
        "handoff_report",
    ):
        if payload.get(key):
            normalized[key] = payload[key]
    normalized["severity"] = str(normalized["severity"]).lower()
    if not isinstance(normalized.get("suspicious_lines"), list):
        normalized["suspicious_lines"] = fallback["suspicious_lines"]
    if not isinstance(normalized.get("commands"), list):
        normalized["commands"] = fallback["commands"]
    return normalized


def most_common_service(lines: list[ParsedLine]) -> str | None:
    services = [line.service for line in lines if line.service]
    if not services:
        return None
    return Counter(services).most_common(1)[0][0]


def top_suspicious_lines(lines: list[ParsedLine], patterns: Counter[str]) -> list[dict[str, Any]]:
    scored: list[tuple[int, ParsedLine]] = []
    for line in lines:
        text = line.message.lower()
        score = patterns.get(line.fingerprint, 0)
        if line.level in {"ERROR", "CRITICAL", "FATAL"}:
            score += 8
        elif line.level == "WARN":
            score += 3
        if any(word in text for word in ERROR_WORDS):
            score += 5
        if "\n" in line.message:
            score += 4
        if score >= 4:
            scored.append((score, line))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "line_number": line.line_number,
            "timestamp": line.timestamp.isoformat() if line.timestamp else None,
            "level": line.level or "UNKNOWN",
            "service": line.service,
            "message": line.message,
            "score": score,
        }
        for score, line in scored[:5]
    ]


def infer_severity(lines: list[ParsedLine], suspicious: list[dict[str, Any]]) -> str:
    levels = Counter(line.level for line in lines if line.level)
    text = "\n".join(line.message.lower() for line in lines[:2000])
    if levels["CRITICAL"] or levels["FATAL"] or "outage" in text or "out of memory" in text or "oom" in text:
        return "critical"
    if levels["ERROR"] >= 5 or "connection refused" in text or "database is down" in text:
        return "high"
    if levels["ERROR"] or suspicious:
        return "medium"
    if levels["WARN"]:
        return "low"
    return "informational"


def infer_root_cause(suspicious: list[dict[str, Any]], incident_type: str) -> str:
    text = "\n".join(str(item["message"]).lower() for item in suspicious)
    if "connection refused" in text or "econnrefused" in text:
        return "A downstream dependency is refusing connections or is not reachable"
    if "timeout" in text or "timed out" in text:
        return "Requests are timing out, likely from a slow dependency or resource saturation"
    if "out of memory" in text or "oom" in text:
        return "The process is exhausting memory and being killed or degraded"
    if "permission denied" in text or "access denied" in text or "unauthorized" in text:
        return "A credential, permission, or policy change is blocking the service"
    if "deadlock" in text or "database" in text or "sql" in text:
        return "Database errors are causing request failures"
    if "exception" in text or "traceback" in text:
        return "Unhandled application exceptions are surfacing in the request path"
    return f"Likely {incident_type} issue; inspect the highlighted repeated warnings and errors"


def infer_fix(root_cause: str, matched_runbooks: list[Runbook]) -> str:
    if matched_runbooks:
        titles = ", ".join(runbook.title for runbook in matched_runbooks[:2])
        return f"Start with the matching runbook(s): {titles}. Validate symptoms, then apply the documented remediation."
    cause = root_cause.lower()
    if "dependency" in cause or "connections" in cause:
        return "Check dependency health, DNS, network policy, and recent deploys. Restart only after confirming the target service is healthy."
    if "timing out" in cause:
        return "Inspect latency, queue depth, thread pools, and database wait events before increasing timeouts."
    if "memory" in cause:
        return "Capture memory metrics and recent allocation changes, then rollback or increase limits while investigating leaks."
    if "credential" in cause or "permission" in cause:
        return "Verify secrets, IAM/policy changes, token expiry, and service account permissions."
    if "database" in cause:
        return "Check database connectivity, migrations, locks, slow queries, and connection pool saturation."
    return "Reproduce with the same request path, compare against the last known good deploy, and add targeted logging around the failing component."


def commands_for(service: str, root_cause: str) -> list[str]:
    safe_service = service if service != "unknown-service" else "<service>"
    commands = [
        f"kubectl logs deploy/{safe_service} --since=30m | grep -Ei 'error|fatal|timeout|exception'",
        f"kubectl describe deploy/{safe_service}",
        f"kubectl get events --sort-by=.lastTimestamp | tail -40",
        f"docker logs {safe_service} --since 30m",
    ]
    cause = root_cause.lower()
    if "database" in cause or "dependency" in cause or "connections" in cause:
        commands.append(f"kubectl exec deploy/{safe_service} -- nc -vz <dependency-host> <port>")
    if "memory" in cause:
        commands.append(f"kubectl top pod -l app={safe_service}")
    return commands[:5]


def match_runbooks(service: str, lines: list[ParsedLine], runbooks: list[Runbook]) -> list[Runbook]:
    text = "\n".join(line.message.lower() for line in lines[:1500])
    matches: list[tuple[int, Runbook]] = []
    for runbook in runbooks:
        score = 0
        if runbook.service.lower() == service.lower():
            score += 4
        for token in re_tokens(runbook.symptoms):
            if token in text:
                score += 1
        if score:
            matches.append((score, runbook))
    matches.sort(key=lambda item: item[0], reverse=True)
    return [runbook for _, runbook in matches[:3]]


def re_tokens(text: str) -> set[str]:
    return {token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(token) > 3}


def build_handoff_report(
    *,
    title: str,
    service: str,
    severity: str,
    root_cause: str,
    suggested_fix: str,
    suspicious: list[dict[str, Any]],
    commands: list[str],
    matched_runbooks: list[Runbook],
) -> str:
    lines = [
        f"Incident: {title}",
        f"Service: {service}",
        f"Severity: {severity}",
        f"Likely root cause: {root_cause}",
        f"Suggested next step: {suggested_fix}",
        "",
        "Suspicious log lines:",
    ]
    lines.extend(f"- L{item['line_number']} {item['level']}: {item['message'][:220]}" for item in suspicious)
    if matched_runbooks:
        lines.append("")
        lines.append("Relevant runbooks:")
        lines.extend(f"- {runbook.title}: {runbook.fix_steps[:180]}" for runbook in matched_runbooks)
    lines.append("")
    lines.append("Commands to inspect next:")
    lines.extend(f"- {command}" for command in commands)
    return "\n".join(lines)
