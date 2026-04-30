"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";

const SCALES: Record<string, string[]> = {
  likert_5: ["없음", "약함", "보통", "심함", "매우 심함"],
  likert_4: ["전혀 없었다", "때때로", "자주", "대부분"],
  nrs_10: ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
  yes_no: ["아니오", "예"],
  text: [],
};
const SCALE_LABELS: Record<string, string> = {
  likert_5: "5단계 (없음~매우 심함)",
  likert_4: "4단계 (전혀~대부분)",
  nrs_10: "NRS 0~10",
  yes_no: "예/아니오",
  text: "자유 텍스트",
};

const TOOL_CODES = ["PRO-CTCAE", "HADS", "FACT-C", "FACIT-F", "PSQI"];
const FREQ_OPTIONS = [
  ["daily", "매일"],
  ["every_3_days", "3일마다"],
  ["weekly", "주 1회"],
  ["monthly", "월 1회"],
];

const PRO_CTCAE_SYMPTOMS = [
  ["fatigue", "피로"],
  ["appetite", "식욕부진"],
  ["nausea", "오심·구토"],
  ["diarrhea", "설사"],
  ["neuropathy", "손발 저림"],
];
const HADS_SUBS = [["A", "불안"], ["D", "우울"]];

export default function BuilderPage() {
  const router = useRouter();
  const params = useSearchParams();
  const editId = params.get("id");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icd, setIcd] = useState("");
  const [tools, setTools] = useState<Record<string, any>>({
    "PRO-CTCAE": { enabled: false, pro_ctcae: {}, frequency: "daily" },
    HADS: { enabled: false, subscales: ["A", "D"], frequency: "monthly" },
    "FACT-C": { enabled: false, frequency: "monthly" },
    "FACIT-F": { enabled: false, frequency: "weekly" },
    PSQI: { enabled: false, frequency: "monthly" },
  });
  const [questions, setQuestions] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (editId) {
      api.customSet(parseInt(editId)).then((s) => {
        setName(s.name);
        setDescription(s.description ?? "");
        setIcd(s.target_icd10 ?? "");
        setTools((prev) => ({ ...prev, ...s.tools }));
        setQuestions(s.custom_questions ?? []);
      });
    }
  }, [editId]);

  const updateTool = (code: string, patch: any) =>
    setTools((p) => ({ ...p, [code]: { ...p[code], ...patch } }));

  const togglePCTCAEAttr = (sym: string, attr: string) => {
    setTools((p) => {
      const cur = p["PRO-CTCAE"].pro_ctcae?.[sym] ?? [];
      const next = cur.includes(attr)
        ? cur.filter((x: string) => x !== attr)
        : [...cur, attr];
      const newMap = { ...(p["PRO-CTCAE"].pro_ctcae ?? {}) };
      if (next.length > 0) newMap[sym] = next;
      else delete newMap[sym];
      return { ...p, "PRO-CTCAE": { ...p["PRO-CTCAE"], pro_ctcae: newMap } };
    });
  };

  const toggleHADSSub = (sub: string) =>
    setTools((p) => {
      const cur = p.HADS.subscales ?? [];
      const next = cur.includes(sub)
        ? cur.filter((x: string) => x !== sub)
        : [...cur, sub];
      return { ...p, HADS: { ...p.HADS, subscales: next } };
    });

  const addQuestion = () => {
    const code = `CUST-${questions.length + 1}`;
    setQuestions([
      ...questions,
      { code, question: "", response_type: "likert_5",
        scale_labels: SCALES.likert_5 },
    ]);
  };

  const updateQuestion = (i: number, patch: any) => {
    setQuestions((qs) => qs.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
  };

  const removeQuestion = (i: number) =>
    setQuestions((qs) => qs.filter((_, idx) => idx !== i));

  const save = async () => {
    if (!name.trim()) {
      setMsg("⚠️ 세트 이름은 필수");
      return;
    }
    setSaving(true);
    setMsg("");
    try {
      const body = {
        name,
        description,
        target_icd10: icd,
        tools,
        custom_questions: questions,
        created_by: "doctor",
      };
      if (editId) {
        await api.updateCustomSet(parseInt(editId), body);
      } else {
        await api.createCustomSet(body);
      }
      setMsg("✅ 저장 완료");
      setTimeout(() => router.push("/tools"), 800);
    } catch (e: any) {
      setMsg("❌ " + e.message);
    } finally {
      setSaving(false);
    }
  };

  const enabledCount = Object.values(tools).filter((t: any) => t.enabled).length;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-5">
      <header>
        <Link href="/tools" className="text-sm text-gray-500">← 라이브러리</Link>
        <h1 className="text-2xl font-bold mt-1">
          {editId ? "커스텀 세트 편집" : "커스텀 PRO 세트 만들기"}
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">
          기본 도구 ON/OFF + 커스텀 질문 추가. 저장 후 환자에게 적용 가능.
        </p>
      </header>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 space-y-3">
        <h2 className="font-bold">기본 정보</h2>
        <div>
          <label className="text-xs text-gray-600 mb-1 block">세트 이름 *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            placeholder="예: FOLFOX 신경병증 추적 세트"
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 mb-1 block">설명</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            rows={2}
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 mb-1 block">대상 ICD-10 (선택)</label>
          <input
            value={icd}
            onChange={(e) => setIcd(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            placeholder="예: C18 (대장암)"
          />
        </div>
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5">
        <h2 className="font-bold mb-3">표준 도구 포함 ({enabledCount}/{TOOL_CODES.length})</h2>
        <div className="space-y-3">
          {TOOL_CODES.map((code) => {
            const t = tools[code];
            return (
              <div
                key={code}
                className={`p-4 rounded-xl border ${
                  t.enabled ? "bg-brand-soft border-brand/30" : "bg-gray-50 border-gray-200"
                }`}
              >
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={t.enabled}
                    onChange={(e) => updateTool(code, { enabled: e.target.checked })}
                  />
                  <span className="font-bold">{code}</span>
                  <Link
                    href={`/tools/${encodeURIComponent(code)}`}
                    target="_blank"
                    className="text-[10px] text-brand"
                  >
                    문항 미리보기 ↗
                  </Link>
                </label>

                {t.enabled && (
                  <div className="mt-3 ml-6 space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-600">빈도:</span>
                      {FREQ_OPTIONS.map(([v, l]) => (
                        <button
                          key={v}
                          onClick={() => updateTool(code, { frequency: v })}
                          className={`text-xs px-2 py-1 rounded ${
                            t.frequency === v
                              ? "bg-brand text-white"
                              : "bg-white border border-gray-300"
                          }`}
                        >
                          {l}
                        </button>
                      ))}
                    </div>

                    {code === "PRO-CTCAE" && (
                      <div>
                        <div className="text-xs text-gray-600 mb-1">증상 × 속성:</div>
                        <table className="text-xs">
                          <thead>
                            <tr>
                              <th className="text-left py-1 pr-2"></th>
                              <th className="px-2">빈도</th>
                              <th className="px-2">강도</th>
                              <th className="px-2">일상</th>
                            </tr>
                          </thead>
                          <tbody>
                            {PRO_CTCAE_SYMPTOMS.map(([sym, label]) => {
                              const cur = t.pro_ctcae?.[sym] ?? [];
                              return (
                                <tr key={sym}>
                                  <td className="py-1 pr-2">{label}</td>
                                  {["freq", "severity", "interference"].map((a) => (
                                    <td key={a} className="text-center px-2">
                                      <input
                                        type="checkbox"
                                        checked={cur.includes(a)}
                                        onChange={() => togglePCTCAEAttr(sym, a)}
                                      />
                                    </td>
                                  ))}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {code === "HADS" && (
                      <div className="flex gap-3">
                        {HADS_SUBS.map(([sub, label]) => (
                          <label key={sub} className="flex items-center gap-1 text-xs">
                            <input
                              type="checkbox"
                              checked={(t.subscales ?? []).includes(sub)}
                              onChange={() => toggleHADSSub(sub)}
                            />
                            HADS-{sub} {label}
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold">커스텀 질문 ({questions.length})</h2>
          <button
            onClick={addQuestion}
            className="text-xs px-3 py-1.5 bg-purple-100 text-purple-800 rounded-lg font-bold"
          >
            + 질문 추가
          </button>
        </div>
        {questions.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">
            특수 증상이나 라이프스타일 질문을 직접 만드실 수 있어요.
          </p>
        ) : (
          <div className="space-y-3">
            {questions.map((q, i) => (
              <div
                key={i}
                className="p-3 border border-purple-200 rounded-xl bg-purple-50/30"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-purple-800">{q.code}</span>
                  <button
                    onClick={() => removeQuestion(i)}
                    className="text-xs text-red-600"
                  >
                    삭제
                  </button>
                </div>
                <input
                  value={q.question}
                  onChange={(e) => updateQuestion(i, { question: e.target.value })}
                  placeholder="질문 내용"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-2"
                />
                <div className="flex flex-wrap gap-1 mb-2">
                  {Object.entries(SCALE_LABELS).map(([type, label]) => (
                    <button
                      key={type}
                      onClick={() =>
                        updateQuestion(i, {
                          response_type: type,
                          scale_labels: SCALES[type],
                        })
                      }
                      className={`text-xs px-2 py-1 rounded ${
                        q.response_type === type
                          ? "bg-purple-600 text-white"
                          : "bg-white border border-gray-300"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {q.scale_labels?.length > 0 && (
                  <div className="text-xs text-gray-500 mt-1">
                    옵션: {q.scale_labels.join(" / ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="sticky bottom-4">
        <div className="bg-brand-soft border border-brand/30 rounded-2xl p-4 flex items-center gap-4">
          <div className="flex-1 text-sm">
            <div className="font-bold text-brand-deep">
              {name || "이름 미정"}
            </div>
            <div className="text-xs text-gray-600">
              표준 {enabledCount}개 + 커스텀 {questions.length}개
            </div>
            {msg && <div className="text-xs mt-1">{msg}</div>}
          </div>
          <button
            onClick={save}
            disabled={saving || !name.trim()}
            className="px-6 py-2 bg-brand text-white rounded-xl text-sm font-bold disabled:bg-gray-300"
          >
            {saving ? "저장 중..." : editId ? "💾 업데이트" : "💾 새 세트 저장"}
          </button>
        </div>
      </section>
    </div>
  );
}
