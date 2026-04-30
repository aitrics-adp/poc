"use client";
export const dynamic = "force-dynamic";

import { useState } from "react";
import Link from "next/link";
import api from "@/lib/api";

type Result = { name: string; data: any; ranAt: string };

export default function JobsPage() {
  const [results, setResults] = useState<Result[]>([]);
  const [running, setRunning] = useState<string>("");

  const run = async (name: string, fn: () => Promise<any>) => {
    setRunning(name);
    try {
      const data = await fn();
      setResults((prev) => [
        { name, data, ranAt: new Date().toLocaleTimeString("ko-KR") },
        ...prev,
      ]);
    } catch (e: any) {
      setResults((prev) => [
        { name, data: { error: e.message }, ranAt: new Date().toLocaleTimeString("ko-KR") },
        ...prev,
      ]);
    } finally {
      setRunning("");
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-4">
      <header>
        <Link href="/" className="text-sm text-gray-500">← 대시보드</Link>
        <h1 className="text-2xl font-bold mt-1">예약 작업 (Cron Jobs)</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          POC에서는 수동 트리거. 운영 시 cron으로 자동 실행 예정.
        </p>
      </header>

      <div className="space-y-3">
        <JobCard
          name="precompute_pre_visit"
          title="📊 Pre-Visit Report 사전계산"
          desc="FN-RPT-007: 외래 D-2 가정. 모든 환자의 One-Line Summary 미리 산출."
          schedule="외래일 기준 D-2 새벽 03:00"
          running={running === "precompute_pre_visit"}
          onClick={() =>
            run("precompute_pre_visit", api.jobPrecomputePreVisit)
          }
        />
        <JobCard
          name="check_mcid"
          title="🔴 MCID 자동 푸시"
          desc="FN-EVENT-001: 모든 환자의 RED 알림을 환자에게 자동 푸시."
          schedule="매일 09:00 KST"
          running={running === "check_mcid"}
          onClick={() => run("check_mcid", api.jobCheckMcid)}
        />
        <JobCard
          name="check_non_response"
          title="📭 3일 미응답 감지"
          desc="FN-EVENT-002: 3일 연속 PRO 미응답 환자에게 알림 푸시."
          schedule="매일 09:00 KST"
          running={running === "check_non_response"}
          onClick={() => run("check_non_response", api.jobCheckNonResponse)}
        />
      </div>

      {results.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-bold mt-6">실행 결과 (최근 {results.length}건)</h2>
          {results.map((r, i) => (
            <div
              key={i}
              className="bg-white border border-gray-200 rounded-xl p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-sm">{r.name}</span>
                <span className="text-xs text-gray-500">{r.ranAt}</span>
              </div>
              <pre className="text-[10px] bg-gray-50 rounded p-2 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(r.data, null, 2)}
              </pre>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function JobCard({
  title,
  desc,
  schedule,
  running,
  onClick,
}: {
  name: string;
  title: string;
  desc: string;
  schedule: string;
  running: boolean;
  onClick: () => void;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 flex items-start gap-4">
      <div className="flex-1">
        <div className="font-bold">{title}</div>
        <p className="text-xs text-gray-700 mt-1">{desc}</p>
        <p className="text-[10px] text-gray-400 mt-1">⏰ {schedule}</p>
      </div>
      <button
        onClick={onClick}
        disabled={running}
        className="px-4 py-2 bg-brand text-white rounded-xl text-sm font-bold disabled:bg-gray-300 whitespace-nowrap"
      >
        {running ? "실행 중..." : "수동 실행"}
      </button>
    </div>
  );
}
