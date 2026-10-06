export type Severity = "unknown" | "informational" | "low" | "medium" | "high" | "critical";
export type IncidentStatus = "processing" | "unresolved" | "resolved" | "failed";

export type SuspiciousLine = {
  line_number: number;
  timestamp: string | null;
  level: string;
  service: string | null;
  message: string;
  score: number;
};

export type Analysis = {
  id: number;
  incident_id: number;
  summary: string;
  root_cause: string;
  suggested_fix: string;
  model_used: string;
  severity: Severity;
  suspicious_lines: SuspiciousLine[];
  commands: string[];
  handoff_report: string;
  created_at: string;
};

export type LogLine = {
  id: number;
  line_number: number;
  timestamp: string | null;
  level: string | null;
  service: string | null;
  message: string;
  raw: string;
  fingerprint: string;
};

export type IncidentSummary = {
  id: number;
  title: string;
  incident_type: string;
  service: string | null;
  severity: Severity;
  status: IncidentStatus;
  created_at: string;
  line_count: number;
  has_analysis: boolean;
};

export type IncidentDetail = IncidentSummary & {
  raw_preview: string | null;
  log_lines: LogLine[];
  analysis: Analysis | null;
};

export type Runbook = {
  id: number;
  title: string;
  service: string;
  symptoms: string;
  fix_steps: string;
  created_at: string;
};

export type RunbookDraft = Omit<Runbook, "id" | "created_at">;

export type IncidentFilters = {
  service: string;
  severity: string;
  status: string;
  keyword: string;
  date_from: string;
  date_to: string;
};
