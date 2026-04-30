"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import api, { DashboardRow } from "@/lib/api";

const LEVEL_STYLE = {
  critical: { color: "bg-red-50 border-red-300 text-red-900",
              badge: "bg-red-600 text-white", label: "🔴 긴급" },
  warning: { color: "bg-yellow-50 border-yellow-300 text-yellow-900",
             badge: "bg-yellow-500 text-white", label: "🟡 주의" },
  stable: { color: "bg-green-50 border-green-200 text-green-900",
            badge: "bg-green-600 text-white", label: "🟢 안정" },
} as const;

export default function Dashboard() {
  const [rows, setRows] = useState<DashboardRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setRows(await api.dashboard());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, []);

  const counts = {
    critical: rows.filter((r) => r.level === "critical").length,
    warning: rows.filter((r) => r.level === "warning").length,
    stable: rows.filter((r) => r.level === "stable").length,
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-bold">담당 환자 모니터링</h1>
        <p className="text-sm text-gray-500 mt-1">
          C-Rehab · 자동 새로고침 10초
        </p>
      </header>

      <section className="grid grid-cols-3 gap-3">
        <SummaryCard label="🔴 긴급" count={counts.critical} bg="bg-red-50" tx="text-red-700" />
        <SummaryCard label="🟡 주의" count={counts.warning} bg="bg-yellow-50" tx="text-yellow-700" />
        <SummaryCard label="🟢 안정" count={counts.stable} bg="bg-green-50" tx="text-green-700" />
      </section>

      <section className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="font-bold">담당 환자 ({rows.length})</h2>
          <button
            onClick={load}
            className="text-xs px-3 py-1 bg-gray-100 rounded-full"
          >
            ↻ 새로고침
          </button>
        </div>

        {loading && rows.length === 0 ? (
          <div className="p-8 text-center text-gray-400">로딩 중...</div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            환자 데이터 없음. backend의 seed.py 실행 확인.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {rows.map((r) => {
              const style = LEVEL_STYLE[r.level];
              return (
                <div
                  key={r.patient.id}
                  className={`flex items-center gap-4 p-5 ${style.color}`}
                >
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-bold ${style.badge}`}
                  >
                    {style.label}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold">
                      {r.patient.name} · {r.patient.id}
                    </div>
                    <div className="text-xs text-gray-600 mt-0.5">
                      {2026 - r.patient.birth_year}세 · {r.patient.icd10} ·
                      사이클 D{r.patient.cycle_day} · 최근 {r.session_count}회 응답
                    </div>
                    <div className="text-sm mt-1 line-clamp-1">
                      {r.summary}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <Link
                      href={`/patients/${r.patient.id}/pre-visit`}
                      className="text-xs px-3 py-2 bg-brand text-white rounded-lg font-semibold whitespace-nowrap text-center"
                    >
                      Pre-Visit Report →
                    </Link>
                    <Link
                      href={`/patients/${r.patient.id}/config`}
                      className="text-xs px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg font-semibold whitespace-nowrap text-center"
                    >
                      ⚙ PRO 설정
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function SummaryCard({
  label, count, bg, tx,
}: { label: string; count: number; bg: string; tx: string }) {
  return (
    <div className={`${bg} ${tx} rounded-2xl p-4`}>
      <div className="text-xs font-semibold">{label}</div>
      <div className="text-3xl font-black mt-2">{count}</div>
    </div>
  );
}
