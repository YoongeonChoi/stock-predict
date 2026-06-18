import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans_KR } from "next/font/google";
import { ThemeProvider } from "next-themes";

import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import SiteFrame from "@/components/SiteFrame";
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

const siteName = "SP";
const siteDescription = "한국 시장 브리핑, 기회 레이더, 스크리너, 포트폴리오 비교를 제공하는 분석 워크스페이스";
const ogImage = {
  url: "/og/sp-og.png",
  width: 1200,
  height: 630,
  alt: "SP 시장 분석 워크스페이스 대표 이미지",
};

export const metadata: Metadata = {
  metadataBase: new URL("https://www.yoongeon.xyz"),
  applicationName: siteName,
  title: {
    default: "SP | yoongeon.xyz",
    template: "%s | SP",
  },
  description: siteDescription,
  openGraph: {
    title: "SP",
    description: siteDescription,
    url: "/",
    siteName,
    locale: "ko_KR",
    type: "website",
    images: [ogImage],
  },
  twitter: {
    card: "summary_large_image",
    title: "SP",
    description: siteDescription,
    images: [ogImage.url],
  },
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
              <SiteFrame>{children}</SiteFrame>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
