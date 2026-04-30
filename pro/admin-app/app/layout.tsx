import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "V.Doc Pro · TRI-PRO Admin",
  description: "C-Rehab POC 의료진 어드민",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen flex flex-col">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-brand font-black text-lg">V.Doc Pro</span>
            <span className="text-xs text-gray-400">| TRI-PRO POC</span>
          </Link>
          <nav className="flex items-center gap-4 text-xs">
            <Link href="/" className="text-gray-600 hover:text-brand">대시보드</Link>
            <Link href="/tools" className="text-gray-600 hover:text-brand">도구 라이브러리</Link>
            <Link href="/jobs" className="text-gray-600 hover:text-brand">Jobs</Link>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="bg-white border-t border-gray-200 px-6 py-2 text-center text-xs text-gray-400">
          POC v0.1 · LLM Mock 모드
        </footer>
      </body>
    </html>
  );
}
