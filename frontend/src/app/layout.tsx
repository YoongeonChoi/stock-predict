import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans_KR } from "next/font/google";
import { ThemeProvider } from "next-themes";

import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import AuthStatus from "@/components/AuthStatus";
import Navigation from "@/components/Navigation";
import SearchBar from "@/components/SearchBar";
import { ToastProvider } from "@/components/Toast";

const ibmPlexSans = IBM_Plex_Sans_KR({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Stock Predict",
  description: "시장 탐색, 포트폴리오 운영, 예측 검증을 같은 흐름에서 확인하는 투자 분석 워크스페이스",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ko"
      suppressHydrationWarning
      className={`${ibmPlexSans.variable} ${ibmPlexMono.variable}`}
    >
      <body className="min-h-screen bg-bg font-sans text-text">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
        >
          본문으로 바로가기
        </a>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          <ToastProvider>
            <AuthProvider>
              <div className="flex min-h-screen overflow-x-clip">
                <Navigation />
                <div className="flex min-w-0 flex-1 flex-col pt-[var(--mobile-nav-height)] lg:pt-0">
                  <header className="relative z-20 bg-transparent shadow-none lg:sticky lg:top-0 lg:z-30 lg:border-b lg:border-border/12 lg:bg-bg/92 lg:backdrop-blur-sm">
                    <div className="mx-auto grid w-full max-w-[var(--layout-max)] gap-2 px-4 pb-2 pt-2 sm:px-5 sm:pb-3 sm:pt-3 lg:grid-cols-[minmax(0,1fr)_minmax(236px,312px)] lg:items-center lg:gap-4 lg:px-7 lg:py-3 xl:px-8">
                      <div className="min-w-0">
                        <SearchBar />
                      </div>
                      <div className="min-w-0 lg:justify-self-end">
                        <AuthStatus />
                      </div>
                    </div>
                  </header>
                  <main id="main-content" className="flex-1">
                    <div className="mx-auto w-full max-w-[var(--layout-max)] px-4 pb-10 pt-2 sm:px-5 sm:pt-4 lg:px-7 lg:pt-6 xl:px-8">
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
