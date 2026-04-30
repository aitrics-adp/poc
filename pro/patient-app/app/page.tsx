"use client";
export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import Link from "next/link";
import api, { Patient } from "@/lib/api";
import { registerPush } from "@/lib/push";

export default function Home() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [subCounts, setSubCounts] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState<string>("");
  const [msg, setMsg] = useState<string>("");

  const refresh = async () => {
    const ps = await api.patients();
    setPatients(ps);
    // 각 환자 구독 수 병렬 조회
    const counts: Record<string, number> = {};
    await Promise.all(
      ps.map(async (p) => {
        try {
          const s = await api.pushSubscriptions(p.id);
          counts[p.id] = s.count;
        } catch {
          counts[p.id] = 0;
        }
      })
    );
    setSubCounts(counts);
  };

  useEffect(() => {
    refresh().catch(console.error);
  }, []);

  const handleSubscribe = async (id: string, name: string) => {
    setBusy(id);
    setMsg("");
    const r = await registerPush(id);
    setBusy("");
    if (r.status === "subscribed") {
      setMsg(`✅ ${name} 구독 완료`);
      await refresh();
    } else if (r.status === "already") {
      setMsg(`ℹ️ ${name} 이미 구독됨`);
    } else if (r.status === "denied") {
      setMsg(
        `⚠️ 알림 권한 거부 — Chrome 주소창 좌측 자물쇠 → 알림 → 허용으로 변경 후 재시도`
      );
    } else if (r.status === "unsupported") {
      setMsg(`❌ ${r.message ?? "이 브라우저는 푸시 미지원"}`);
    } else {
      setMsg(`❌ ${r.status}: ${r.message ?? ""}`);
    }
  };

  return (
    <div className="p-6 space-y-5">
      <header>
        <div className="text-xs text-brand font-semibold uppercase tracking-widest">
          TRI-PRO · C-Rehab POC
        </div>
        <h1 className="text-2xl font-bold mt-1">환자앱</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          환자별 푸시 구독 후 어드민에서 알림 발송 가능
        </p>
      </header>

      <section>
        <h2 className="text-sm text-gray-500 mb-2">시연 환자 ({patients.length}명)</h2>
        <div className="space-y-2">
          {patients.length === 0 && (
            <div className="text-sm text-gray-400 p-4 bg-gray-50 rounded-lg">
              백엔드 연결 중... (uvicorn 8000 확인)
            </div>
          )}
          {patients.map((p) => {
            const subscribed = (subCounts[p.id] ?? 0) > 0;
            return (
              <div
                key={p.id}
                className="p-3 border border-gray-200 rounded-xl bg-white"
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold flex items-center gap-2">
                      <span>{p.name}</span>
                      <span className="text-xs text-gray-400">{p.id}</span>
                      {subscribed && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded-full">
                          🔔 구독중 ({subCounts[p.id]})
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">
                      {2026 - p.birth_year}세 · {p.icd10} · 사이클 D{p.cycle_day}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  <Link
                    href={`/pro/start?patient_id=${p.id}`}
                    className="px-2.5 py-1.5 bg-brand text-white rounded-lg text-xs font-semibold"
                  >
                    PRO 시작
                  </Link>
                  <Link
                    href={`/elder/home?patient_id=${p.id}`}
                    className="px-2.5 py-1.5 bg-warn text-white rounded-lg text-xs font-semibold"
                  >
                    어르신
                  </Link>
                  <button
                    onClick={() => handleSubscribe(p.id, p.name)}
                    disabled={busy === p.id}
                    className={`ml-auto px-2.5 py-1.5 rounded-lg text-xs font-semibold border ${
                      subscribed
                        ? "bg-green-50 border-green-300 text-green-700"
                        : "bg-white border-gray-300 text-gray-700"
                    }`}
                  >
                    {busy === p.id
                      ? "..."
                      : subscribed
                      ? "🔔 재구독"
                      : "🔔 푸시 구독"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {msg && (
        <div className="text-xs p-3 bg-yellow-50 text-yellow-900 rounded-lg border border-yellow-200">
          {msg}
        </div>
      )}

      <section className="space-y-2">
        <h2 className="text-sm text-gray-500">기능 메뉴</h2>
        <Link
          href="/talk"
          className="block p-3 bg-brand-soft text-brand-deep rounded-xl text-center font-semibold"
        >
          🤖 LLM 가드레일 시연 (Free Talk)
        </Link>
      </section>

      <footer className="pt-4 border-t border-gray-200 text-xs text-gray-400">
        POC v0.2 · LLM Mock · SQLite · Localhost · 5명 환자
      </footer>
    </div>
  );
}
