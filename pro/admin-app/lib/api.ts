/**
 * 어드민 앱 API 클라이언트.
 *
 * 모든 의료진 어드민 화면(대시보드·Pre-Visit Report·PRO 설정·도구 라이브러리·
 * 커스텀 세트 빌더·일별 응답·Audit·Jobs)이 이 모듈을 통해 백엔드와 통신.
 *
 * - cache: "no-store" — 어드민은 항상 최신 데이터 (의료 의사결정용)
 * - 에러 메시지는 디버깅 위해 method·URL·응답 body 일부 포함
 *
 * 환경변수: NEXT_PUBLIC_API_URL (Vercel 배포 시 backend URL 주입)
 */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * 공통 fetch wrapper.
 *
 * 실패 케이스:
 *  - 네트워크 오류    → "Network error → METHOD URL: ..."
 *  - non-2xx 응답     → "STATUS STATUSTEXT ← METHOD URL :: <body 200자>"
 */
async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API}${path}`;
  const method = init?.method ?? "GET";
  let r: Response;
  try {
    r = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
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
  id: string; name: string; birth_year: number;
  icd10: string; cycle_day: number; caregiver_phone: string;
};

export type DashboardRow = {
  patient: Patient;
  level: "critical" | "warning" | "stable";
  red_count: number;
  yellow_count: number;
  summary: string;
  session_count: number;
};

export type Alert = {
  tool: string; subscale: string; value: number;
  level: "red" | "yellow";
};

export type PreVisitReport = {
  summary: string;
  alerts: Alert[];
  trend: Record<string, { date: string; value: number; level: string | null }[]>;
  lifelog_correlation: string;
  window_days: number;
  session_count: number;
  patient: Patient;
};

export type ProConfig = {
  patient_id: string;
  pro_ctcae: Record<string, string[]>;
  hads_enabled: boolean;
  hads_subscales: string[];
  frequency: string;
  cycle_trigger_days: number[];
  thresholds: {
    pro_ctcae_red: number;
    pro_ctcae_persist_days: number;
    hads_yellow: number;
    hads_red: number;
  };
  updated_at: string;
  updated_by: string;
};

export type ProToolCatalog = {
  pro_ctcae: {
    symptom: string;
    label: string;
    attributes: string[];
    questions: Record<string, string>;
  }[];
  hads: { subscales: { code: string; label: string; items: number }[] };
  frequencies: { code: string; label: string }[];
};

export type ToolLibraryItem = {
  tool_code: string;
  name: string;
  domain: string;
  items: number | string;
  duration_min: number;
  license: string;
  evidence_grade: string;
  default_frequency: string;
};

export type ProConfigAudit = {
  id: number;
  changed_at: string;
  changed_by: string;
  action: string;
  diff: { before: any; after: any };
};

export const api = {
  dashboard: () => req<DashboardRow[]>("/api/admin/dashboard"),
  preVisit: (id: string) => req<PreVisitReport>(`/api/patients/${id}/pre-visit-report`),
  patient: (id: string) => req<Patient>(`/api/patients/${id}`),
  sendPush: (data: { patient_id: string; title?: string; body?: string; url?: string }) =>
    req<{ sent: number; failed: any[] }>("/api/push/send", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  proConfig: (id: string) => req<ProConfig>(`/api/patients/${id}/pro-config`),
  catalog: () => req<ProToolCatalog>(`/api/pro-tools/catalog`),
  updateProConfig: (id: string, body: any) =>
    req<{ updated: boolean; config: ProConfig }>(
      `/api/patients/${id}/pro-config`,
      { method: "PUT", body: JSON.stringify(body) }
    ),
  toolLibrary: (q?: string) =>
    req<ToolLibraryItem[]>(`/api/pro-tools/library${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  toolDetail: (code: string) =>
    req<any>(`/api/pro-tools/library/${encodeURIComponent(code)}`),
  recommendProSet: (icd10: string, age?: number) =>
    req<any>(`/api/pro-tools/recommend?icd10=${encodeURIComponent(icd10)}${age ? `&age=${age}` : ""}`),
  customSets: () => req<any[]>(`/api/pro-sets`),
  customSet: (id: number) => req<any>(`/api/pro-sets/${id}`),
  createCustomSet: (body: any) =>
    req<any>(`/api/pro-sets`, { method: "POST", body: JSON.stringify(body) }),
  updateCustomSet: (id: number, body: any) =>
    req<any>(`/api/pro-sets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteCustomSet: (id: number) =>
    req<any>(`/api/pro-sets/${id}`, { method: "DELETE" }),
  applyCustomSet: (patient_id: string, set_id: number) =>
    req<any>(`/api/patients/${patient_id}/apply-pro-set/${set_id}`,
             { method: "POST" }),
  loadDefaults: (patient_id: string) =>
    req<any>(`/api/patients/${patient_id}/load-defaults`, { method: "POST" }),
  responsesByDay: (patient_id: string, days = 30) =>
    req<any>(`/api/patients/${patient_id}/responses-by-day?days=${days}`),
  configAudit: (id: string) =>
    req<ProConfigAudit[]>(`/api/patients/${id}/pro-config/audit`),
  // jobs (cron triggers)
  jobPrecomputePreVisit: () =>
    req<any>("/api/jobs/precompute-pre-visit", { method: "POST" }),
  jobCheckMcid: () =>
    req<any>("/api/jobs/check-mcid-and-push", { method: "POST" }),
  jobCheckNonResponse: () =>
    req<any>("/api/jobs/check-non-response", { method: "POST" }),
};
export default api;
