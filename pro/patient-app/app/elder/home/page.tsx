"use client";
export const dynamic = "force-dynamic";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export default function ElderHome() {
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const caregiverTel = process.env.NEXT_PUBLIC_CAREGIVER_TEL || "010-0000-0000";
  const hotlineTel = process.env.NEXT_PUBLIC_HOTLINE_TEL || "1577-0000";

  return (
    <div className="p-6 min-h-screen flex flex-col text-elder">
      <div className="text-center mt-8">
        <div className="text-6xl">👋</div>
        <h1 className="text-elder-lg font-bold mt-4">안녕하세요</h1>
        <p className="text-elder text-gray-600 mt-2">
          오늘도 함께 해드릴게요
        </p>
      </div>

      <div className="flex-1 flex flex-col justify-center gap-4 mt-8">
        <Link
          href={`/elder/pro?patient_id=${patientId}`}
          className="w-full py-6 bg-brand text-white text-2xl font-black rounded-3xl shadow-lg text-center"
        >
          😊 오늘 어떠세요?
        </Link>
        <p className="text-center text-base text-gray-500">
          (3분 안에 끝나요)
        </p>
      </div>

      <div className="space-y-3 pt-6 border-t border-gray-200">
        <p className="text-base text-gray-700 text-center font-semibold">
          도움이 필요하실 땐
        </p>
        <a
          href={`tel:${caregiverTel}`}
          className="w-full py-5 bg-warn text-white text-xl font-bold rounded-2xl text-center block"
        >
          📞 가족에게 전화하기
        </a>
        <a
          href={`tel:${hotlineTel}`}
          className="w-full py-5 bg-success text-white text-xl font-bold rounded-2xl text-center block"
        >
          🏥 병원에 전화하기
        </a>
      </div>

      <Link
        href="/"
        className="mt-6 text-center text-sm text-gray-400"
      >
        (일반 모드로 돌아가기)
      </Link>
    </div>
  );
}
