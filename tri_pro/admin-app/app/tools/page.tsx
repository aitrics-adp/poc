"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import api, { ToolLibraryItem } from "@/lib/api";

export default function ToolLibraryPage() {
  const [tools, setTools] = useState<ToolLibraryItem[]>([]);
  const [customSets, setCustomSets] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (query?: string) => {
    setLoading(true);
    const [ts, cs] = await Promise.all([
      api.toolLibrary(query),
      api.customSets().catch(() => []),
    ]);
    setTools(ts);
    setCustomSets(cs);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`"${name}" 세트를 삭제하시겠어요?`)) return;
    await api.deleteCustomSet(id);
    load();
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">PRO 도구 라이브러리</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          기본 도구 5종 + 의사가 만든 커스텀 세트 관리
        </p>
      </header>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold">표준 PRO 도구</h2>
        </div>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(q)}
            placeholder="도구명·영역 검색"
            className="flex-1 px-4 py-2 border border-gray-300 rounded-xl text-sm"
          />
          <button
            onClick={() => load(q)}
            className="px-4 py-2 bg-brand text-white rounded-xl text-sm font-bold"
          >
            검색
          </button>
        </div>
        {loading ? (
          <div className="text-center text-gray-400 py-10">로딩...</div>
        ) : tools.length === 0 ? (
          <div className="text-center text-gray-400 py-10">검색 결과 없음</div>
        ) : (
          <div className="space-y-2">
            {tools.map((t) => (
              <Link
                key={t.tool_code}
                href={`/tools/${encodeURIComponent(t.tool_code)}`}
                className="block bg-white border border-gray-200 rounded-2xl p-5 hover:border-brand/50 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-lg">{t.name}</h3>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800">
                        Grade {t.evidence_grade}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{t.domain}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>📋 {t.items}문항</span>
                      <span>⏱ {t.duration_min}분</span>
                      <span>📅 {t.default_frequency}</span>
                      <span>📜 {t.license}</span>
                    </div>
                  </div>
                  <span className="text-brand text-xl">→</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold">커스텀 PRO 세트 ({customSets.length})</h2>
          <Link
            href="/tools/builder"
            className="px-3 py-1.5 bg-brand text-white rounded-lg text-xs font-bold"
          >
            + 새 세트 만들기
          </Link>
        </div>
        {customSets.length === 0 ? (
          <div className="bg-gray-50 rounded-xl p-8 text-center">
            <p className="text-sm text-gray-500">
              아직 만든 커스텀 세트가 없습니다.
            </p>
            <Link
              href="/tools/builder"
              className="inline-block mt-2 text-brand text-sm font-bold"
            >
              + 첫 세트 만들기
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {customSets.map((s) => (
              <div
                key={s.id}
                className="bg-white border border-gray-200 rounded-2xl p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <Link
                      href={`/tools/builder?id=${s.id}`}
                      className="font-bold text-lg hover:text-brand"
                    >
                      {s.name}
                    </Link>
                    {s.target_icd10 && (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                        {s.target_icd10}
                      </span>
                    )}
                    <p className="text-sm text-gray-700 mt-1">{s.description}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {Object.entries(s.tools || {})
                        .filter(([_, v]: any) => v.enabled)
                        .map(([code]) => (
                          <span
                            key={code}
                            className="text-[10px] px-2 py-0.5 bg-gray-100 rounded-full"
                          >
                            {code}
                          </span>
                        ))}
                      {(s.custom_questions || []).length > 0 && (
                        <span className="text-[10px] px-2 py-0.5 bg-purple-100 text-purple-800 rounded-full">
                          + 커스텀 문항 {s.custom_questions.length}개
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(s.id, s.name)}
                    className="text-xs text-red-600"
                  >
                    삭제
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
