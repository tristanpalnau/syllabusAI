const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface StructuredSummary {
  exam_dates: { name: string; date: string }[];
  assignment_deadlines: { name: string; date: string }[];
  grade_weights: Record<string, number>;
  late_policy: string | null;
  attendance_policy: string | null;
  office_hours: { instructor: string; time: string; location: string }[];
  instructor: { name: string; email?: string } | null;
  course_name: string | null;
}

export interface UploadResponse {
  session_id: string;
  structured_summary: StructuredSummary;
}

export interface QueryResponse {
  answer: string;
  layer_used: "structured" | "rag";
  source?: string;
}

export async function uploadSyllabus(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function querySession(
  session_id: string,
  question: string
): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id, question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Query failed");
  }
  return res.json();
}

export async function pingSession(session_id: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/session/${session_id}/ping`);
    return res.ok;
  } catch {
    return false;
  }
}

export function calendarUrl(session_id: string): string {
  return `${BASE}/session/${session_id}/calendar`;
}
