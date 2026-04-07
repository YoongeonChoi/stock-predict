import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import AuthStatus from "@/components/AuthStatus";
import Navigation from "@/components/Navigation";
import SearchBar from "@/components/SearchBar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Stock Predict",
  description: "시장 탐색, 포트폴리오 운영, 예측 검증을 한 흐름으로 이어주는 투자 분석 워크스페이스",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <ToastProvider>
            <AuthProvider>
              <div className="flex min-h-screen overflow-x-clip">
                <Navigation />
                <div className="flex min-w-0 flex-1 flex-col pt-[var(--mobile-nav-height)] lg:pt-0">
                  <header className="relative z-20 bg-transparent shadow-none lg:sticky lg:top-0 lg:z-30 lg:border-b lg:border-border/70 lg:bg-surface/92 lg:shadow-[0_18px_36px_-32px_rgba(15,23,42,0.24)] lg:backdrop-blur-sm">
                    <div className="mx-auto grid w-full max-w-[1500px] gap-2 px-4 pb-2 pt-3 sm:px-6 sm:pt-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-4 lg:px-8 lg:py-3 xl:px-10">
                      <div className="min-w-0">
                        <SearchBar />
                      </div>
                      <div className="min-w-0 lg:justify-self-end">
                        <AuthStatus />
                      </div>
                    </div>
                  </header>
                  <main className="flex-1">
                    <div className="mx-auto w-full max-w-[1500px] px-4 pb-10 pt-3 sm:px-6 sm:pt-5 lg:px-8 lg:pt-6 xl:px-10">
                      {children}
                    </div>
                  </main>
                </div>
              </div>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
