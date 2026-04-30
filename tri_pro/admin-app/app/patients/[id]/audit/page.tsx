"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import api, { ProConfigAudit } from "@/lib/api";

const SYMPTOM_LABEL: Record<string, string> = {
  fatigue: "피로", appetite: "식욕부진", nausea: "오심·구토",
  diarrhea: "설사", neuropathy: "손발 저림",
};
const ATTR_LABEL: Record<string, string> = {
  freq: "빈도", severity: "강도", interference: "일상 방해",
};
const FREQ_LABEL: Record<string, string> = {
  daily: "매일", every_3_days: "3일마다", weekly: "주 1회",
  monthly: "월 1회", cycle: "사이클 기반",
};
const THRESHOLD_LABEL: Record<string, string> = {
  pro_ctcae_red: "PRO-CTCAE RED 점수",
  pro_ctcae_persist_days: "PRO-CTCAE 지속 일수",
  hads_yellow: "HADS YELLOW 임계값",
  hads_red: "HADS RED 임계값",
};

type Event = {
  icon: string;
  label: string;
  before?: string;
  after?: string;
  color: string;
};

function diffToEvents(diff: any, action: string): Event[] {
  const events: Event[] = [];
  const before = diff?.before || {};
  const after = diff?.after || {};

  // ── 액션별 메타 ─────────────────────────────
  if (action === "apply_custom_set" && diff.set_name) {
    events.push({
      icon: "📋",
      label: `커스텀 세트 "${diff.set_name}" 적용`,
      color: "bg-purple-50 border-purple-200 text-purple-900",
    });
  }
  if (action === "load_defaults") {
    events.push({
      icon: "📚",
      label: `ICD-10 기본값 적용 (${diff.icd10}, ${diff.age}세)`,
      after: diff.rationale,
      color: "bg-blue-50 border-blue-200 text-blue-900",
    });
  }

  // ── 도구 활성/비활성 (tools.X.enabled) ─────
  const beforeTools = before.tools || {};
  const afterTools = after.tools || {};
  const allToolKeys = new Set([
    ...Object.keys(beforeTools), ...Object.keys(afterTools),
  ]);
  for (const code of allToolKeys) {
    if (code === "__custom_questions__") continue;
    const b = beforeTools[code] ?? {};
    const a = afterTools[code] ?? {};
    const wasOn = !!b.enabled;
    const isOn = !!a.enabled;
    if (!wasOn && isOn) {
      events.push({
        icon: "✅",
        label: `${code} 활성화`,
        color: "bg-green-50 border-green-200 text-green-900",
      });
    } else if (wasOn && !isOn) {
      events.push({
        icon: "❌",
        label: `${code} 비활성화`,
        color: "bg-red-50 border-red-200 text-red-900",
      });
    } else if (wasOn && isOn && b.frequency !== a.frequency && a.frequency) {
      events.push({
        icon: "🔄",
        label: `${code} 빈도 변경`,
        before: FREQ_LABEL[b.frequency] ?? b.frequency,
        after: FREQ_LABEL[a.frequency] ?? a.frequency,
        color: "bg-yellow-50 border-yellow-200 text-yellow-900",
      });
    }
  }

  // ── PRO-CTCAE 매트릭스 ──────────────────────
  const beforePC = before.pro_ctcae || {};
  const afterPC = after.pro_ctcae || {};
  const allSymptoms = new Set([
    ...Object.keys(beforePC), ...Object.keys(afterPC),
  ]);
  for (const sym of allSymptoms) {
    const symLabel = SYMPTOM_LABEL[sym] ?? sym;
    const bAttrs = new Set<string>(beforePC[sym] || []);
    const aAttrs = new Set<string>(afterPC[sym] || []);
    for (const attr of aAttrs) {
      if (!bAttrs.has(attr)) {
        events.push({
          icon: "➕",
          label: `${symLabel} ${ATTR_LABEL[attr] ?? attr} 측정 추가`,
          color: "bg-emerald-50 border-emerald-200 text-emerald-900",
        });
      }
    }
    for (const attr of bAttrs) {
      if (!aAttrs.has(attr)) {
        events.push({
          icon: "➖",
          label: `${symLabel} ${ATTR_LABEL[attr] ?? attr} 측정 제거`,
          color: "bg-orange-50 border-orange-200 text-orange-900",
        });
      }
    }
  }

  // ── HADS 서브스케일 ─────────────────────────
  const beforeHADS = new Set<string>(before.hads_subscales || []);
  const afterHADS = new Set<string>(after.hads_subscales || []);
  for (const s of afterHADS) {
    if (!beforeHADS.has(s)) {
      events.push({
        icon: "➕",
        label: `HADS-${s} (${s === "A" ? "불안" : "우울"}) 추가`,
        color: "bg-emerald-50 border-emerald-200 text-emerald-900",
      });
    }
  }
  for (const s of beforeHADS) {
    if (!afterHADS.has(s)) {
      events.push({
        icon: "➖",
        label: `HADS-${s} (${s === "A" ? "불안" : "우울"}) 제거`,
        color: "bg-orange-50 border-orange-200 text-orange-900",
      });
    }
  }

  // ── HADS 활성 토글 ──────────────────────────
  if (before.hads_enabled !== undefined && after.hads_enabled !== undefined) {
    if (!before.hads_enabled && after.hads_enabled) {
      events.push({
        icon: "✅", label: "HADS 활성화",
        color: "bg-green-50 border-green-200 text-green-900",
      });
    } else if (before.hads_enabled && !after.hads_enabled) {
      events.push({
        icon: "❌", label: "HADS 비활성화",
        color: "bg-red-50 border-red-200 text-red-900",
      });
    }
  }

  // ── 전체 PRO-CTCAE 빈도 ─────────────────────
  if (before.frequency !== undefined && after.frequency !== undefined &&
      before.frequency !== after.frequency) {
    events.push({
      icon: "🔄",
      label: "PRO-CTCAE 전체 빈도 변경",
      before: FREQ_LABEL[before.frequency] ?? before.frequency,
      after: FREQ_LABEL[after.frequency] ?? after.frequency,
      color: "bg-yellow-50 border-yellow-200 text-yellow-900",
    });
  }

  // ── 임계값 ──────────────────────────────────
  const beforeTH = before.thresholds || {};
  const afterTH = after.thresholds || {};
  for (const key of Object.keys(afterTH)) {
    if (beforeTH[key] !== afterTH[key]) {
      events.push({
        icon: "🔧",
        label: THRESHOLD_LABEL[key] ?? key,
        before: String(beforeTH[key] ?? "—"),
        after: String(afterTH[key]),
        color: "bg-indigo-50 border-indigo-200 text-indigo-900",
      });
    }
  }

  // ── 커스텀 문항 ─────────────────────────────
  const bCustom = beforeTools.__custom_questions__?.questions ?? [];
  const aCustom = afterTools.__custom_questions__?.questions ?? [];
  if (bCustom.length === 0 && aCustom.length > 0) {
    events.push({
      icon: "➕",
      label: `커스텀 문항 ${aCustom.length}개 추가`,
      color: "bg-purple-50 border-purple-200 text-purple-900",
    });
  } else if (bCustom.length > 0 && aCustom.length === 0) {
    events.push({
      icon: "➖",
      label: `커스텀 문항 ${bCustom.length}개 제거`,
      color: "bg-orange-50 border-orange-200 text-orange-900",
    });
  } else if (bCustom.length !== aCustom.length) {
    events.push({
      icon: "🔄", label: "커스텀 문항 변경",
      before: `${bCustom.length}개`, after: `${aCustom.length}개`,
      color: "bg-purple-50 border-purple-200 text-purple-900",
    });
  }

  return events;
}

