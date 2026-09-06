export type ApplicationRow = {
  application_id?: string;
  id?: string;
  name?: string;
};

export type Decision = {
  category?: string;
  outcome?: string;
  scenario?: string;
  reasoning?: string;
};

export type CausedLink = {
  from?: string;
  to?: string;
};

export type Chunk = {
  kind?: string;
  application_id?: string;
  score?: number | string;
  source?: string;
  text?: string;
};

export type EntityHit = {
  text?: string;
  type?: string;
};

export type RetrievePayload = {
  query?: string;
  chunks?: Chunk[];
  decisions?: Decision[];
  caused?: CausedLink[];
  entities?: EntityHit[];
};

export type ChatPayload = RetrievePayload & {
  answer?: string;
  source?: string;
  error?: string;
};

export type ImportResult = {
  applicant_name?: string;
  application_id?: string;
  entity_count?: number | string;
  decisions?: unknown;
  flow_run_id?: string;
  status?: string;
  error?: string;
};

export type OntologyClass = {
  name?: string;
  description?: string;
};

export type OntologyProperty = {
  domain?: string;
  name?: string;
  range?: string;
  required?: boolean;
  description?: string;
};

export type OntologyRelationship = {
  name?: string;
  domain?: string;
  range?: string;
  required?: boolean;
  description?: string;
};

export type OntologyViolation = {
  id?: string;
  type?: string;
  field?: string;
  message?: string;
};

export type OntologyPayload = {
  ontology?: {
    classes?: OntologyClass[];
    properties?: OntologyProperty[];
    relationships?: OntologyRelationship[];
  };
  owl?: string;
  shacl?: string;
  validation?: {
    conforms?: boolean;
    checked?: number | string;
    violations?: OntologyViolation[];
  };
};

const API_BASE = String(import.meta.env.VITE_LENDING_API_BASE || "http://localhost:8001").replace(
  /\/$/,
  "",
);

export const EXPLORER_URL = String(
  import.meta.env.VITE_LENDING_EXPLORER_URL || "http://localhost:8000",
).replace(/\/$/, "") + "/";

export function lendingApi(path: string): string {
  return API_BASE + path;
}

async function readJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

export async function listApplications(): Promise<ApplicationRow[]> {
  const response = await fetch(lendingApi("/api/lending/applications"));
  const body = await readJson<{ applications?: ApplicationRow[] }>(response);
  return body.applications || [];
}

export async function importApplication(form: FormData): Promise<ImportResult> {
  const response = await fetch(lendingApi("/api/lending/import"), {
    method: "POST",
    body: form,
  });
  const body = await readJson<ImportResult>(response);
  if (!response.ok) {
    throw new Error(body.error || "导入失败");
  }
  return body;
}

export async function getImportJob(flowRunId: string): Promise<ImportResult> {
  const response = await fetch(lendingApi(`/api/lending/jobs/${encodeURIComponent(flowRunId)}`));
  const body = await readJson<ImportResult>(response);
  if (!response.ok) {
    throw new Error(body.error || "查询导入任务失败");
  }
  return body;
}

export async function retrieveQuery(query: string): Promise<RetrievePayload> {
  const response = await fetch(lendingApi("/api/lending/retrieve"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return readJson<RetrievePayload>(response);
}

export async function chatQuery(query: string): Promise<ChatPayload> {
  const response = await fetch(lendingApi("/api/lending/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return readJson<ChatPayload>(response);
}

export async function loadOntology(): Promise<OntologyPayload> {
  const response = await fetch(lendingApi("/api/lending/ontology"));
  return readJson<OntologyPayload>(response);
}
