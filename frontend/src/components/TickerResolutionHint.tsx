import type { TickerResolution } from "@/lib/api";

interface TickerResolutionHintProps {
  resolution: TickerResolution | null;
}

export default function TickerResolutionHint({ resolution }: TickerResolutionHintProps) {
  if (!resolution || !resolution.ticker) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3 text-sm text-text-secondary">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="font-medium text-text">표준 티커 {resolution.ticker}</span>
        <span className="info-chip">{resolution.country_code} · {resolution.confidence}</span>
      </div>
      <div className="mt-2">{resolution.note}</div>
      {resolution.name ? <div className="mt-1 text-xs">인식 종목명: {resolution.name}</div> : null}
    </div>
  );
}
