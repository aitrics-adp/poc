"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  LineChart, Line, CartesianGrid, XAxis, YAxis, ResponsiveContainer, Tooltip,
} from "recharts";
import api, { ProScore, ProSession } from "@/lib/api";

export default function ResultPage() {
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const [history, setHistory] = useState<{
    sessions: ProSession[]; scores: ProScore[];
  }>({ sessions: [], scores: [] });

  useEffect(() => {
    api.history(patientId).then(setHistory);
  }, [patientId]);

  // 가장 최근 세션의 점수만 추출
  const latestSessionId = [...history.sessions]
    .sort((a, b) => +new Date(b.started_at) - +new Date(a.started_at))[0]?.id;
  const latestScores = history.scores.filter((s) => s.session_id === latestSessionId);

  // 시계열 (PRO-CTCAE 신경병증 severity)
  const sessionsAsc = [...history.sessions].sort(
    (a, b) => +new Date(a.started_at) - +new Date(b.started_at)
  );
  const trendData = sessionsAsc.map((s) => {
    const day = new Date(s.started_at).toLocaleDateString("ko-KR", {
      month: "numeric", day: "numeric",
    });
    const sc = history.scores.find(
      (x) => x.session_id === s.id && x.tool_code === "PRO-CTCAE" && x.subscale === "neuropathy"
    );
    return { day, neuropathy: sc?.value ?? 0 };
  });

  const hadsA = latestScores.find((s) => s.subscale === "HADS-A");
  const hadsD = latestScores.find((s) => s.subscale === "HADS-D");

  return (
    <div className="p-6 space-y-5">
      <header>
        <h1 className="text-xl font-bold">이번 세션 결과</h1>
        <p className="text-xs text-gray-500 mt-1">
          {history.sessions.length}일째 기록 누적 중
        </p>
      </header>

      {/* HADS 결과 카드 */}
      {(hadsA || hadsD) && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">HADS · 불안·우울</h2>
          <div className="grid grid-cols-2 gap-2">
            {hadsA && (
              <ScoreCard
                title="불안 (HADS-A)"
                value={hadsA.value}
                level={hadsA.classification}
                flag={hadsA.mcid_flag}
              />
            )}
            {hadsD && (
              <ScoreCard
                title="우울 (HADS-D)"
                value={hadsD.value}
                level={hadsD.classification}
                flag={hadsD.mcid_flag}
              />
            )}
          </div>
        </section>
      )}

      {/* 추세 차트 */}
      {trendData.length > 1 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <h2 className="text-sm font-semibold mb-2">최근 7일 신경병증 추세</h2>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 4]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone" dataKey="neuropathy"
                stroke="#DC2626" strokeWidth={2} dot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="text-xs text-gray-500 mt-2">
            0=없음 · 4=매우 심함. 2점↑ 2주 지속 시 RED 알림.
          </div>
        </section>
      )}

      {/* PRO-CTCAE 최신 점수 */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">PRO-CTCAE · 증상</h2>
        <div className="grid grid-cols-2 gap-2">
          {latestScores
            .filter((s) => s.tool_code === "PRO-CTCAE")
            .map((s) => (
              <ScoreCard
                key={s.id}
                title={koSymptomName(s.subscale ?? "")}
                value={s.value}
                level={null}
                flag={s.mcid_flag}
              />
            ))}
        </div>
      </section>

      <div className="pt-4 space-y-2">
        <Link
          href="/"
          className="block w-full py-3 bg-brand text-white text-center rounded-xl font-semibold"
        >
          홈으로
        </Link>
        <Link
          href="/talk"
          className="block w-full py-3 bg-brand-soft text-brand-deep text-center rounded-xl font-semibold"
        >
          💬 건강 상담 (LLM Free Talk)
        </Link>
      </div>
    </div>
  );
}

function ScoreCard({ title, value, level, flag }: {
  title: string; value: number; level: string | null; flag: string | null;
}) {
  const bg =
    flag === "red"
      ? "bg-red-50 border-red-200 text-red-900"
      : flag === "yellow"
      ? "bg-yellow-50 border-yellow-200 text-yellow-900"
      : level === "borderline"
      ? "bg-yellow-50 border-yellow-200 text-yellow-900"
      : level === "case"
      ? "bg-red-50 border-red-200 text-red-900"
      : "bg-gray-50 border-gray-200 text-gray-800";
  return (
    <div className={`border rounded-xl p-3 ${bg}`}>
      <div className="text-xs">{title}</div>
      <div className="text-2xl font-bold mt-1">{value.toFixed(0)}</div>
      <div className="text-xs mt-1">
        {flag === "red" && "🔴 RED 알림"}
        {flag === "yellow" && "🟡 주의"}
        {level === "borderline" && !flag && "경계값"}
        {level === "case" && !flag && "이상"}
        {level === "normal" && !flag && "정상"}
      </div>
    </div>
  );
}

function koSymptomName(en: string) {
  const map: Record<string, string> = {
    fatigue: "피로",
    appetite: "식욕부진",
    nausea: "오심·구토",
    diarrhea: "설사",
    neuropathy: "신경병증",
  };
  return map[en] ?? en;
}
