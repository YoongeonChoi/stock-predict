"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowRight } from "lucide-react";

import AuthStatus from "@/components/AuthStatus";
import ContactSection from "@/components/ContactSection";
import Navigation from "@/components/Navigation";
import SearchBar from "@/components/SearchBar";
import { ButtonLink } from "@/components/ui";

export default function SiteFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  if (isLanding) {
    return (
      <div className="min-h-screen bg-bg">
        <header className="sticky top-0 z-50 border-b border-border/70 bg-white/90 backdrop-blur-md">
          <div className="mx-auto flex min-h-16 w-full max-w-[1180px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <Link className="min-w-0 text-base font-bold text-text" href="/">
              yoongeon.xyz
            </Link>
            <nav className="hidden items-center gap-7 text-sm font-semibold text-text-secondary md:flex" aria-label="랜딩 내비게이션">
              <a className="transition-colors hover:text-text" href="#features">
                기능
              </a>
              <a className="transition-colors hover:text-text" href="#workflow">
                흐름
              </a>
              <a className="transition-colors hover:text-text" href="#limits">
                기준
              </a>
              <a className="transition-colors hover:text-text" href="#contact-title">
                Contact
              </a>
            </nav>
            <ButtonLink className="hidden sm:inline-flex" href="/dashboard" size="md">
              대시보드 보기
              <ArrowRight size={17} aria-hidden="true" />
            </ButtonLink>
          </div>
        </header>
        <main id="main-content">
          <div className="mx-auto w-full max-w-[1180px] px-4 pb-12 sm:px-6 lg:px-8">
            {children}
            <div className="pb-6 pt-6 sm:pt-10">
              <ContactSection />
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
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
            <div className="mt-[var(--space-section)]">
              <ContactSection />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
