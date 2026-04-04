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
      { href: "/", label: "대시보드", description: "선택 시장 현황과 핵심 흐름", icon: LayoutDashboard },
      { href: "/radar", label: "기회 레이더", description: "지금 가장 강한 셋업 탐색", icon: Crosshair },
      { href: "/screener", label: "스크리너", description: "조건 기반 종목 필터링", icon: ListFilter },
      { href: "/compare", label: "비교", description: "종목 2~4개 나란히 비교", icon: GitCompareArrows },
    ],
  },
  {
    title: "운영",
    items: [
      { href: "/portfolio", label: "포트폴리오", description: "자산과 보유 종목 운영", icon: BriefcaseBusiness },
      { href: "/watchlist", label: "관심종목", description: "후보 추적과 빠른 접근", icon: Star },
      { href: "/calendar", label: "캘린더", description: "실적·거시 이벤트 일정", icon: CalendarDays },
      { href: "/archive", label: "아카이브", description: "과거 리포트와 예측 기록", icon: Archive },
    ],
  },
  {
    title: "리서치",
    items: [
      { href: "/lab", label: "예측 연구실", description: "적중률과 calibration 점검", icon: FlaskConical },
      { href: "/settings", label: "설정 및 시스템", description: "시장 세션과 시스템 상태", icon: Settings2 },
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
    <div className="space-y-7 pb-3">
      {NAV_GROUPS.map((group) => (
        <div key={group.title}>
          <div className="break-words px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
            {group.title}
          </div>
          <div className="mt-2.5 space-y-2">
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "group flex min-h-[var(--touch-target-min)] items-start gap-3 rounded-[24px] border px-3.5 py-3.5 transition-all",
                    active
                      ? "border-accent/25 bg-accent/10 text-text shadow-[0_18px_38px_-30px_rgba(37,99,235,0.25)]"
                      : "border-transparent text-text-secondary hover:border-border hover:bg-white/55 hover:text-text dark:hover:bg-slate-900/42",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-11 w-11 shrink-0 items-center justify-center rounded-[20px] border transition-colors",
                      active
                        ? "border-accent/20 bg-accent/15 text-accent"
                        : "border-border bg-surface/50 text-text-secondary group-hover:text-text",
                    )}
                  >
                    <Icon size={18} strokeWidth={2.1} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className={cn("break-words text-[0.95rem] font-semibold", active ? "text-text" : "")}>{item.label}</span>
                      <ChevronRight
                        size={16}
                        className={cn("transition-transform group-hover:translate-x-0.5", active ? "text-accent" : "text-text-secondary")}
                      />
                    </span>
                    <span className="mt-1 block break-words text-[0.82rem] leading-5 text-text-secondary">{item.description}</span>
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <>
      <aside className="hidden lg:flex lg:w-[312px] lg:shrink-0 xl:w-[324px]">
        <div className="sticky top-0 flex h-screen w-full flex-col border-r border-border/70 bg-surface px-4 py-5 shadow-[0_24px_48px_-42px_rgba(15,23,42,0.22)] xl:px-5">
          <Link href="/" className="flex items-center gap-3 rounded-[24px] border border-border/70 bg-surface/76 px-4 py-3.5 transition-colors hover:border-accent/35">
            <span className="flex h-11 w-11 items-center justify-center rounded-[20px] bg-accent/10 text-sm font-semibold text-accent">
              SP
            </span>
            <div className="min-w-0">
              <div className="text-[1rem] font-semibold tracking-tight text-text">Stock Predict</div>
              <div className="mt-0.5 text-[0.78rem] text-text-secondary">분석과 운영을 한 흐름으로 잇는 워크스페이스</div>
            </div>
          </Link>

          <div className="mt-6 min-h-0 flex-1 overflow-y-auto pr-1.5">
            <nav>{navLinks}</nav>
          </div>

          <div className="mt-6 ui-panel-muted">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">테마</div>
            <button
              onClick={() => setTheme(isDarkMode ? "light" : "dark")}
              className="ui-button-secondary mt-3 flex w-full items-center justify-between px-4"
            >
              <span className="flex items-center gap-3">
                <span className="flex h-[17px] w-[17px] items-center justify-center">
                  {isDarkMode ? <SunMedium size={17} /> : <MoonStar size={17} />}
                </span>
                {themeButtonLabel}
              </span>
              <ChevronRight size={16} className="text-text-secondary" />
            </button>
          </div>
        </div>
      </aside>

      <div
        className="fixed left-0 right-0 top-0 z-50 flex min-h-[var(--mobile-nav-height)] items-center justify-between border-b border-border/70 bg-surface/98 px-4 pb-3 pt-3 shadow-[0_18px_36px_-30px_rgba(15,23,42,0.28)] backdrop-blur-md lg:hidden"
        style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}
      >
        <Link href="/" className="min-w-0 flex-1 pr-3">
          <div className="text-[0.98rem] font-semibold tracking-tight text-text">Stock Predict</div>
          <div className="mt-0.5 truncate text-[0.72rem] text-text-secondary">시장 탐색과 운영 흐름</div>
        </Link>
        <div className="flex items-center gap-2 pl-3">
          <button
            onClick={() => setTheme(isDarkMode ? "light" : "dark")}
            className="flex h-11 w-11 items-center justify-center rounded-[20px] border border-border bg-surface/74 text-text-secondary"
            aria-label={themeButtonLabel}
          >
            <span className="flex h-[17px] w-[17px] items-center justify-center">
              {isDarkMode ? <SunMedium size={17} /> : <MoonStar size={17} />}
            </span>
          </button>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="flex h-11 w-11 items-center justify-center rounded-[20px] border border-border bg-surface/74 text-text"
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 overflow-hidden lg:hidden">
          <button
            aria-label="메뉴 닫기"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-[2px]"
          />
          <div
            className="relative h-full w-[min(88vw,348px)] overflow-y-auto overscroll-contain border-r border-border/70 bg-surface px-4 pb-8 shadow-[0_28px_60px_-40px_rgba(15,23,42,0.55)]"
            style={{ paddingTop: "calc(var(--mobile-nav-height) + 0.75rem)" }}
          >
            <div className="ui-panel-muted">
              <div className="text-sm font-semibold text-text">메뉴</div>
              <div className="mt-1 text-xs leading-6 text-text-secondary">탐색, 운영, 리서치 흐름을 한 곳에서 이동합니다.</div>
            </div>
            <nav className="mt-4">{navLinks}</nav>
          </div>
        </div>
      )}
    </>
  );
}
