"use client";
export const dynamic = "force-dynamic";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import api from "@/lib/api";

type Msg = {
  role: "user" | "assistant";
  text: string;
  type?: "emergency" | "out_of_scope" | "normal";
};

const SAMPLE_PROMPTS = [
  { label: "🟢 정상", text: "오늘 좀 피곤하네요" },
  { label: "🔴 응급", text: "숨이 안 쉬어져요" },
  { label: "🟡 처방", text: "약 더 먹어도 되나요?" },
];

export default function TalkPage() {
  const params = useSearchParams();
  const patientId = params.get("patient_id") ?? "C-1042";
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [emergency, setEmergency] = useState(false);

  const send = async (text: string) => {
    if (!text.trim()) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const r = await api.talk(text, patientId);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: r.response, type: r.type as any },
      ]);
      if (r.type === "emergency") setEmergency(true);
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `(에러: ${e.message})`, type: "normal" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // 응급 화면 강제 전환 (FN-EVENT-003)
  if (emergency) {
    return (
      <div className="p-6 min-h-screen bg-red-50 flex flex-col">
        <div className="text-7xl text-center mt-12">🚨</div>
        <h1 className="text-3xl font-black text-red-700 text-center mt-6">
          즉시 119에 전화하세요
        </h1>
        <p className="text-center text-red-900 mt-4 px-4 leading-relaxed">
          응급 상황으로 분류되었어요.
          <br />
          가까운 응급실로 가시거나, 119에 즉시 전화하세요.
        </p>

        <a
          href="tel:119"
          className="mt-8 mx-auto w-full max-w-xs py-5 bg-red-600 text-white text-2xl font-black text-center rounded-2xl shadow-lg"
        >
          📞 119 전화
        </a>
        <a
          href="tel:010-0000-0000"
          className="mt-3 mx-auto w-full max-w-xs py-4 bg-white border-2 border-red-300 text-red-700 text-lg font-bold text-center rounded-2xl"
        >
          가족에게 전화
        </a>

        <button
          onClick={() => {
            setEmergency(false);
            setMessages([]);
          }}
          className="mt-12 mx-auto text-sm text-red-600 underline"
        >
          (시연 종료 — 처음으로)
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4 min-h-screen flex flex-col pb-32">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-sm text-gray-500">
          ← 홈
        </Link>
        <span className="text-xs text-gray-400">LLM 가드레일 시연</span>
      </header>

      <h1 className="text-xl font-bold">건강 상담</h1>
      <p className="text-xs text-gray-500 -mt-2">
        ⚠️ POC: LLM Mock 모드 — 응급/처방 키워드 사전 매칭으로 100% 차단 검증
      </p>

      {/* 빠른 시연 버튼 */}
      <div className="flex flex-wrap gap-2">
        {SAMPLE_PROMPTS.map((p) => (
          <button
            key={p.text}
            onClick={() => send(p.text)}
            className="px-3 py-1.5 bg-brand-soft text-brand-deep rounded-full text-xs font-semibold"
          >
            {p.label}: {p.text}
          </button>
        ))}
      </div>

      {/* 채팅 영역 */}
      <div className="flex-1 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-gray-400 p-6 bg-gray-50 rounded-xl text-center">
            메시지를 입력하거나 위 버튼을 눌러보세요
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[80%] rounded-2xl p-3 text-sm ${
              m.role === "user"
                ? "ml-auto bg-brand text-white"
                : m.type === "out_of_scope"
                ? "bg-yellow-50 border border-yellow-200 text-yellow-900"
                : m.type === "emergency"
                ? "bg-red-50 border border-red-200 text-red-900"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {m.type === "out_of_scope" && (
              <div className="text-xs font-bold mb-1">
                🛡 가드레일: Out-of-Scope 차단
              </div>
            )}
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="bg-gray-100 rounded-2xl p-3 text-sm text-gray-500">
            응답 중...
          </div>
        )}
      </div>

      {/* 입력창 */}
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-white border-t border-gray-200 p-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-xl text-sm"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-3 bg-brand text-white rounded-xl text-sm font-semibold disabled:bg-gray-300"
          >
            보내기
          </button>
        </form>
      </div>
    </div>
  );
}
