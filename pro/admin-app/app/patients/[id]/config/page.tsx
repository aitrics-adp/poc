"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import api, { ProConfig, ProToolCatalog } from "@/lib/api";

const SYMPTOM_LABELS: Record<string, string> = {
  fatigue: "피로", appetite: "식욕부진", nausea: "오심·구토",
  diarrhea: "설사", neuropathy: "손발 저림 (신경병증)",
};

const FREQ_LABELS: Record<string, string> = {
  daily: "매일", every_3_days: "3일마다", weekly: "주 1회",
  monthly: "월 1회", cycle: "사이클 기반",
};

const TOOLS = [
  { code: "PRO-CTCAE", desc: "항암 부작용 (빈도/강도/일상)", items: "5증상×2~3속성" },
  { code: "HADS",      desc: "불안·우울 (Hospital Anxiety & Depression)", items: "14문항" },
  { code: "FACT-C",    desc: "대장암 특이 QoL (PWB·SWB·EWB·FWB·CCS)", items: "36문항" },
  { code: "FACIT-F",   desc: "암성 피로 (Fatigue Subscale)", items: "13문항" },
  { code: "PSQI",      desc: "수면의 질", items: "19문항" },
];

export default function PatientConfigPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const patientId = params.id;

  const [cfg, setCfg] = useState<ProConfig | null>(null);
  const [catalog, setCatalog] = useState<ProToolCatalog | null>(null);
  const [customSets, setCustomSets] = useState<any[]>([]);
  const [showCustomPicker, setShowCustomPicker] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const reload = async () => {
    const [c, cat, sets] = await Promise.all([
      api.proConfig(patientId),
      api.catalog(),
      api.customSets().catch(() => []),
    ]);
    setCfg(c);
    setCatalog(cat);
    setCustomSets(sets);
  };

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [patientId]);

  if (loading || !cfg || !catalog)
    return <div className="p-8 text-center text-gray-400">로딩...</div>;

  const tools = cfg.tools || {};
  const customQs = (tools as any).__custom_questions__;

  // ──────────── PRO-CTCAE 매트릭스 ────────────
  const togglePCTCAEAttr = (sym: string, attr: string) => {
    setCfg((prev) => {
      if (!prev) return prev;
      const cur = prev.pro_ctcae[sym] ?? [];
      const next = cur.includes(attr)
        ? cur.filter((a) => a !== attr)
        : [...cur, attr];
      const newMap = { ...prev.pro_ctcae };
      if (next.length > 0) newMap[sym] = next;
      else delete newMap[sym];
      return { ...prev, pro_ctcae: newMap };
    });
  };

  // ──────────── 도구 ON/OFF ────────────
  const toolEnabled = (code: string) => {
    if (code === "PRO-CTCAE") return Object.keys(cfg.pro_ctcae).length > 0;
    if (code === "HADS") return cfg.hads_enabled;
    return Boolean((tools as any)[code]?.enabled);
  };

  const toolRequired = (code: string) =>
    Boolean((tools as any)[code]?.required);

  const toolFrequency = (code: string) => {
    if (code === "PRO-CTCAE") return cfg.frequency;
    return (tools as any)[code]?.frequency ?? "monthly";
  };

  const toggleTool = (code: string, on: boolean) => {
    if (toolRequired(code) && !on) {
      setMsg(`⚠️ ${code}는 필수 도구라 비활성화할 수 없습니다`);
      return;
    }
    setCfg((p) => {
      if (!p) return p;
      if (code === "PRO-CTCAE") {
        return {
          ...p,
          pro_ctcae: on
            ? Object.keys(p.pro_ctcae).length > 0
              ? p.pro_ctcae
              : { fatigue: ["freq", "severity"], nausea: ["severity"] }
            : {},
        };
      }
      if (code === "HADS") {
        return { ...p, hads_enabled: on };
      }
      const newTools: any = { ...p.tools };
      newTools[code] = { ...(newTools[code] ?? {}), enabled: on };
      return { ...p, tools: newTools };
    });
  };

  const setToolFreq = (code: string, freq: string) => {
    setCfg((p) => {
      if (!p) return p;
      if (code === "PRO-CTCAE") return { ...p, frequency: freq };
      const newTools: any = { ...p.tools };
      newTools[code] = { ...(newTools[code] ?? {}), frequency: freq };
      return { ...p, tools: newTools };
    });
  };

  const toggleHadsSub = (sub: string) =>
    setCfg((p) => {
      if (!p) return p;
      const cur = p.hads_subscales;
      const next = cur.includes(sub)
        ? cur.filter((s) => s !== sub)
        : [...cur, sub];
      return { ...p, hads_subscales: next };
    });

  const setThreshold = (key: keyof ProConfig["thresholds"], val: number) =>
    setCfg((p) => p ? { ...p, thresholds: { ...p.thresholds, [key]: val } } : p);

  // ──────────── 액션 ────────────
  const loadDefaults = async () => {
    if (!confirm("ICD-10 기본 추천값으로 초기화하시겠습니까? 현재 설정이 덮어쓰여집니다."))
      return;
    setSaving(true);
    try {
      const r = await api.loadDefaults(patientId);
      await reload();
      setMsg(
        `✅ 기본값 적용: 필수 ${r.required.length}개, 선택 ${r.optional.length}개`
      );
    } catch (e: any) {
      setMsg("❌ " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const applyCustomSet = async (setId: number, setName: string) => {
    if (!confirm(`"${setName}" 세트를 적용하시겠습니까? 현재 설정이 덮어쓰여집니다.`))
      return;
    setSaving(true);
    try {
      await api.applyCustomSet(patientId, setId);
      await reload();
      setShowCustomPicker(false);
      setMsg(`✅ "${setName}" 적용 완료. 세부설정 변경 가능합니다.`);
    } catch (e: any) {
      setMsg("❌ " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const save = async () => {
    if (!cfg) return;
    setSaving(true);
    setMsg("");
    try {
      const cleanedTools = { ...(cfg.tools as any) };
      delete cleanedTools.__custom_questions__;
      const body = {
        pro_ctcae: cfg.pro_ctcae,
        hads_enabled: cfg.hads_enabled,
        hads_subscales: cfg.hads_subscales,
        frequency: cfg.frequency,
        cycle_trigger_days: cfg.cycle_trigger_days,
        thresholds: cfg.thresholds,
        tools: { ...cleanedTools, ...(customQs ? { __custom_questions__: customQs } : {}) },
        updated_by: "doctor",
      };
      const res = await api.updateProConfig(patientId, body);
      setCfg(res.config);
      setMsg("✅ 저장 완료");
    } catch (e: any) {
      setMsg("❌ " + e.message);
    } finally {
      setSaving(false);
    }
  };

  // ──────────── 요약 ────────────
  const enabledTools = TOOLS.filter((t) => toolEnabled(t.code));
  const totalQuestions =
    Object.values(cfg.pro_ctcae).reduce((s, a) => s + a.length, 0) +
    (cfg.hads_enabled ? cfg.hads_subscales.length * 7 : 0) +
    (toolEnabled("FACT-C") ? 36 : 0) +
    (toolEnabled("FACIT-F") ? 13 : 0) +
    (toolEnabled("PSQI") ? 19 : 0) +
    (customQs?.questions?.length ?? 0);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-5">
      {/* ───────────── Header ───────────── */}
      <header>
        <Link href="/" className="text-sm text-gray-500">← 모니터링 대시보드</Link>
        <h1 className="text-2xl font-bold mt-1">PRO 도구 커스터마이징</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          환자 {patientId} · 마지막 수정 {new Date(cfg.updated_at).toLocaleString("ko-KR")}{" "}
          · {cfg.updated_by}
        </p>
        <div className="flex gap-2 mt-3 flex-wrap">
          <button
            onClick={loadDefaults}
            className="text-xs px-3 py-1.5 bg-blue-100 text-blue-800 rounded-lg font-bold"
          >
            📚 ICD-10 기본값 불러오기
          </button>
          <button
            onClick={() => setShowCustomPicker((v) => !v)}
            className="text-xs px-3 py-1.5 bg-purple-100 text-purple-800 rounded-lg font-bold"
          >
            📋 커스텀 세트 적용 ({customSets.length})
          </button>
          <Link
            href="/tools/builder"
            className="text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-lg"
          >
            + 새 세트 만들기
          </Link>
          <Link
            href={`/patients/${patientId}/audit`}
            className="text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-lg"
          >
            📋 변경 이력
          </Link>
          <Link
            href={`/patients/${patientId}/preview`}
            className="text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-lg"
          >
            👁 환자 화면 미리보기
          </Link>
        </div>

        {showCustomPicker && (
          <div className="mt-3 bg-purple-50 border border-purple-200 rounded-xl p-3">
            <div className="text-xs font-bold text-purple-800 mb-2">
              커스텀 세트 적용 (적용 후 세부 변경 가능)
            </div>
            {customSets.length === 0 ? (
              <p className="text-xs text-gray-500">
                저장된 세트 없음.{" "}
                <Link href="/tools/builder" className="text-brand">+ 새로 만들기</Link>
              </p>
            ) : (
              <div className="space-y-1">
                {customSets.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => applyCustomSet(s.id, s.name)}
                    className="w-full text-left bg-white border border-gray-200 rounded-lg p-2 hover:border-brand"
                  >
                    <div className="font-semibold text-sm">{s.name}</div>
                    <div className="text-[10px] text-gray-500">
                      {s.description?.slice(0, 80) || "설명 없음"}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </header>

      {/* ───────────── 도구 카드 5종 ───────────── */}
      <section className="space-y-3">
        <h2 className="font-bold">표준 PRO 도구 ({enabledTools.length}/{TOOLS.length} 활성)</h2>

        {TOOLS.map((tool) => {
          const enabled = toolEnabled(tool.code);
          const required = toolRequired(tool.code);
          const freq = toolFrequency(tool.code);
          return (
            <div
              key={tool.code}
              className={`border rounded-2xl p-4 ${
                enabled
                  ? "bg-white border-brand/30"
                  : "bg-gray-50 border-gray-200"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => toggleTool(tool.code, e.target.checked)}
                    disabled={required && enabled}
                    className="w-4 h-4"
                  />
                  <span className="font-bold">{tool.code}</span>
                  {required && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full">
                      🔒 필수
                    </span>
                  )}
                  {!required && enabled && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                      선택
                    </span>
                  )}
                  <Link
                    href={`/tools/${encodeURIComponent(tool.code)}`}
                    target="_blank"
                    className="text-[10px] text-brand"
                  >
                    문항 미리보기 ↗
                  </Link>
                </div>
                <span className="text-xs text-gray-500">{tool.items}</span>
              </div>
              <p className="text-xs text-gray-600 mb-2">{tool.desc}</p>

              {enabled && (
                <div className="space-y-2 ml-6">
                  {/* 빈도 */}
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-xs text-gray-600 mr-1">빈도:</span>
                    {Object.entries(FREQ_LABELS).map(([v, l]) => (
                      <button
                        key={v}
                        onClick={() => setToolFreq(tool.code, v)}
                        className={`text-xs px-2 py-1 rounded ${
                          freq === v
                            ? "bg-brand text-white"
                            : "bg-white border border-gray-300"
                        }`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>

                  {/* PRO-CTCAE 매트릭스 */}
                  {tool.code === "PRO-CTCAE" && catalog && (
                    <div className="overflow-x-auto">
                      <table className="text-xs">
                        <thead>
                          <tr className="text-gray-500 border-b border-gray-200">
                            <th className="text-left py-1 pr-2">증상</th>
                            <th className="px-2">빈도</th>
                            <th className="px-2">강도</th>
                            <th className="px-2">일상 방해</th>
                          </tr>
                        </thead>
                        <tbody>
                          {catalog.pro_ctcae.map((c) => {
                            const cur = cfg.pro_ctcae[c.symptom] ?? [];
                            return (
                              <tr key={c.symptom} className="border-b border-gray-100">
                                <td className="py-1.5 pr-2 font-semibold">
                                  {SYMPTOM_LABELS[c.symptom] ?? c.symptom}
                                </td>
                                {(["freq", "severity", "interference"] as const).map(
                                  (attr) => {
                                    const supported = c.attributes.includes(attr);
                                    return (
                                      <td key={attr} className="text-center px-2">
                                        {supported ? (
                                          <input
                                            type="checkbox"
                                            checked={cur.includes(attr)}
                                            onChange={() => togglePCTCAEAttr(c.symptom, attr)}
                                          />
                                        ) : (
                                          <span className="text-gray-300">—</span>
                                        )}
                                      </td>
                                    );
                                  }
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* HADS 서브스케일 */}
                  {tool.code === "HADS" && (
                    <div className="flex gap-3">
                      {[["A", "불안 (HADS-A)"], ["D", "우울 (HADS-D)"]].map(([s, l]) => (
                        <label key={s} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={cfg.hads_subscales.includes(s)}
                            onChange={() => toggleHadsSub(s)}
                          />
                          {l} · 7문항
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </section>

      {/* ───────────── 커스텀 문항 (커스텀 세트 적용 시) ───────────── */}
      {customQs?.questions?.length > 0 && (
        <section className="bg-purple-50 border border-purple-200 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-bold">
              📋 커스텀 문항 ({customQs.questions.length})
            </h2>
            <span className="text-[10px] text-purple-700">
              from "{customQs.set_name}"
            </span>
          </div>
          <p className="text-xs text-gray-600 mb-3">
            적용된 커스텀 세트의 문항. 빌더에서 편집 가능.
          </p>
          <div className="space-y-2">
            {customQs.questions.map((q: any) => (
              <div
                key={q.code}
                className="bg-white border border-purple-200 rounded-lg p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-purple-800">{q.code}</span>
                  <span className="text-[10px] text-gray-500">{q.response_type}</span>
                </div>
                <p className="text-sm font-semibold mt-1">{q.question}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {(q.scale_labels ?? []).join(" / ")}
                </p>
              </div>
            ))}
          </div>
          <Link
            href={`/tools/builder?id=${customQs.set_id}`}
            className="inline-block mt-3 text-xs text-purple-700 font-bold"
          >
            세트 편집하기 →
          </Link>
        </section>
      )}

      {/* ───────────── 임계값 ───────────── */}
      <section className="bg-white border border-gray-200 rounded-2xl p-5">
        <h2 className="font-bold mb-1">Red/Yellow 임계값</h2>
        <p className="text-xs text-gray-500 mb-3">
          MCID 알림 발생 기준. 환자 특성 따라 조정 가능.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <ThresholdInput
            label="PRO-CTCAE RED 점수 (0~4)"
            value={cfg.thresholds.pro_ctcae_red}
            onChange={(v) => setThreshold("pro_ctcae_red", v)}
            min={1} max={4}
          />
          <ThresholdInput
            label="PRO-CTCAE 지속 일수"
            value={cfg.thresholds.pro_ctcae_persist_days}
            onChange={(v) => setThreshold("pro_ctcae_persist_days", v)}
            min={1} max={7}
          />
          <ThresholdInput
            label="HADS YELLOW (0~21)"
            value={cfg.thresholds.hads_yellow}
            onChange={(v) => setThreshold("hads_yellow", v)}
            min={0} max={21}
          />
          <ThresholdInput
            label="HADS RED (0~21)"
            value={cfg.thresholds.hads_red}
            onChange={(v) => setThreshold("hads_red", v)}
            min={0} max={21}
          />
        </div>
      </section>

      {/* ───────────── Sticky 저장바 ───────────── */}
      <section className="bg-brand-soft border border-brand/30 rounded-2xl p-4 sticky bottom-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 text-sm">
            <span className="font-bold text-brand-deep">
              총 {totalQuestions}문항
            </span>
            <span className="text-gray-600 ml-2 text-xs">
              · 활성 도구 {enabledTools.length}개
              {customQs?.questions?.length > 0 && (
                <> · 커스텀 {customQs.questions.length}개</>
              )}
            </span>
            {msg && <div className="text-xs mt-1">{msg}</div>}
          </div>
          <button
            onClick={save}
            disabled={saving}
            className="px-6 py-2 bg-brand text-white rounded-xl text-sm font-bold disabled:bg-gray-300"
          >
            {saving ? "저장 중..." : "💾 저장"}
          </button>
        </div>
      </section>
    </div>
  );
}

function ThresholdInput({
  label, value, onChange, min, max,
}: {
  label: string; value: number; onChange: (v: number) => void;
  min: number; max: number;
}) {
  return (
    <div>
      <label className="text-xs text-gray-600 mb-1 block">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value) || min)}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
      />
    </div>
  );
}
