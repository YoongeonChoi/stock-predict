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
              <div className="flex min-h-screen">
                <Navigation />
                <div className="flex min-w-0 flex-1 flex-col">
                  <header className="border-b border-border/70 bg-surface/92 backdrop-blur-sm shadow-[0_18px_36px_-32px_rgba(15,23,42,0.24)] lg:sticky lg:top-0 lg:z-30">
                    <div className="mx-auto grid w-full max-w-[1500px] gap-3 px-4 py-3 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-4 lg:px-8 xl:px-10">
                      <div className="min-w-0">
                        <SearchBar />
                      </div>
                      <div className="min-w-0 lg:justify-self-end">
                        <AuthStatus />
                      </div>
                    </div>
                  </header>
                  <main className="flex-1">
                    <div className="mx-auto w-full max-w-[1500px] px-4 pb-10 pt-5 sm:px-6 sm:pt-6 lg:px-8 xl:px-10">
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
