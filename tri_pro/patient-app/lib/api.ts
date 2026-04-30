/**
 * 환자앱 API 클라이언트.
 *
 * 일반 모드(`/`, `/pro`, `/talk`, `/result`)와 어르신 모드(`/elder/*`)가
 * 모두 이 모듈을 통해 백엔드와 통신. 동일 endpoint·동일 응답 구조 사용으로
 * 모드 등가성(FN-MODE-007) 보장.
 *
 * 환경변수: NEXT_PUBLIC_API_URL (배포 시 backend URL 주입).
 *
 * 에러 메시지에 method·URL·body 포함 — Service Worker·푸시 디버깅 시 유리.
 */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * 공통 fetch wrapper.
 *
 * 어드민과 거의 동일하지만 환자앱은 Service Worker를 활용하므로
 * cache 옵션은 default (브라우저 휴리스틱). 빠른 재방문 응답성 우선.
 */
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API}${path}`;
  const method = init?.method ?? "GET";
  let r: Response;
  try {
    r = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (e: any) {
    throw new Error(`Network error → ${method} ${url}: ${e.message}`);
  }
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new Error(
      `${r.status} ${r.statusText} ← ${method} ${url}${body ? ` :: ${body.slice(0, 200)}` : ""}`
    );
  }
  return r.json();
}

export type Patient = {
  id: string;
  name: string;
  birth_year: number;
  icd10: string;
  cycle_day: number;
  caregiver_phone: string;
};

export type ProSession = {
  id: number;
  patient_id: string;
  started_at: string;
  completed_at: string | null;
  ui_mode: string;
};

export type ProScore = {
  id: number;
  session_id: number;
  patient_id: string;
  tool_code: string;
  subscale: string | null;
  value: number;
  classification: string | null;
  mcid_flag: string | null;
  computed_at: string;
};

export type DynamicProForm = {
  pro_ctcae: {
    symptom: string;
    attribute: "freq" | "severity" | "interference";
    question: string;
    scale_labels: string[];
  }[];
  hads: {
    code: string;
    subscale: "A" | "D";
    question: string;
    reverse: boolean;
  }[];
  frequency: string;
  patient_id: string;
};

export type QuickCategory = {
  id: string;
  label: string;
  symptoms: string[];
};

export type FullModeStatus = {
  requires_full: boolean;
  reason: string | null;
  days_since_last_full: number | null;
  last_full_at?: string;
};

export const api = {
  patients: () => req<Patient[]>("/api/patients"),
  patient: (id: string) => req<Patient>(`/api/patients/${id}`),
  proTools: () => req<any>("/api/pro-tools"),
  proForm: (patient_id: string) =>
    req<DynamicProForm>(`/api/patients/${patient_id}/pro-form`),
  quickCategories: () => req<QuickCategory[]>("/api/quick-categories"),
  fullModeStatus: (patient_id: string) =>
    req<FullModeStatus>(`/api/patients/${patient_id}/full-mode-status`),
  submitQuickScreening: (session_id: number, selected: string[]) =>
    req<DynamicProForm>(`/api/pro-sessions/${session_id}/quick-screening`, {
      method: "POST",
      body: JSON.stringify({ session_id, selected_categories: selected }),
    }),
  applyCarryOver: (session_id: number) =>
    req<{ copied: number; from_session: number }>(
      `/api/pro-sessions/${session_id}/apply-carry-over`,
      { method: "POST" }
    ),
  startSession: (patient_id: string, ui_mode = "general", flex_mode = "full") =>
    req<ProSession>("/api/pro-sessions", {
      method: "POST",
      body: JSON.stringify({ patient_id, ui_mode, flex_mode }),
    }),
  submitResponses: (session_id: number, responses: any[]) =>
    req(`/api/pro-sessions/${session_id}/responses`, {
      method: "POST",
      body: JSON.stringify({ session_id, responses }),
    }),
  completeSession: (session_id: number) =>
    req<{ completed: boolean; scores: ProScore[] }>(
      `/api/pro-sessions/${session_id}/complete`,
      { method: "POST" }
    ),
  history: (patient_id: string) =>
    req<{ sessions: ProSession[]; scores: ProScore[] }>(
      `/api/patients/${patient_id}/pro-history`
    ),
  talk: (text: string, patient_id?: string) =>
    req<{ type: string; response: string; matched: string }>("/api/llm/talk", {
      method: "POST",
      body: JSON.stringify({ text, patient_id }),
    }),
  vapidKey: () => req<{ public_key: string }>("/api/push/vapid-public-key"),
  pushSubscribe: (data: any) =>
    req("/api/push/subscribe", { method: "POST", body: JSON.stringify(data) }),
  pushSubscriptions: (patient_id: string) =>
    req<{ patient_id: string; count: number; subscriptions: any[] }>(
      `/api/push/subscriptions/${patient_id}`
    ),
};

export default api;
