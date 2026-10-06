import type { Dispatch, FormEvent, ReactNode, SetStateAction } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Command,
  FileText,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  Server,
  ShieldAlert,
  Trash2,
  UploadCloud
} from "lucide-react";
import {
  createIncident,
  createRunbook,
  deleteRunbook,
  getIncident,
  listIncidents,
  listRunbooks,
  updateIncident
} from "./api";
import type { IncidentDetail, IncidentFilters, IncidentSummary, IncidentStatus, Runbook, Severity } from "./types";

const emptyFilters: IncidentFilters = {
  service: "",
  severity: "",
  status: "",
  keyword: "",
  date_from: "",
  date_to: ""
};

const sampleLogs = `2026-09-18T14:21:01Z INFO service=api request started /checkout
2026-09-18T14:21:03Z ERROR [billing] PaymentException: card gateway timeout
    at BillingClient.charge(BillingClient.java:42)
    at Checkout.submit(Checkout.java:88)
2026-09-18T14:21:04Z WARN service=api retrying checkout`;

function App() {
  const [activeView, setActiveView] = useState<"triage" | "runbooks">("triage");
  const [filters, setFilters] = useState<IncidentFilters>(emptyFilters);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<IncidentDetail | null>(null);
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    title: "Checkout failures",
    incident_type: "payment",
    service: "",
    logs_text: sampleLogs,
    file: null as File | null
  });
  const [runbookDraft, setRunbookDraft] = useState({
    title: "",
    service: "",
    symptoms: "",
    fix_steps: ""
  });

  const severityCounts = useMemo(() => {
    return incidents.reduce<Record<string, number>>((acc, incident) => {
      acc[incident.severity] = (acc[incident.severity] ?? 0) + 1;
      return acc;
    }, {});
  }, [incidents]);

  async function refreshIncidents(nextFilters = filters) {
    setLoading(true);
    setError(null);
    try {
      const data = await listIncidents(nextFilters);
      setIncidents(data);
      if (!selectedId && data[0]) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }

  async function refreshRunbooks() {
    try {
      setRunbooks(await listRunbooks());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runbooks");
    }
  }

  useEffect(() => {
    void refreshIncidents();
    void refreshRunbooks();
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      return;
    }

    let cancelled = false;
    async function loadDetail() {
      try {
        const detail = await getIncident(selectedId as number);
        if (!cancelled) {
          setSelected(detail);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load incident");
        }
      }
    }

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (selected?.status !== "processing") {
      return;
    }
    const timer = window.setInterval(async () => {
      if (!selectedId) {
        return;
      }
      const detail = await getIncident(selectedId);
      setSelected(detail);
      void refreshIncidents();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [selected?.status, selectedId]);

  async function handleCreateIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData();
    formData.set("title", draft.title);
    formData.set("incident_type", draft.incident_type);
    if (draft.service) {
      formData.set("service", draft.service);
    }
    if (draft.logs_text) {
      formData.set("logs_text", draft.logs_text);
    }
    if (draft.file) {
      formData.set("file", draft.file);
    }

    setCreating(true);
    setError(null);
    try {
      const incident = await createIncident(formData);
      setSelectedId(incident.id);
      setDraft((current) => ({ ...current, logs_text: "", file: null }));
      await refreshIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create incident");
    } finally {
      setCreating(false);
    }
  }

  async function handleFilterChange(nextFilters: IncidentFilters) {
    setFilters(nextFilters);
    await refreshIncidents(nextFilters);
  }

  async function handleStatusUpdate(status: IncidentStatus) {
    if (!selected) {
      return;
    }
    const updated = await updateIncident(selected.id, { status });
    setSelected((current) => (current ? { ...current, status: updated.status } : current));
    await refreshIncidents();
  }

  async function handleCreateRunbook(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createRunbook(runbookDraft);
    setRunbookDraft({ title: "", service: "", symptoms: "", fix_steps: "" });
    await refreshRunbooks();
  }

  async function handleDeleteRunbook(id: number) {
    await deleteRunbook(id);
    await refreshRunbooks();
  }

  return (
    <main className="min-h-screen text-slate-950">
      <header className="border-b border-slate-200 bg-white/86 backdrop-blur">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-700 text-white">
              <ShieldAlert size={22} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">LogSage</h1>
              <p className="text-sm text-slate-600">AI log triage and incident tracker</p>
            </div>
          </div>
          <nav className="flex items-center gap-2" aria-label="Primary">
            <TabButton active={activeView === "triage"} onClick={() => setActiveView("triage")} icon={<ClipboardList size={16} />}>
              Triage
            </TabButton>
            <TabButton active={activeView === "runbooks"} onClick={() => setActiveView("runbooks")} icon={<BookOpen size={16} />}>
              Runbooks
            </TabButton>
            <IconButton label="Refresh" onClick={() => refreshIncidents()} disabled={loading}>
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            </IconButton>
          </nav>
        </div>
      </header>

      {error && (
        <div className="mx-auto mt-4 max-w-[1440px] px-4 sm:px-6">
          <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="break-words">{error}</span>
          </div>
        </div>
      )}

      {activeView === "triage" ? (
        <section className="mx-auto grid max-w-[1440px] gap-4 px-4 py-5 sm:px-6 xl:grid-cols-[360px_minmax(380px,1fr)_minmax(420px,0.95fr)]">
          <IncidentForm draft={draft} setDraft={setDraft} creating={creating} onSubmit={handleCreateIncident} />
          <IncidentList
            incidents={incidents}
            selectedId={selectedId}
            filters={filters}
            severityCounts={severityCounts}
            loading={loading}
            onSelect={setSelectedId}
            onFilterChange={handleFilterChange}
          />
          <IncidentPanel incident={selected} runbooks={runbooks} onStatusUpdate={handleStatusUpdate} />
        </section>
      ) : (
        <RunbookPage
          runbooks={runbooks}
          draft={runbookDraft}
          setDraft={setRunbookDraft}
          onSubmit={handleCreateRunbook}
          onDelete={handleDeleteRunbook}
        />
      )}
    </main>
  );
}

function IncidentForm({
  draft,
  setDraft,
  creating,
  onSubmit
}: {
  draft: { title: string; incident_type: string; service: string; logs_text: string; file: File | null };
  setDraft: Dispatch<SetStateAction<{ title: string; incident_type: string; service: string; logs_text: string; file: File | null }>>;
  creating: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form onSubmit={onSubmit} className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">New incident</h2>
          <p className="text-sm text-slate-600">Upload `.log`/`.txt` or paste directly.</p>
        </div>
        <UploadCloud className="text-cyan-700" size={22} aria-hidden="true" />
      </div>

      <Label text="Title">
        <input
          required
          value={draft.title}
          onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
          className="field"
          placeholder="Checkout failures"
        />
      </Label>

      <div className="grid grid-cols-2 gap-3">
        <Label text="Incident type">
          <select
            value={draft.incident_type}
            onChange={(event) => setDraft((current) => ({ ...current, incident_type: event.target.value }))}
            className="field"
          >
            <option value="general">General</option>
            <option value="api">API</option>
            <option value="database">Database</option>
            <option value="payment">Payment</option>
            <option value="deploy">Deploy</option>
            <option value="security">Security</option>
          </select>
        </Label>
        <Label text="Service">
          <input
            value={draft.service}
            onChange={(event) => setDraft((current) => ({ ...current, service: event.target.value }))}
            className="field"
            placeholder="api"
          />
        </Label>
      </div>

      <Label text="Log file">
        <input
          type="file"
          accept=".log,.txt,text/plain"
          onChange={(event) => setDraft((current) => ({ ...current, file: event.target.files?.[0] ?? null }))}
          className="block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:border-cyan-600"
        />
      </Label>

      <Label text="Pasted logs">
        <textarea
          value={draft.logs_text}
          onChange={(event) => setDraft((current) => ({ ...current, logs_text: event.target.value }))}
          className="field min-h-[250px] resize-y font-mono text-xs leading-5"
          placeholder="Paste server, app, or container logs"
        />
      </Label>

      <button
        type="submit"
        disabled={creating}
        className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-cyan-700 px-4 text-sm font-semibold text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {creating ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
        Analyze logs
      </button>
    </form>
  );
}

function IncidentList({
  incidents,
  selectedId,
  filters,
  severityCounts,
  loading,
  onSelect,
  onFilterChange
}: {
  incidents: IncidentSummary[];
  selectedId: number | null;
  filters: IncidentFilters;
  severityCounts: Record<string, number>;
  loading: boolean;
  onSelect: (id: number) => void;
  onFilterChange: (filters: IncidentFilters) => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-4 flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Incident history</h2>
            <p className="text-sm text-slate-600">{incidents.length} matching incidents</p>
          </div>
          <Filter className="text-amber-700" size={20} aria-hidden="true" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(["critical", "high", "medium"] as Severity[]).map((severity) => (
            <div key={severity} className="rounded-lg border border-slate-200 px-3 py-2">
              <div className="text-xs capitalize text-slate-500">{severity}</div>
              <div className="text-lg font-semibold">{severityCounts[severity] ?? 0}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="relative sm:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} aria-hidden="true" />
          <input
            value={filters.keyword}
            onChange={(event) => onFilterChange({ ...filters, keyword: event.target.value })}
            className="field pl-9"
            placeholder="Search logs, titles, incident types"
          />
        </div>
        <input
          value={filters.service}
          onChange={(event) => onFilterChange({ ...filters, service: event.target.value })}
          className="field"
          placeholder="Service"
        />
        <select
          value={filters.severity}
          onChange={(event) => onFilterChange({ ...filters, severity: event.target.value })}
          className="field"
        >
          <option value="">Any severity</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="informational">Informational</option>
        </select>
        <select
          value={filters.status}
          onChange={(event) => onFilterChange({ ...filters, status: event.target.value })}
          className="field"
        >
          <option value="">Any status</option>
          <option value="processing">Processing</option>
          <option value="unresolved">Unresolved</option>
          <option value="resolved">Resolved</option>
          <option value="failed">Failed</option>
        </select>
        <input
          type="date"
          value={filters.date_from}
          onChange={(event) => onFilterChange({ ...filters, date_from: event.target.value })}
          className="field"
        />
      </div>

      <div className="mt-4 max-h-[680px] space-y-2 overflow-auto pr-1 scrollbar-thin">
        {loading && incidents.length === 0 ? (
          <EmptyState icon={<Loader2 className="animate-spin" size={18} />} title="Loading incidents" />
        ) : incidents.length === 0 ? (
          <EmptyState icon={<FileText size={18} />} title="No incidents match" />
        ) : (
          incidents.map((incident) => (
            <button
              key={incident.id}
              type="button"
              onClick={() => onSelect(incident.id)}
              className={`w-full rounded-lg border p-3 text-left transition hover:border-cyan-500 ${
                selectedId === incident.id ? "border-cyan-600 bg-cyan-50" : "border-slate-200 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{incident.title}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1">
                      <Server size={12} aria-hidden="true" />
                      {incident.service ?? "unknown"}
                    </span>
                    <span>{incident.line_count} lines</span>
                  </div>
                </div>
                <SeverityPill severity={incident.severity} />
              </div>
              <div className="mt-3 flex items-center justify-between gap-2">
                <StatusPill status={incident.status} />
                <time className="text-xs text-slate-500">{formatDate(incident.created_at)}</time>
              </div>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function IncidentPanel({
  incident,
  runbooks,
  onStatusUpdate
}: {
  incident: IncidentDetail | null;
  runbooks: Runbook[];
  onStatusUpdate: (status: IncidentStatus) => void;
}) {
  if (!incident) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
        <EmptyState icon={<FileText size={20} />} title="Select an incident" />
      </section>
    );
  }

  const relatedRunbooks = runbooks.filter((runbook) => incident.service && runbook.service.toLowerCase() === incident.service.toLowerCase());

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-200 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <SeverityPill severity={incident.severity} />
              <StatusPill status={incident.status} />
              {incident.status === "processing" && <Loader2 size={16} className="animate-spin text-cyan-700" aria-hidden="true" />}
            </div>
            <h2 className="break-words text-lg font-semibold">{incident.title}</h2>
            <p className="mt-1 text-sm text-slate-600">
              {incident.service ?? "unknown service"} · {incident.incident_type} · {incident.line_count} parsed lines
            </p>
          </div>
          <div className="flex gap-2">
            <IconButton label="Mark unresolved" onClick={() => onStatusUpdate("unresolved")}>
              <AlertTriangle size={16} />
            </IconButton>
            <IconButton label="Mark resolved" onClick={() => onStatusUpdate("resolved")}>
              <CheckCircle2 size={16} />
            </IconButton>
          </div>
        </div>
      </div>

      <div className="max-h-[780px] overflow-auto p-4 scrollbar-thin">
        {incident.analysis ? (
          <div className="space-y-4">
            <PanelBlock title="Diagnosis" icon={<ShieldAlert size={16} />}>
              <p className="text-sm text-slate-700">{incident.analysis.summary}</p>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <KeyValue label="Likely root cause" value={incident.analysis.root_cause} />
                <KeyValue label="Suggested fix" value={incident.analysis.suggested_fix} />
              </dl>
            </PanelBlock>

            <PanelBlock title="Suspicious lines" icon={<AlertTriangle size={16} />}>
              <div className="space-y-2">
                {incident.analysis.suspicious_lines.map((line) => (
                  <div key={`${line.line_number}-${line.score}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                      <span className="font-mono">L{line.line_number}</span>
                      <span>{line.level}</span>
                      {line.service && <span>{line.service}</span>}
                      <span>score {line.score}</span>
                    </div>
                    <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-slate-900">{line.message}</pre>
                  </div>
                ))}
              </div>
            </PanelBlock>

            <PanelBlock title="Commands" icon={<Command size={16} />}>
              <div className="space-y-2">
                {incident.analysis.commands.map((command) => (
                  <code key={command} className="block overflow-auto rounded-lg bg-slate-950 px-3 py-2 font-mono text-xs text-cyan-100">
                    {command}
                  </code>
                ))}
              </div>
            </PanelBlock>

            <PanelBlock title="Handoff report" icon={<FileText size={16} />}>
              <pre className="whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs leading-5 text-slate-800">
                {incident.analysis.handoff_report}
              </pre>
            </PanelBlock>
          </div>
        ) : (
          <EmptyState icon={<Loader2 size={18} className="animate-spin" />} title="Analysis queued" />
        )}

        <PanelBlock title="Related runbooks" icon={<BookOpen size={16} />}>
          {relatedRunbooks.length ? (
            <div className="space-y-2">
              {relatedRunbooks.map((runbook) => (
                <div key={runbook.id} className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                  <div className="font-medium text-emerald-950">{runbook.title}</div>
                  <p className="mt-1 text-sm text-emerald-900">{runbook.fix_steps}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No saved runbook for this service yet.</p>
          )}
        </PanelBlock>

        <PanelBlock title="Parsed lines" icon={<FileText size={16} />}>
          <div className="max-h-64 overflow-auto rounded-lg border border-slate-200 scrollbar-thin">
            <table className="w-full min-w-[560px] border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-3 py-2 font-medium">Line</th>
                  <th className="px-3 py-2 font-medium">Level</th>
                  <th className="px-3 py-2 font-medium">Service</th>
                  <th className="px-3 py-2 font-medium">Message</th>
                </tr>
              </thead>
              <tbody>
                {incident.log_lines.map((line) => (
                  <tr key={line.id} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-mono">{line.line_number}</td>
                    <td className="px-3 py-2">{line.level ?? "-"}</td>
                    <td className="px-3 py-2">{line.service ?? "-"}</td>
                    <td className="px-3 py-2 font-mono">{line.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PanelBlock>
      </div>
    </section>
  );
}

function RunbookPage({
  runbooks,
  draft,
  setDraft,
  onSubmit,
  onDelete
}: {
  runbooks: Runbook[];
  draft: { title: string; service: string; symptoms: string; fix_steps: string };
  setDraft: Dispatch<SetStateAction<{ title: string; service: string; symptoms: string; fix_steps: string }>>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <section className="mx-auto grid max-w-[1200px] gap-4 px-4 py-5 sm:px-6 lg:grid-cols-[380px_1fr]">
      <form onSubmit={onSubmit} className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">New runbook</h2>
            <p className="text-sm text-slate-600">Reusable fixes for repeated incidents.</p>
          </div>
          <BookOpen className="text-emerald-700" size={22} aria-hidden="true" />
        </div>
        <Label text="Title">
          <input required value={draft.title} onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} className="field" />
        </Label>
        <Label text="Service">
          <input required value={draft.service} onChange={(event) => setDraft((current) => ({ ...current, service: event.target.value }))} className="field" />
        </Label>
        <Label text="Symptoms">
          <textarea
            required
            value={draft.symptoms}
            onChange={(event) => setDraft((current) => ({ ...current, symptoms: event.target.value }))}
            className="field min-h-28 resize-y"
          />
        </Label>
        <Label text="Fix steps">
          <textarea
            required
            value={draft.fix_steps}
            onChange={(event) => setDraft((current) => ({ ...current, fix_steps: event.target.value }))}
            className="field min-h-36 resize-y"
          />
        </Label>
        <button type="submit" className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-4 text-sm font-semibold text-white hover:bg-emerald-800">
          <BookOpen size={16} />
          Save runbook
        </button>
      </form>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
        <h2 className="text-base font-semibold">Saved runbooks</h2>
        <div className="mt-4 grid gap-3">
          {runbooks.length === 0 ? (
            <EmptyState icon={<BookOpen size={18} />} title="No runbooks saved" />
          ) : (
            runbooks.map((runbook) => (
              <article key={runbook.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{runbook.title}</h3>
                    <p className="mt-1 text-sm text-slate-600">{runbook.service}</p>
                  </div>
                  <IconButton label="Delete runbook" onClick={() => onDelete(runbook.id)}>
                    <Trash2 size={16} />
                  </IconButton>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <KeyValue label="Symptoms" value={runbook.symptoms} />
                  <KeyValue label="Fix steps" value={runbook.fix_steps} />
                </div>
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

function Label({ text, children }: { text: string; children: ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-medium uppercase text-slate-600">{text}</span>
      {children}
    </label>
  );
}

function PanelBlock({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-4 first:mt-0">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
        <span className="text-slate-500">{icon}</span>
        {title}
      </div>
      {children}
    </section>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-800">{value}</dd>
    </div>
  );
}

function SeverityPill({ severity }: { severity: Severity }) {
  const styles: Record<Severity, string> = {
    critical: "bg-rose-100 text-rose-800 border-rose-200",
    high: "bg-orange-100 text-orange-800 border-orange-200",
    medium: "bg-amber-100 text-amber-800 border-amber-200",
    low: "bg-emerald-100 text-emerald-800 border-emerald-200",
    informational: "bg-sky-100 text-sky-800 border-sky-200",
    unknown: "bg-slate-100 text-slate-700 border-slate-200"
  };
  return <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold capitalize ${styles[severity] ?? styles.unknown}`}>{severity}</span>;
}

function StatusPill({ status }: { status: IncidentStatus }) {
  const styles: Record<IncidentStatus, string> = {
    processing: "bg-cyan-100 text-cyan-800 border-cyan-200",
    unresolved: "bg-amber-100 text-amber-800 border-amber-200",
    resolved: "bg-emerald-100 text-emerald-800 border-emerald-200",
    failed: "bg-rose-100 text-rose-800 border-rose-200"
  };
  return <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold capitalize ${styles[status]}`}>{status}</span>;
}

function TabButton({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: ReactNode; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-medium ${
        active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:border-cyan-600"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

function IconButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-cyan-600 hover:text-cyan-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function EmptyState({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
      <div className="flex items-center gap-2">
        {icon}
        <span>{title}</span>
      </div>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export default App;
