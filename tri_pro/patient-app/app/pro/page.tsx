"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api, { DynamicProForm } from "@/lib/api";

type ResponseItem = {
  tool_code: string;
  item_code: string;
  attribute?: string;
  raw_value: number;
};

const SYMPTOM_LABELS: Record<string, string> = {
  fatigue: "피로",
  appetite: "식욕부진",
  nausea: "오심·구토",
  diarrhea: "설사",
  neuropathy: "손발 저림 (신경병증)",
};

const HADS_SCALE = ["전혀 없었다", "때때로", "자주", "대부분"];

export default function ProResponsePage() {
  const router = useRouter();
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";

  const [form, setForm] = useState<DynamicProForm | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [responses, setResponses] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    // 환자별 동적 폼 로드
    api.proForm(patientId)
      .then(setForm)
      .catch((e) => setError(`폼 로드 실패: ${e.message}`));
    api.startSession(patientId, "general").then((s) => setSessionId(s.id));
  }, [patientId]);

  if (error) return <div className="p-8 text-center text-red-600">{error}</div>;
  if (!form) return <div className="p-8 text-center text-gray-400">폼 준비 중...</div>;

  const totalQuestions = form.pro_ctcae.length + form.hads.length;
  const answered = Object.keys(responses).length;
  const progress = totalQuestions
    ? Math.round((answered / totalQuestions) * 100)
    : 0;

  const setAnswer = (key: string, val: number) =>
    setResponses((prev) => ({ ...prev, [key]: val }));

  const handleSubmit = async () => {
    if (!sessionId) return;
    if (answered < totalQuestions) {
      alert(`아직 ${totalQuestions - answered}개 항목이 남았어요`);
      return;
    }
    setSubmitting(true);
    const items: ResponseItem[] = [];
    for (const q of form.pro_ctcae) {
      const k = `ctcae:${q.symptom}:${q.attribute}`;
      items.push({
        tool_code: "PRO-CTCAE",
        item_code: q.symptom,
        attribute: q.attribute,
        raw_value: responses[k],
      });
    }
    for (const q of form.hads) {
      items.push({
        tool_code: "HADS",
        item_code: q.code,
        raw_value: responses[`hads:${q.code}`],
      });
    }
    await api.submitResponses(sessionId, items);
    await api.completeSession(sessionId);
    router.push(`/result?patient_id=${patientId}`);
  };

  // 증상별로 그룹핑 (같은 증상의 freq/severity/interference를 한 카드로)
  const ctcaeBySymptom: Record<string, typeof form.pro_ctcae> = {};
  for (const q of form.pro_ctcae) {
    (ctcaeBySymptom[q.symptom] ||= []).push(q);
  }

  return (
    <div className="p-6 space-y-6 pb-24">
      <header className="sticky top-0 bg-white -mx-6 px-6 py-4 border-b border-gray-200 z-10">
        <div className="flex items-center justify-between mb-2">
          <button
            onClick={() => router.back()}
            className="text-sm text-gray-500"
          >
            ← 뒤로
          </button>
          <span className="text-xs text-gray-500">
            {answered}/{totalQuestions} · 주기 {form.frequency}
          </span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full">
          <div
            className="h-2 bg-brand rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </header>

      {form.pro_ctcae.length > 0 && (
        <section>
          <h2 className="text-lg font-bold mb-3">PRO-CTCAE · 부작용</h2>
          <div className="space-y-4">
            {Object.entries(ctcaeBySymptom).map(([symptom, qs]) => (
              <div
                key={symptom}
                className="bg-white border border-gray-200 rounded-xl p-4"
              >
                <div className="text-sm font-bold text-brand-deep mb-3">
                  {SYMPTOM_LABELS[symptom] ?? symptom}
                </div>
                <div className="space-y-3">
                  {qs.map((q) => {
                    const key = `ctcae:${q.symptom}:${q.attribute}`;
                    return (
                      <div key={key}>
                        <div className="text-sm mb-2">{q.question}</div>
                        <div className="grid grid-cols-5 gap-1">
                          {q.scale_labels.map((label, idx) => {
                            const selected = responses[key] === idx;
                            return (
                              <button
                                key={idx}
                                onClick={() => setAnswer(key, idx)}
                                className={`px-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                                  selected
                                    ? "bg-brand text-white"
                                    : "bg-gray-100 text-gray-700"
                                }`}
                              >
                                <div className="text-base font-bold">{idx}</div>
                                <div>{label}</div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {form.hads.length > 0 && (
        <section>
          <h2 className="text-lg font-bold mb-3">HADS · 불안·우울</h2>
          <div className="space-y-3">
            {form.hads.map((q, i) => {
              const key = `hads:${q.code}`;
              return (
                <div
                  key={key}
                  className="bg-white border border-gray-200 rounded-xl p-4"
                >
                  <div className="text-sm font-semibold mb-3">
                    {i + 1}. {q.question}
                  </div>
                  <div className="grid grid-cols-4 gap-1">
                    {HADS_SCALE.map((label, idx) => {
                      const selected = responses[key] === idx;
                      return (
                        <button
                          key={idx}
                          onClick={() => setAnswer(key, idx)}
                          className={`px-2 py-2 rounded-lg text-xs font-medium ${
                            selected
                              ? "bg-brand text-white"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {totalQuestions === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 text-sm text-yellow-900">
          담당의가 PRO 항목을 아직 설정하지 않았습니다.
        </div>
      )}

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 max-w-md mx-auto">
        <button
          onClick={handleSubmit}
          disabled={submitting || answered < totalQuestions || totalQuestions === 0}
          className="w-full py-3 rounded-xl font-bold text-white disabled:bg-gray-300 bg-brand"
        >
          {submitting
            ? "제출 중..."
            : answered < totalQuestions
            ? `${totalQuestions - answered}개 더 답해주세요`
            : "제출하고 결과 보기"}
        </button>
      </div>
    </div>
  );
}
