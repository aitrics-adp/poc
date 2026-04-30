"use client";
export const dynamic = "force-dynamic";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import api, { ProScore } from "@/lib/api";

/**
 * 어르신 모드 결과:
 * - 신호등 (초록/노랑/빨강) + 자연어 요약
 * - 수치 X, 차트 X
 * - "잘 하셨어요" + 가족 공유 안내
 */

export default function ElderResult() {
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const [scores, setScores] = useState<ProScore[]>([]);

  useEffect(() => {
    api.history(patientId).then((h) => {
      // 가장 최근 세션의 점수만
      const latest = [...h.sessions].sort(
        (a, b) => +new Date(b.started_at) - +new Date(a.started_at)
      )[0];
      if (latest) {
        setScores(h.scores.filter((s) => s.session_id === latest.id));
      }
    });
  }, [patientId]);

  // 신호등 등급 결정
  const hasRed = scores.some((s) => s.mcid_flag === "red");
  const hasYellow = scores.some((s) => s.mcid_flag === "yellow");
  const level: "red" | "yellow" | "green" =
    hasRed ? "red" : hasYellow ? "yellow" : "green";

  const config = {
    green: {
      bg: "bg-green-50",
      emoji: "🌱",
      title: "오늘도 잘 하셨어요!",
      message: "몸 상태가 안정적이에요.\n계속 같이 해드릴게요.",
      border: "border-green-200",
    },
    yellow: {
      bg: "bg-yellow-50",
      emoji: "🌼",
      title: "잘 알려주셨어요",
      message: "조금 신경 써야 할 부분이 있어요.\n다음 진료 때 선생님께 전해드릴게요.",
      border: "border-yellow-200",
    },
    red: {
      bg: "bg-red-50",
      emoji: "❤️",
      title: "솔직하게 말씀해 주셔서 고마워요",
      message: "지금 상태가 많이 힘드신 것 같아요.\n선생님께 바로 알려드릴게요.\n불편하시면 가족에게도 전화해 보세요.",
      border: "border-red-200",
    },
  }[level];

  const caregiverTel = process.env.NEXT_PUBLIC_CAREGIVER_TEL || "010-0000-0000";

  return (
    <div className="p-6 min-h-screen flex flex-col">
      <div className={`flex-1 flex flex-col items-center justify-center text-center ${config.bg} ${config.border} border-2 rounded-3xl p-8 mt-4`}>
        <div className="text-8xl mb-6">{config.emoji}</div>
        <h1 className="text-elder-lg font-bold mb-4">{config.title}</h1>
        <p className="text-elder leading-relaxed whitespace-pre-line">
          {config.message}
        </p>
      </div>

      <div className="space-y-3 mt-6">
        {level === "red" && (
          <a
            href={`tel:${caregiverTel}`}
            className="block w-full py-5 bg-warn text-white text-xl font-bold rounded-2xl text-center"
          >
            📞 가족에게 전화하기
          </a>
        )}
        <Link
          href={`/elder/home?patient_id=${patientId}`}
          className="block w-full py-5 bg-brand text-white text-xl font-bold rounded-2xl text-center"
        >
          홈으로
        </Link>
      </div>
    </div>
  );
}
