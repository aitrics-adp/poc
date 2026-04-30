"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api, { QuickCategory, DynamicProForm } from "@/lib/api";

const HADS_SCALE = ["전혀 없었다", "때때로", "자주", "대부분"];

export default function QuickModePage() {
  const router = useRouter();
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const sessionId = parseInt(params.get("session_id") || "0");

  const [step, setStep] = useState<"screen" | "detail">("screen");
  const [categories, setCategories] = useState<QuickCategory[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [form, setForm] = useState<DynamicProForm | null>(null);
  const [responses, setResponses] = useState<Record<string, number>>({});

  useEffect(() => {
    api.quickCategories().then(setCategories);
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const goDetail = async () => {
    const f = await api.submitQuickScreening(sessionId, Array.from(selected));
    setForm(f);
    if (f.pro_ctcae.length === 0 && f.hads.length === 0) {
      // 양성 0건 — 즉시 완료 (No-Change에 준함)
      await api.submitResponses(sessionId, []);
      await api.completeSession(sessionId);
      router.push(`/result?patient_id=${patientId}`);
      return;
    }
    setStep("detail");
  };

  const submitDetail = async () => {
    if (!form) return;
    const items = [
      ...form.pro_ctcae.map((q) => ({
        tool_code: "PRO-CTCAE",
        item_code: q.symptom,
        attribute: q.attribute,
        raw_value: responses[`ctcae:${q.symptom}:${q.attribute}`] ?? 0,
      })),
      ...form.hads.map((q) => ({
        tool_code: "HADS",
        item_code: q.code,
        raw_value: responses[`hads:${q.code}`] ?? 0,
      })),
    ];
    await api.submitResponses(sessionId, items);
    await api.completeSession(sessionId);
    router.push(`/result?patient_id=${patientId}`);
  };

  // ---------------------- Step 1: 카테고리 스크리닝 ----------------------
  if (step === "screen") {
    return (
      <div className="p-6 space-y-4 max-w-md mx-auto">
        <header>
          <button onClick={() => router.back()} className="text-sm text-gray-500">
            ← 뒤로
          </button>
          <h1 className="text-xl font-bold mt-1">Quick 스크리닝</h1>
          <p className="text-xs text-gray-500 mt-1">
            지난 며칠 사이 불편한 영역만 골라주세요. 없으면 비워둬도 OK.
          </p>
        </header>
        <div className="space-y-2">
          {categories.map((c) => {
            const on = selected.has(c.id);
            return (
              <button
                key={c.id}
                onClick={() => toggle(c.id)}
                className={`w-full p-4 rounded-xl border text-left ${
                  on
                    ? "bg-brand-soft border-brand"
                    : "bg-white border-gray-200"
                }`}
              >
                <div className="font-bold flex items-center justify-between">
                  <span>{c.label}</span>
                  <span className="text-xs">{on ? "✓ 있음" : "없음"}</span>
                </div>
              </button>
            );
          })}
        </div>
        <div className="fixed bottom-4 left-0 right-0 px-6 max-w-md mx-auto">
          <button
            onClick={goDetail}
            className="w-full py-3 bg-brand text-white rounded-xl font-bold"
          >
            {selected.size === 0 ? "변화 없음으로 완료" : `${selected.size}개 영역 세부 문항으로`}
          </button>
        </div>
      </div>
    );
  }

  // ---------------------- Step 2: 세부 문항 ----------------------
  if (!form) return <div className="p-8 text-center text-gray-400">로딩...</div>;

  const total = form.pro_ctcae.length + form.hads.length;
  const answered = Object.keys(responses).length;

  return (
    <div className="p-6 space-y-4 pb-24 max-w-md mx-auto">
      <header>
        <h1 className="text-lg font-bold">세부 문항 ({answered}/{total})</h1>
      </header>
      {form.pro_ctcae.map((q) => {
        const key = `ctcae:${q.symptom}:${q.attribute}`;
        return (
          <div key={key} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="text-sm font-semibold mb-3">{q.question}</div>
            <div className="grid grid-cols-5 gap-1">
              {q.scale_labels.map((label, idx) => (
                <button
                  key={idx}
                  onClick={() => setResponses({ ...responses, [key]: idx })}
                  className={`px-1 py-2 rounded-lg text-xs font-medium ${
                    responses[key] === idx ? "bg-brand text-white" : "bg-gray-100"
                  }`}
                >
                  <div className="text-base font-bold">{idx}</div>
                  <div>{label}</div>
                </button>
              ))}
            </div>
          </div>
        );
      })}
      {form.hads.map((q, i) => {
        const key = `hads:${q.code}`;
        return (
          <div key={key} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="text-sm font-semibold mb-3">{i + 1}. {q.question}</div>
            <div className="grid grid-cols-4 gap-1">
              {HADS_SCALE.map((label, idx) => (
                <button
                  key={idx}
                  onClick={() => setResponses({ ...responses, [key]: idx })}
                  className={`px-2 py-2 rounded-lg text-xs ${
                    responses[key] === idx ? "bg-brand text-white" : "bg-gray-100"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        );
      })}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white border-t max-w-md mx-auto">
        <button
          onClick={submitDetail}
          disabled={answered < total}
          className="w-full py-3 bg-brand text-white rounded-xl font-bold disabled:bg-gray-300"
        >
          {answered < total ? `${total - answered}개 더` : "제출"}
        </button>
      </div>
    </div>
  );
}
