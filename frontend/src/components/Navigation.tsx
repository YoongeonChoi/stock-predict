"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: "◈" },
  { href: "/watchlist", label: "Watchlist", icon: "★" },
  { href: "/compare", label: "Compare", icon: "⇄" },
  { href: "/archive", label: "Archive", icon: "▤" },
  { href: "/calendar", label: "Calendar", icon: "▦" },
];

export default function Navigation() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  return (
    <aside className="hidden lg:flex flex-col w-56 border-r border-border bg-surface px-3 py-6 shrink-0">
      <Link href="/" className="text-lg font-semibold tracking-tight px-3 mb-8">
        Stock Predict
      </Link>

      <nav className="flex flex-col gap-1 flex-1">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
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
      </nav>

      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className="px-3 py-2 text-sm text-text-secondary hover:text-text transition-colors"
      >
        {theme === "dark" ? "☀ Light" : "☾ Dark"}
      </button>
    </aside>
  );
}
