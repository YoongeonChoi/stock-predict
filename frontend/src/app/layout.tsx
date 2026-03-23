import type { Metadata } from "next";
import Link from "next/link";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import Navigation from "@/components/Navigation";
import SearchBar from "@/components/SearchBar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Stock Predict",
  description: "미국·한국·일본 시장을 위한 AI 기반 주식 분석 플랫폼",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <ToastProvider>
            <div className="flex min-h-screen">
              <Navigation />
              <div className="flex min-w-0 flex-1 flex-col">
                <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/94 shadow-[0_20px_40px_-38px_rgba(15,23,42,0.45)]">
                  <div className="mx-auto flex w-full max-w-[1500px] items-center gap-4 px-4 py-4 sm:px-6 lg:px-8 xl:px-10">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 hidden text-[11px] font-semibold uppercase tracking-[0.2em] text-text-secondary xl:block">
                        Market Workspace
                      </div>
                      <SearchBar />
                    </div>
                    <div className="hidden items-center gap-2 xl:flex">
                      <Link href="/portfolio" className="action-chip-secondary">
                        포트폴리오
                      </Link>
                      <Link href="/radar" className="action-chip-secondary">
                        레이더
                      </Link>
                    </div>
                  </div>
                </header>
                <main className="flex-1">
                  <div className="mx-auto w-full max-w-[1500px] px-4 pb-10 pt-6 sm:px-6 lg:px-8 xl:px-10">
                    {children}
                  </div>
                </main>
              </div>
            </div>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
