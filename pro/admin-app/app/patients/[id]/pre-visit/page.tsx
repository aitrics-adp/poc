"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  LineChart, Line, CartesianGrid, XAxis, YAxis,
  ResponsiveContainer, Tooltip, Legend,
} from "recharts";
import api, { PreVisitReport } from "@/lib/api";

export default function PreVisitPage() {
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const [report, setReport] = useState<PreVisitReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [pushStatus, setPushStatus] = useState<string>("");

  useEffect(() => {
    api.preVisit(patientId).then((r) => {
      setReport(r);
      setLoading(false);
    });
  }, [patientId]);

  const sendPush = async () => {
    setPushStatus("발송 중...");
    try {
      const r: any = await api.sendPush({
        patient_id: patientId,
        title: "오늘의 PRO 설문 시작해주세요",
        body: "5분이면 돼요. 어드민에서 보낸 알림입니다.",
        url: "/pro/start",
      });
      if (r.sent > 0) {
        setPushStatus(`✅ ${r.sent}/${r.subscription_count} 디바이스에 푸시 완료`);
      } else if (r.reason === "no_subscriptions") {
        setPushStatus(
          `⚠️ 구독 0건 — 환자앱 홈에서 ${patientId}의 '🔔 푸시 구독' 버튼을 먼저 눌러주세요.`
        );
      } else if (r.reason === "no_vapid_key") {
        setPushStatus(`❌ ${r.hint ?? r.reason}`);
      } else if (r.failed?.length > 0) {
        setPushStatus(
          `❌ 모든 디바이스 발송 실패 (구독 ${r.subscription_count}건): ${r.failed[0].error.slice(0, 80)}`
        );
      } else {
        setPushStatus(`⚠️ 발송 0건. ${r.hint ?? ""}`);
      }
    } catch (e: any) {
      setPushStatus("❌ " + e.message);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-400">로딩 중...</div>;
  if (!report) return <div className="p-8 text-center text-red-500">환자를 찾을 수 없습니다.</div>;

  // 추세 차트 데이터 정리: PRO-CTCAE_neuropathy + HADS-A를 한 차트에 오버레이
  const neuropathy = report.trend["PRO-CTCAE_neuropathy"] ?? [];
  const hadsA = report.trend["HADS_HADS-A"] ?? [];

  const chartData = neuropathy.map((n) => {
    const date = new Date(n.date).toLocaleDateString("ko-KR", {
      month: "numeric", day: "numeric",
    });
    const matchA = hadsA.find((h) =>
      new Date(h.date).toDateString() === new Date(n.date).toDateString());
    return {
      date,
      "신경병증": n.value,
      "HADS-A": matchA?.value ?? null,
    };
  });

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-gray-500">
            ← 모니터링 대시보드
          </Link>
          <h1 className="text-2xl font-bold mt-1">
            {report.patient.name} · {report.patient.id} · Pre-Visit Report
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {2026 - report.patient.birth_year}세 · {report.patient.icd10} ·
            사이클 D{report.patient.cycle_day} ·
            최근 {report.window_days}일 ({report.session_count}회 응답)
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <button
            onClick={sendPush}
            className="px-4 py-2 bg-brand text-white rounded-xl text-sm font-bold"
          >
            🔔 환자에게 PRO 알림 푸시
          </button>
          {pushStatus && (
            <div className="text-xs text-gray-600 max-w-xs text-right">{pushStatus}</div>
          )}
        </div>
      </header>

      {/* One-Line Summary */}
      <section className="bg-brand-soft border border-brand/30 rounded-2xl p-5">
        <div className="text-xs font-bold text-brand uppercase tracking-widest">
          One-Line Summary
        </div>
        <p className="text-base font-semibold mt-2 text-brand-deep">
          {report.summary}
        </p>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Trend Chart */}
        <section className="md:col-span-2 bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="font-bold mb-3">최근 7일 추세</h2>
          {chartData.length > 1 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone" dataKey="신경병증"
                  stroke="#DC2626" strokeWidth={2.5}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone" dataKey="HADS-A"
                  stroke="#F59E0B" strokeWidth={2}
                  dot={{ r: 4 }} connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-sm text-gray-400 py-10 text-center">
              데이터 부족 — 환자 응답 누적 후 표시됩니다.
            </div>
          )}
          <div className="mt-3 text-xs text-gray-500">
            🔴 PRO-CTCAE 신경병증 (0–4) · 🟡 HADS-A 불안 (0–21)
          </div>
        </section>

        {/* Key Changes */}
        <section className="bg-white border border-gray-200 rounded-2xl p-5">
          <h2 className="font-bold mb-3">Key Changes</h2>
          {report.alerts.length === 0 ? (
            <div className="text-sm text-gray-400 py-6 text-center">
              알림 없음 — 안정적
            </div>
          ) : (
            <div className="space-y-2">
              {report.alerts.map((a, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl border text-xs ${
                    a.level === "red"
                      ? "bg-red-50 border-red-200 text-red-900"
                      : "bg-yellow-50 border-yellow-200 text-yellow-900"
                  }`}
                >
                  <div className="font-bold">
                    {a.level === "red" ? "🔴 RED" : "🟡 YELLOW"} ·{" "}
                    {a.tool} {a.subscale}
                  </div>
                  <div className="mt-1">현재 값: {a.value}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Lifelog */}
      <section className="bg-white border border-gray-200 rounded-2xl p-5">
        <h2 className="font-bold mb-2">라이프로그 대조</h2>
        <p className="text-sm text-gray-700">{report.lifelog_correlation}</p>
      </section>

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        <Link
          href={`/patients/${patientId}/responses`}
          className="px-4 py-2 bg-brand text-white rounded-xl text-sm font-semibold"
        >
          📋 일별 PRO 응답 보기
        </Link>
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-white border border-gray-300 rounded-xl text-sm font-semibold"
        >
          📄 PDF 인쇄
        </button>
        <Link
          href={`/patients/${patientId}/config`}
          className="px-4 py-2 bg-white border border-gray-300 rounded-xl text-sm font-semibold"
        >
          ⚙ PRO 도구 설정
        </Link>
        <Link
          href="/"
          className="px-4 py-2 bg-gray-100 rounded-xl text-sm font-semibold"
        >
          ← 모니터링으로
        </Link>
      </div>
    </div>
  );
}
