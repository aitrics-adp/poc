"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import api from "@/lib/api";

const SYMPTOM_LABEL: Record<string, string> = {
  fatigue: "피로", appetite: "식욕부진", nausea: "오심·구토",
  diarrhea: "설사", neuropathy: "손발 저림 (신경병증)",
};
const ATTR_LABEL: Record<string, string> = {
  freq: "빈도", severity: "강도", interference: "일상 방해",
};

export default function ToolDetailPage() {
  const params = useParams<{ code: string }>();
  const code = decodeURIComponent(params.code);
  const [detail, setDetail] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.toolDetail(code).then(setDetail).catch((e) => setErr(e.message));
  }, [code]);

  if (err)
    return (
      <div className="p-8 text-center text-red-600">
        ❌ {err}
        <div className="mt-4">
          <Link href="/tools" className="text-brand">← 라이브러리로</Link>
        </div>
      </div>
    );
  if (!detail) return <div className="p-8 text-center text-gray-400">로딩...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-5">
      <header>
        <Link href="/tools" className="text-sm text-gray-500">← 라이브러리</Link>
        <div className="flex items-center gap-2 mt-1">
          <h1 className="text-2xl font-bold">{detail.name}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800">
            Grade {detail.evidence_grade}
          </span>
        </div>
        <p className="text-sm text-gray-700 mt-1">{detail.domain}</p>
        <p className="text-xs text-gray-500 mt-0.5">📜 {detail.license}</p>
      </header>

      <section className="bg-brand-soft border border-brand/30 rounded-2xl p-4">
        <div className="text-xs font-bold text-brand uppercase tracking-wider mb-1">
          채점 방식
        </div>
        <p className="text-sm">{detail.scoring_note}</p>
      </section>

      <section>
        <h2 className="font-bold mb-3">실제 문항 ({detail.items.length}개)</h2>
        <div className="space-y-2">
          {detail.items.map((it: any, i: number) => (
            <ItemCard key={it.code ?? i} item={it} index={i + 1} toolCode={code} />
          ))}
        </div>
      </section>
    </div>
  );
}

function ItemCard({ item, index, toolCode }: any) {
  const labels: string[] = item.scale_labels ?? item.scale ?? [];

  if (toolCode.toUpperCase() === "PRO-CTCAE") {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-gray-500">
            {SYMPTOM_LABEL[item.symptom] ?? item.symptom} · {ATTR_LABEL[item.attribute]}
          </div>
          <span className="text-[10px] text-gray-400">#{index}</span>
        </div>
        <div className="text-sm font-semibold mb-3">{item.question}</div>
        <div className="grid grid-cols-5 gap-1">
          {labels.map((l: string, idx: number) => (
            <div
              key={idx}
              className="text-center p-2 bg-gray-50 rounded-lg text-xs"
            >
              <div className="font-bold text-base">{idx}</div>
              <div className="text-gray-600">{l}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (toolCode.toUpperCase() === "PSQI" && item.type) {
    // PSQI는 type별 다른 입력
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-gray-500">
            {item.code} · {item.type === "minutes" ? "분 입력"
              : item.type === "hours" ? "시간 입력" : "선택"}
          </div>
          <span className="text-[10px] text-gray-400">#{index}</span>
        </div>
        <div className="text-sm font-semibold mb-3">{item.question}</div>
        {item.scale ? (
          <div className="grid grid-cols-4 gap-1">
            {item.scale.map((l: string, idx: number) => (
              <div key={idx} className="text-center p-2 bg-gray-50 rounded-lg text-xs">
                <div className="font-bold">{idx}</div>
                <div className="text-gray-600">{l}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-gray-400 italic">
            (숫자 입력 — 예: {item.type === "minutes" ? "10, 30, 60" : "5, 7, 8"})
          </div>
        )}
      </div>
    );
  }

  // HADS / FACT-C / FACIT-F: 공통 형식
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs text-gray-500 flex items-center gap-2">
          <span>{item.code}</span>
          {item.subscale && (
            <span className="px-1.5 py-0.5 bg-gray-100 rounded text-[10px]">
              {item.subscale}
            </span>
          )}
          {item.reverse && (
            <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-800 rounded text-[10px]">
              역채점
            </span>
          )}
        </div>
        <span className="text-[10px] text-gray-400">#{index}</span>
      </div>
      <div className="text-sm font-semibold mb-3">{item.question}</div>
      <div className={`grid gap-1 ${labels.length === 4 ? "grid-cols-4" : "grid-cols-5"}`}>
        {labels.map((l: string, idx: number) => (
          <div key={idx} className="text-center p-2 bg-gray-50 rounded-lg text-xs">
            <div className="font-bold text-base">{idx}</div>
            <div className="text-gray-600">{l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
