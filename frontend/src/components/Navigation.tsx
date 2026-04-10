"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Archive,
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  Crosshair,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  ListFilter,
  Menu,
  MoonStar,
  Settings2,
  Star,
  SunMedium,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_GROUPS = [
  {
    title: "시장 탐색",
    items: [
      { href: "/", label: "대시보드", description: "시장 흐름과 오늘의 핵심 판단", icon: LayoutDashboard },
      { href: "/radar", label: "기회 레이더", description: "지금 바로 볼 후보와 실행 흐름", icon: Crosshair },
      { href: "/screener", label: "스크리너", description: "조건 기반 종목 필터링", icon: ListFilter },
      { href: "/compare", label: "비교", description: "종목 2~4개 정면 비교", icon: GitCompareArrows },
    ],
  },
  {
    title: "운영",
    items: [
      { href: "/portfolio", label: "포트폴리오", description: "보유 종목과 추천 운영", icon: BriefcaseBusiness },
      { href: "/watchlist", label: "관심종목", description: "추적 후보와 빠른 접근", icon: Star },
      { href: "/calendar", label: "캘린더", description: "정책, 지표, 실적 일정", icon: CalendarDays },
      { href: "/archive", label: "아카이브", description: "과거 리포트와 예측 기록", icon: Archive },
    ],
  },
  {
    title: "리서치",
    items: [
      { href: "/lab", label: "예측 연구실", description: "표본 수집과 검증 흐름", icon: FlaskConical },
      { href: "/settings", label: "설정 및 시스템", description: "계정, 진단, 운영 상태", icon: Settings2 },
    ],
  },
];

export default function Navigation() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [themeReady, setThemeReady] = useState(false);

  useEffect(() => {
    setThemeReady(true);
  }, []);

  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = mobileOpen ? "hidden" : originalOverflow;
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [mobileOpen]);

  const isDarkMode = themeReady && theme === "dark";
  const themeButtonLabel = isDarkMode ? "라이트 모드로 전환" : "다크 모드로 전환";

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const navLinks = (
    <div className="space-y-7 pb-4">
      {NAV_GROUPS.map((group) => (
        <section key={group.title}>
          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">
            {group.title}
          </div>
          <div className="mt-3 border-t border-border/10">
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "grid grid-cols-[18px_minmax(0,1fr)_16px] items-start gap-3 border-b border-border/10 py-3 transition-colors",
                    active ? "text-text" : "text-text-secondary hover:text-text",
                  )}
                >
                  <Icon size={17} strokeWidth={2.1} className={cn("mt-0.5", active ? "text-accent" : "text-text-secondary")} />
                  <span className="min-w-0">
                    <span className={cn("block text-[0.95rem] font-semibold tracking-tight", active ? "text-text" : "")}>
                      {item.label}
                    </span>
                    <span className="mt-1 block text-[0.8rem] leading-5 text-text-secondary">
                      {item.description}
                    </span>
                  </span>
                  <ChevronRight size={15} className={cn("mt-0.5", active ? "text-accent" : "text-text-secondary")} />
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );

  return (
    <>
      <aside className="hidden lg:flex lg:w-[288px] lg:shrink-0 xl:w-[304px]">
        <div className="sticky top-0 flex h-screen w-full flex-col border-r border-border/12 bg-bg px-5 py-5">
          <Link href="/" className="border-b border-border/12 pb-5">
            <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">Stock Predict</div>
            <div className="mt-2 text-[1.45rem] font-semibold tracking-tight text-text">시장 탐색과 운영을 한 흐름으로</div>
            <div className="mt-2 max-w-[18rem] text-[0.86rem] leading-6 text-text-secondary">
              숫자, 일정, 후보, 검증 흐름을 더 적은 프레임과 더 큰 위계로 보여주는 투자 워크스페이스.
            </div>
          </Link>

          <div className="mt-6 min-h-0 flex-1 overflow-y-auto pr-1">
            <nav>{navLinks}</nav>
          </div>

          <div className="border-t border-border/12 pt-4">
            <button
              onClick={() => setTheme(isDarkMode ? "light" : "dark")}
              className="ui-button-secondary w-full justify-between px-4"
              aria-label={themeButtonLabel}
            >
              <span className="flex items-center gap-2">
                {isDarkMode ? <SunMedium size={16} /> : <MoonStar size={16} />}
                {isDarkMode ? "라이트 테마" : "다크 테마"}
              </span>
              <ChevronRight size={15} className="text-text-secondary" />
            </button>
          </div>
        </div>
      </aside>

      <div
        className="fixed left-0 right-0 top-0 z-50 flex min-h-[var(--mobile-nav-height)] items-center justify-between border-b border-border/12 bg-bg/98 px-4 pb-2 pt-2 backdrop-blur-md lg:hidden"
        style={{ paddingTop: "max(0.55rem, env(safe-area-inset-top))" }}
      >
        <Link href="/" className="min-w-0 flex-1 pr-3">
          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.15em] text-text-secondary" translate="no">
            Stock Predict
          </div>
          <div className="mt-1 truncate text-[0.84rem] font-semibold tracking-tight text-text">
            시장 탐색과 운영
          </div>
        </Link>
        <div className="flex items-center gap-2 pl-3">
          <button
            onClick={() => setTheme(isDarkMode ? "light" : "dark")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] border border-border/15 bg-surface text-text-secondary"
            aria-label={themeButtonLabel}
          >
            {isDarkMode ? <SunMedium size={17} /> : <MoonStar size={17} />}
          </button>
          <button
            onClick={() => setMobileOpen((value) => !value)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] border border-border/15 bg-surface text-text"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 overflow-hidden lg:hidden">
          <button
            aria-label="메뉴 닫기"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-slate-950/48"
          />
          <div
            className="relative h-full w-[min(88vw,360px)] overflow-y-auto overscroll-contain border-r border-border/12 bg-bg px-5 pb-8"
            style={{ paddingTop: "calc(var(--mobile-nav-height) + 0.55rem)" }}
          >
            <div className="border-b border-border/12 pb-4">
              <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">Menu</div>
              <div className="mt-2 text-[1.2rem] font-semibold tracking-tight text-text">탐색, 운영, 검증 흐름</div>
            </div>
            <nav className="mt-5">{navLinks}</nav>
          </div>
        </div>
      ) : null}
    </>
  );
}
