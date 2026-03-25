import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number | undefined | null, decimals = 2): string {
  if (n == null) return "N/A";
  if (Math.abs(n) >= 1e12) return `${(n / 1e12).toFixed(1)}T`;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

export function formatPct(n: number | undefined | null): string {
  if (n == null) return "N/A";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function scoreColor(score: number, max: number): string {
  const pct = score / max;
  if (pct >= 0.8) return "text-emerald-500";
  if (pct >= 0.6) return "text-green-500";
  if (pct >= 0.4) return "text-yellow-500";
  if (pct >= 0.2) return "text-orange-500";
  return "text-red-500";
}

export function changeColor(pct: number): string {
  if (pct > 0) return "text-positive";
  if (pct < 0) return "text-negative";
  return "text-text-secondary";
}

export function currencySymbol(countryOrTicker: string): string {
  const v = countryOrTicker.toUpperCase();
  if (v === "KR" || v.endsWith(".KS") || v.endsWith(".KQ")) return "₩";
  return "$";
}

export function formatPrice(n: number | undefined | null, countryOrTicker: string): string {
  if (n == null) return "N/A";
  const sym = currencySymbol(countryOrTicker);
  if (sym === "₩") return `₩${Math.round(n).toLocaleString()}`;
  if (sym === "¥") return `¥${Math.round(n).toLocaleString()}`;
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatMarketCap(n: number | undefined | null, countryOrTicker?: string): string {
  if (n == null) return "N/A";
  const sym = countryOrTicker ? currencySymbol(countryOrTicker) : "$";
  if (Math.abs(n) >= 1e12) return `${sym}${(n / 1e12).toFixed(1)}T`;
  if (Math.abs(n) >= 1e9) return `${sym}${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${sym}${(n / 1e6).toFixed(1)}M`;
  return `${sym}${n.toLocaleString()}`;
}
