"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api, { FullModeStatus } from "@/lib/api";

export default function ProStartPage() {
  const router = useRouter();
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const [status, setStatus] = useState<FullModeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    api.fullModeStatus(patientId).then((s) => {
      setStatus(s);
      setLoading(false);
    });
  }, [patientId]);

  const startMode = async (flex: "full" | "quick" | "no_change") => {
    setErr("");
    try {
      const s = await api.startSession(patientId, "general", flex);
      if (flex === "no_change") {
        await api.applyCarryOver(s.id);
        await api.completeSession(s.id);
        router.push(`/result?patient_id=${patientId}`);
        return;
      }
      if (flex === "quick") {
        router.push(`/pro/quick?patient_id=${patientId}&session_id=${s.id}`);
        return;
      }
      router.push(`/pro?patient_id=${patientId}&session_id=${s.id}`);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-400">로딩 중...</div>;

  const requiresFull = status?.requires_full;

  return (
    <div className="p-6 space-y-4 max-w-md mx-auto">
      <header>
        <button
          onClick={() => router.push("/")}
          className="text-sm text-gray-500"
        >
          ← 홈
        </button>
        <h1 className="text-xl font-bold mt-1">오늘의 PRO 모드 선택</h1>
        {status?.days_since_last_full !== null && status?.days_since_last_full !== undefined && (
          <p className="text-xs text-gray-500 mt-0.5">
            마지막 Full 응답 {status.days_since_last_full}일 전
          </p>
        )}
      </header>

      {requiresFull && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-xs text-yellow-900">
          📌 30일 이상 Full 응답이 없어 오늘은 Full 모드로 진행됩니다 (월 1회 의무).
        </div>
      )}
      {err && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-900">
          {err}
        </div>
      )}

      <ModeCard
        title="🟢 Full 모드"
        subtitle="전체 문항 응답 (5~10분)"
        body="모든 항목을 처음부터 답해요. 가장 정확한 데이터가 됩니다."
        recommended={requiresFull}
        onClick={() => startMode("full")}
      />
      <ModeCard
        title="🟡 Quick 모드"
        subtitle="카테고리 스크리닝 후 양성만 (2~3분)"
        body="5개 카테고리 중 '있음'만 골라 세부 문항으로 진행. 평소엔 이게 빠릅니다."
        disabled={requiresFull}
        onClick={() => startMode("quick")}
      />
      <ModeCard
        title="⚪ No-Change 모드"
        subtitle="직전 응답 그대로 확인 (15초)"
        body="어제와 같다면 한 번에 확인. 직전 Full 후 30일 이내·연속 3회 이내 사용 가능."
        disabled={requiresFull}
        onClick={() => startMode("no_change")}
      />
    </div>
  );
}

function ModeCard({
  title, subtitle, body, recommended, disabled, onClick,
}: {
  title: string;
  subtitle: string;
  body: string;
  recommended?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full text-left p-4 rounded-2xl border transition-colors ${
        disabled
          ? "bg-gray-50 border-gray-200 text-gray-400"
          : recommended
          ? "bg-brand-soft border-brand text-brand-deep"
          : "bg-white border-gray-200 text-gray-900 hover:border-brand/50"
      }`}
    >
      <div className="font-bold text-base">
        {title}
        {recommended && <span className="ml-2 text-xs">(권장)</span>}
      </div>
      <div className="text-xs mt-0.5 opacity-80">{subtitle}</div>
      <div className="text-xs mt-2">{body}</div>
    </button>
  );
}
