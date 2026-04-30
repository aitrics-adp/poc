"use client";
export const dynamic = "force-dynamic";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

const PATIENT_APP_URL = process.env.NEXT_PUBLIC_PATIENT_APP_URL || "http://localhost:3000";

export default function PatientPreviewPage() {
  const params = useParams<{ id: string }>();
  const patientId = params.id;
  const [mode, setMode] = useState<"general" | "elder">("general");

  const previewUrl =
    mode === "elder"
      ? `${PATIENT_APP_URL}/elder/home?patient_id=${patientId}`
      : `${PATIENT_APP_URL}/?patient_id=${patientId}`;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-4">
      <header>
        <Link href={`/patients/${patientId}/config`} className="text-sm text-gray-500">
          ← PRO 설정으로
        </Link>
        <h1 className="text-2xl font-bold mt-1">환자 화면 미리보기</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          환자 {patientId}가 보게 될 실제 PRO 화면
        </p>
      </header>

      <div className="flex gap-2">
        {(["general", "elder"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-2 rounded-xl text-sm font-bold ${
              mode === m
                ? "bg-brand text-white"
                : "bg-gray-100 text-gray-700"
            }`}
          >
            {m === "general" ? "일반 모드" : "어르신 모드"}
          </button>
        ))}
        <a
          href={previewUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto px-4 py-2 bg-white border border-gray-300 rounded-xl text-sm"
        >
          새 창에서 열기 ↗
        </a>
      </div>

      <div className="bg-gray-100 rounded-2xl p-4">
        <div className="bg-black rounded-2xl p-2 mx-auto" style={{ width: 380 }}>
          <iframe
            src={previewUrl}
            className="bg-white rounded-xl"
            style={{ width: "100%", height: 700, border: 0 }}
            title={`Patient ${mode} mode preview`}
          />
        </div>
        <div className="text-xs text-gray-500 text-center mt-2">
          ⓘ 환자앱 dev 서버({PATIENT_APP_URL})가 떠 있어야 보입니다.
        </div>
      </div>
    </div>
  );
}
