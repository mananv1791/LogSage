import type { IncidentDetail, IncidentFilters, IncidentSummary, Runbook, RunbookDraft } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function listIncidents(filters: IncidentFilters): Promise<IncidentSummary[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return request<IncidentSummary[]>(`/api/incidents${query ? `?${query}` : ""}`);
}

export async function getIncident(id: number): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/api/incidents/${id}`);
}

export async function updateIncident(id: number, payload: Partial<IncidentSummary>): Promise<IncidentSummary> {
  return request<IncidentSummary>(`/api/incidents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function createIncident(formData: FormData): Promise<IncidentSummary> {
  return request<IncidentSummary>("/api/incidents", {
    method: "POST",
    body: formData
  });
}

export async function listRunbooks(): Promise<Runbook[]> {
  return request<Runbook[]>("/api/runbooks");
}

export async function createRunbook(payload: RunbookDraft): Promise<Runbook> {
  return request<Runbook>("/api/runbooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteRunbook(id: number): Promise<void> {
  await request<void>(`/api/runbooks/${id}`, { method: "DELETE" });
}
