"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import api from "@/lib/api";

const SYMPTOM_LABEL: Record<string, string> = {
  fatigue: "피로", appetite: "식욕부진", nausea: "오심·구토",
  diarrhea: "설사", neuropathy: "손발 저림",
};
const ATTR_LABEL: Record<string, string> = {
  freq: "빈도", severity: "강도", interference: "일상 방해",
};

export default function ResponsesByDayPage() {
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const [data, setData] = useState<any>(null);
  const [windowDays, setWindowDays] = useState(7);
  const [openDay, setOpenDay] = useState<string | null>(null);

  const load = async () => {
    const d = await api.responsesByDay(patientId, windowDays);
    setData(d);
    if (d.days?.length > 0 && !openDay) setOpenDay(d.days[0].date);
  };

  useEffect(() => { load(); }, [patientId, windowDays]);

  if (!data) return <div className="p-8 text-center text-gray-400">로딩...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <header>
        <Link href={`/patients/${patientId}/pre-visit`} className="text-sm text-gray-500">
          ← Pre-Visit Report
        </Link>
        <h1 className="text-2xl font-bold mt-1">일별 PRO 응답 상세</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          환자 {patientId} {data.patient_name && `· ${data.patient_name}`} ·{" "}
          최근 {windowDays}일 ({data.days?.length || 0}일 응답)
        </p>
        <div className="flex gap-2 mt-3">
          {[7, 14, 30, 60].map((d) => (
            <button
              key={d}
              onClick={() => setWindowDays(d)}
              className={`text-xs px-3 py-1.5 rounded-lg ${
                windowDays === d
                  ? "bg-brand text-white"
                  : "bg-white border border-gray-300"
              }`}
            >
              {d}일
            </button>
          ))}
        </div>
      </header>

      {data.days?.length === 0 ? (
        <div className="bg-gray-50 rounded-xl p-10 text-center text-gray-400">
          선택 기간 내 응답 없음
        </div>
      ) : (
        <div className="space-y-2">
          {data.days?.map((day: any) => (
            <DayCard
              key={day.date}
              day={day}
              isOpen={openDay === day.date}
              onToggle={() => setOpenDay(openDay === day.date ? null : day.date)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DayCard({ day, isOpen, onToggle }: any) {
  const totalResponses = day.sessions.reduce(
    (s: number, sess: any) => s + sess.responses.length,
    0
  );
  // RED/YELLOW 카운트
  const reds = day.sessions.flatMap((s: any) =>
    s.scores.filter((x: any) => x.mcid_flag === "red")
  );
  const yellows = day.sessions.flatMap((s: any) =>
    s.scores.filter((x: any) => x.mcid_flag === "yellow")
  );
  const dateLabel = new Date(day.date).toLocaleDateString("ko-KR", {
    month: "long", day: "numeric", weekday: "short",
  });

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-50"
      >
        <div className="flex items-center gap-3 text-left">
          <span className="font-bold">{dateLabel}</span>
          <span className="text-xs text-gray-500">
            {day.sessions.length}회 · {totalResponses}문항
          </span>
          {reds.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded-full">
              🔴 RED {reds.length}
            </span>
          )}
          {yellows.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">
              🟡 {yellows.length}
            </span>
          )}
        </div>
        <span className="text-gray-400">{isOpen ? "▼" : "▶"}</span>
      </button>

      {isOpen && (
        <div className="border-t border-gray-200 p-4 space-y-4">
          {day.sessions.map((sess: any) => (
            <SessionDetail key={sess.id} sess={sess} />
          ))}
        </div>
      )}
    </div>
  );
}

function SessionDetail({ sess }: any) {
  const time = new Date(sess.started_at).toLocaleTimeString("ko-KR", {
    hour: "2-digit", minute: "2-digit",
  });

  // 도구별 그룹핑
  const byTool: Record<string, any[]> = {};
  for (const r of sess.responses) {
    (byTool[r.tool_code] ||= []).push(r);
  }

  return (
    <div className="bg-gray-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-600">
          🕐 {time} ·
          <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-white border">
            {sess.flex_mode === "full"
              ? "🟢 Full"
              : sess.flex_mode === "quick"
              ? "🟡 Quick"
              : "⚪ NoChange"}
          </span>
          <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-white border">
            {sess.ui_mode === "elder" ? "👴 어르신" : "🧑 일반"}
          </span>
        </div>
        <span className="text-[10px] text-gray-400">세션 #{sess.id}</span>
      </div>

      {sess.scores.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] text-gray-500 mb-1">📊 채점 결과</div>
          <div className="flex flex-wrap gap-1">
            {sess.scores.map((sc: any, i: number) => {
              const flag = sc.mcid_flag;
              const cls =
                flag === "red"
                  ? "bg-red-100 text-red-800"
                  : flag === "yellow"
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-white border border-gray-200 text-gray-700";
              return (
                <span
                  key={i}
                  className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${cls}`}
                >
                  {sc.tool_code} {sc.subscale}: {sc.value.toFixed(1)}
                  {flag && ` ${flag === "red" ? "🔴" : "🟡"}`}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="space-y-3">
        {Object.entries(byTool).map(([tool, responses]) => (
          <div key={tool}>
            <div className="text-xs font-bold text-gray-700 mb-1">{tool}</div>
            {tool === "PRO-CTCAE" ? (
              <ProCtcaeTable responses={responses} />
            ) : tool === "HADS" ? (
              <HadsList responses={responses} />
            ) : (
              <GenericList responses={responses} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ProCtcaeTable({ responses }: any) {
  // 증상별 그룹핑
  const bySym: Record<string, any[]> = {};
  for (const r of responses) {
    (bySym[r.item_code] ||= []).push(r);
  }
  return (
    <table className="text-xs w-full">
      <thead>
        <tr className="text-gray-500 border-b border-gray-200">
          <th className="text-left py-1 pr-2">증상</th>
          <th className="text-left px-2">속성</th>
          <th className="text-left px-2">응답</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(bySym).map(([sym, items]) =>
          (items as any[]).map((r, i) => (
            <tr key={`${sym}-${i}`} className="border-b border-gray-100">
              <td className="py-1.5 pr-2">
                {i === 0 ? (
                  <span className="font-semibold">
                    {SYMPTOM_LABEL[sym] ?? sym}
                  </span>
                ) : ""}
              </td>
              <td className="px-2 text-gray-600">
                {ATTR_LABEL[r.attribute] ?? r.attribute}
              </td>
              <td className="px-2">
                <span className="font-bold">{r.raw_value}</span>{" "}
                <span className="text-gray-500">{r.label}</span>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}

function HadsList({ responses }: any) {
  return (
    <div className="space-y-1">
      {responses.map((r: any) => (
        <div
          key={r.item_code}
          className="flex items-start justify-between gap-3 text-xs py-1 border-b border-gray-100"
        >
          <div className="flex-1 min-w-0">
            <span className="font-semibold mr-2">{r.item_code}</span>
            <span className="text-gray-600">{r.question}</span>
          </div>
          <div className="whitespace-nowrap">
            <span className="font-bold">{r.raw_value}</span>{" "}
            <span className="text-gray-500">{r.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function GenericList({ responses }: any) {
  return (
    <div className="space-y-1">
      {responses.map((r: any, i: number) => (
        <div
          key={i}
          className="flex items-start justify-between gap-3 text-xs py-1 border-b border-gray-100"
        >
          <span>
            {r.item_code} {r.attribute && `(${r.attribute})`}
          </span>
          <span className="font-bold">{r.raw_value}</span>
        </div>
      ))}
    </div>
  );
}
