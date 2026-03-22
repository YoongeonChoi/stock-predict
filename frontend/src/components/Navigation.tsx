"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: "◈" },
  { href: "/screener", label: "Screener", icon: "⊞" },
  { href: "/portfolio", label: "Portfolio", icon: "◉" },
  { href: "/watchlist", label: "Watchlist", icon: "★" },
  { href: "/compare", label: "Compare", icon: "⇄" },
  { href: "/archive", label: "Archive", icon: "▤" },
  { href: "/calendar", label: "Calendar", icon: "▦" },
];

export default function Navigation() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navLinks = (
    <>
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={() => setMobileOpen(false)}
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
            pathname === item.href
              ? "bg-accent/10 text-accent font-medium"
              : "text-text-secondary hover:text-text hover:bg-surface"
          )}
        >
          <span className="text-base">{item.icon}</span>
          {item.label}
        </Link>
      ))}
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-56 border-r border-border bg-surface px-3 py-6 shrink-0">
        <Link href="/" className="text-lg font-semibold tracking-tight px-3 mb-8">
          Stock Predict
        </Link>
        <nav className="flex flex-col gap-1 flex-1">{navLinks}</nav>
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="px-3 py-2 text-sm text-text-secondary hover:text-text transition-colors"
        >
          {theme === "dark" ? "☀ Light" : "☾ Dark"}
        </button>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-3 bg-surface border-b border-border">
        <Link href="/" className="font-semibold text-sm">Stock Predict</Link>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="text-sm text-text-secondary"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <button onClick={() => setMobileOpen(!mobileOpen)} className="text-lg">
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-bg/90 pt-14">
          <nav className="flex flex-col gap-1 p-4">{navLinks}</nav>
        </div>
      )}

      {/* Mobile spacer */}
      <div className="lg:hidden h-14 shrink-0" />
    </>
  );
}
