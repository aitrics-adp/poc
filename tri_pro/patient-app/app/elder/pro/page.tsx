"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api, { DynamicProForm } from "@/lib/api";

/**
 * 어르신 모드 PRO 응답 — One-Question-One-Screen.
 *
 * 모드 등가성 (FN-MODE-007):
 *   - 환자 PRO Config (필수+선택 도구)을 일반 모드와 동일하게 따라감
 *   - PRO-CTCAE: 5단계 얼굴척도 → raw_value 0..4
 *   - HADS:      4단계 얼굴척도 → raw_value 0..3
 *   - 결정론 채점 엔진은 ui_mode를 보지 않으므로 동일 입력 → 동일 출력 보장
 */

const SYMPTOM_LABEL: Record<string, string> = {
  fatigue: "피곤함", appetite: "식욕부진", nausea: "속 메스꺼움",
  diarrhea: "설사", neuropathy: "손발 저림",
};
const ATTR_LABEL: Record<string, string> = {
  freq: "얼마나 자주", severity: "얼마나 심하게", interference: "일상생활 지장",
};

// PRO-CTCAE: 5단계 얼굴
const FACES_5 = [
  { emoji: "😀", label: "전혀 안 그래요", value: 0, bg: "bg-green-100 border-green-300" },
  { emoji: "🙂", label: "조금요",         value: 1, bg: "bg-lime-100 border-lime-300" },
  { emoji: "😐", label: "보통이에요",     value: 2, bg: "bg-yellow-100 border-yellow-300" },
  { emoji: "😣", label: "많이 그래요",     value: 3, bg: "bg-orange-100 border-orange-300" },
  { emoji: "😭", label: "정말 너무 심해요", value: 4, bg: "bg-red-100 border-red-300" },
];

// HADS: 4단계 얼굴
const FACES_4 = [
  { emoji: "😀", label: "전혀 없었어요",   value: 0, bg: "bg-green-100 border-green-300" },
  { emoji: "🙂", label: "가끔이요",       value: 1, bg: "bg-yellow-100 border-yellow-300" },
  { emoji: "😣", label: "자주 있었어요",   value: 2, bg: "bg-orange-100 border-orange-300" },
  { emoji: "😭", label: "거의 매일이요",   value: 3, bg: "bg-red-100 border-red-300" },
];

type Q = {
  tool_code: "PRO-CTCAE" | "HADS";
  item_code: string;
  attribute?: string;
  text: string;
  faces: typeof FACES_5;
};

function buildQuestions(form: DynamicProForm): Q[] {
  const qs: Q[] = [];
  for (const q of form.pro_ctcae) {
    const sym = SYMPTOM_LABEL[q.symptom] ?? q.symptom;
    const attr = ATTR_LABEL[q.attribute] ?? "";
    qs.push({
      tool_code: "PRO-CTCAE",
      item_code: q.symptom,
      attribute: q.attribute,
      text: `${sym} — ${attr} 어땠어요?`,
      faces: FACES_5,
    });
  }
  for (const q of form.hads) {
    qs.push({
      tool_code: "HADS",
      item_code: q.code,
      text: q.question,
      faces: FACES_4,
    });
  }
  return qs;
}

export default function ElderPro() {
  const router = useRouter();
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<Q[]>([]);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.proForm(patientId),
      api.startSession(patientId, "elder"),
    ])
      .then(([form, s]) => {
        const qs = buildQuestions(form);
        if (qs.length === 0) {
          setError("담당의가 PRO 항목을 아직 설정하지 않았습니다.");
          return;
        }
        setQuestions(qs);
        setSessionId(s.id);
      })
      .catch((e) => setError(e.message));
  }, [patientId]);

  if (error)
    return <div className="p-8 text-elder text-center text-red-600">{error}</div>;
  if (questions.length === 0)
    return <div className="p-8 text-elder text-center text-gray-400">준비 중...</div>;

  const current = questions[step];
  const isLast = step === questions.length - 1;

  const choose = async (val: number) => {
    const newAnswers = { ...answers, [step]: val };
    setAnswers(newAnswers);

    if (!isLast) {
      setTimeout(() => setStep(step + 1), 250);
      return;
    }
    if (!sessionId) return;
    const responses = questions.map((q, i) => ({
      tool_code: q.tool_code,
      item_code: q.item_code,
      attribute: q.attribute,
      raw_value: newAnswers[i] ?? 0,
    }));
    await api.submitResponses(sessionId, responses);
    await api.completeSession(sessionId);
    router.push(`/elder/result?patient_id=${patientId}`);
  };

  return (
    <div className="p-6 min-h-screen flex flex-col">
      <header className="flex items-center justify-between mb-6">
        <button
          onClick={() => (step > 0 ? setStep(step - 1) : router.back())}
          className="text-base text-gray-500"
        >
          ← 뒤로
        </button>
        <span className="text-base text-gray-500">
          {step + 1} / {questions.length}
        </span>
      </header>

      <div className="h-3 bg-gray-200 rounded-full mb-8">
        <div
          className="h-3 bg-brand rounded-full transition-all"
          style={{ width: `${((step + 1) / questions.length) * 100}%` }}
        />
      </div>

      <div className="flex-1">
        <div className="text-base text-center text-gray-500 mb-2">
          {current.tool_code === "HADS" ? "💚 마음 상태" : "🩺 몸 상태"}
        </div>
        <h1 className="text-elder-lg font-bold text-center mb-8 leading-relaxed">
          {current.text}
        </h1>

        <div className="space-y-3">
          {current.faces.map((f) => {
            const selected = answers[step] === f.value;
            return (
              <button
                key={f.value}
                onClick={() => choose(f.value)}
                className={`w-full py-4 px-5 border-2 rounded-2xl flex items-center gap-4 transition-all ${
                  selected
                    ? "bg-brand text-white border-brand"
                    : `${f.bg} text-gray-800`
                }`}
              >
                <span className="text-5xl">{f.emoji}</span>
                <span className="text-elder font-bold flex-1 text-left">
                  {f.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <p className="mt-6 text-base text-center text-gray-500">
        {isLast ? "마지막 질문이에요" : "잘 하고 계세요!"}
      </p>
    </div>
  );
}