const ACTION_LABEL: Record<string, { label: string; color: string }> = {
  updated: { label: "수동 변경", color: "bg-gray-100 text-gray-700" },
  load_defaults: { label: "기본값 적용", color: "bg-blue-100 text-blue-800" },
  apply_custom_set: { label: "커스텀 세트 적용", color: "bg-purple-100 text-purple-800" },
  created: { label: "최초 생성", color: "bg-green-100 text-green-800" },
};

export default function AuditLogPage() {
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const [logs, setLogs] = useState<ProConfigAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRaw, setShowRaw] = useState<Record<number, boolean>>({});

  useEffect(() => {
    api.configAudit(patientId).then((rs) => {
      setLogs(rs);
      setLoading(false);
    });
  }, [patientId]);

  if (loading) return <div className="p-8 text-center text-gray-400">로딩...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <header>
        <Link href={`/patients/${patientId}/config`} className="text-sm text-gray-500">
          ← PRO 설정으로
        </Link>
        <h1 className="text-2xl font-bold mt-1">PRO 세트 변경 이력</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          환자 {patientId} · {logs.length}건의 변경
        </p>
      </header>

      {logs.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-10 text-center text-gray-400">
          변경 이력 없음
        </div>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => {
            const meta = ACTION_LABEL[log.action] || {
              label: log.action, color: "bg-gray-100 text-gray-700",
            };
            const events = diffToEvents(log.diff, log.action);
            return (
              <div
                key={log.id}
                className="bg-white border border-gray-200 rounded-2xl p-4"
              >
                <div className="flex items-center justify-between mb-3 gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${meta.color}`}
                    >
                      {meta.label}
                    </span>
                    <span className="text-xs text-gray-500">
                      by <strong>{log.changed_by}</strong>
                    </span>
                  </div>
                  <span className="text-[11px] text-gray-500">
                    {new Date(log.changed_at).toLocaleString("ko-KR", {
                      month: "short", day: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </span>
                </div>

                {events.length === 0 ? (
                  <div className="text-xs text-gray-400 italic">
                    감지된 변경사항 없음
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {events.map((ev, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm border ${ev.color}`}
                      >
                        <span className="text-base">{ev.icon}</span>
                        <span className="flex-1 font-semibold">{ev.label}</span>
                        {ev.before !== undefined && ev.after !== undefined && (
                          <span className="text-xs whitespace-nowrap">
                            <span className="line-through text-gray-500">{ev.before}</span>
                            <span className="mx-1">→</span>
                            <strong>{ev.after}</strong>
                          </span>
                        )}
                        {ev.before === undefined && ev.after !== undefined && (
                          <span className="text-xs italic text-right">{ev.after}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={() => setShowRaw((s) => ({ ...s, [log.id]: !s[log.id] }))}
                  className="mt-3 text-[10px] text-gray-400 hover:text-gray-600"
                >
                  {showRaw[log.id] ? "▾ Raw JSON 숨기기" : "▸ Raw JSON 보기"}
                </button>
                {showRaw[log.id] && (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      <div className="text-[10px] text-red-700 font-bold mb-1">Before</div>
                      <pre className="text-[9px] bg-red-50 border border-red-200 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(log.diff?.before, null, 2)}
                      </pre>
                    </div>
                    <div>
                      <div className="text-[10px] text-green-700 font-bold mb-1">After</div>
                      <pre className="text-[9px] bg-green-50 border border-green-200 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(log.diff?.after, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
