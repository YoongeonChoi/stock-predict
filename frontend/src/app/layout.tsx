import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import Navigation from "@/components/Navigation";
import SearchBar from "@/components/SearchBar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "Stock Predict",
  description: "AI-powered stock market analysis for US, KR, JP markets",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <ToastProvider>
            <div className="flex min-h-screen">
              <Navigation />
              <main className="flex-1 overflow-auto">
                <div className="px-6 lg:px-8 pt-4 pb-2">
                  <SearchBar />
                </div>
                <div className="px-6 lg:px-8 pb-8">{children}</div>
              </main>
            </div>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
