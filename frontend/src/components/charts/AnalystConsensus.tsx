"use client";

interface Props {
  buy: number;
  hold: number;
  sell: number;
  targetLow: number | null;
  targetMean: number | null;
  targetHigh: number | null;
  currentPrice: number;
}

function consensusLabel(buy: number, sell: number) {
  if (buy > sell * 1.5) return "강한 매수";
  if (buy > sell) return "매수 우위";
  if (sell > buy * 1.5) return "강한 매도";
  if (sell > buy) return "매도 우위";
  return "중립";
}

function consensusColor(label: string) {
  if (label.includes("매수")) return "text-positive";
  if (label.includes("매도")) return "text-negative";
  return "text-warning";
}

export default function AnalystConsensus({ buy, hold, sell, targetLow, targetMean, targetHigh, currentPrice }: Props) {
  const total = buy + hold + sell;
  if (total === 0) return null;

  const buyPct = (buy / total) * 100;
  const holdPct = (hold / total) * 100;
  const sellPct = (sell / total) * 100;
  const consensus = consensusLabel(buy, sell);
  const rangeMin = targetLow ?? currentPrice * 0.9;
  const rangeMax = targetHigh ?? currentPrice * 1.1;
  const rangeSpan = Math.max(rangeMax - rangeMin, 1);
  const currentLeft = ((currentPrice - rangeMin) / rangeSpan) * 100;
  const lowLeft = targetLow != null ? ((targetLow - rangeMin) / rangeSpan) * 100 : 0;
  const highLeft = targetHigh != null ? ((targetHigh - rangeMin) / rangeSpan) * 100 : 100;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">애널리스트 컨센서스</span>
        <span className={`text-sm font-bold ${consensusColor(consensus)}`}>{consensus}</span>
      </div>

      <div className="flex h-3 rounded-full overflow-hidden">
        <div className="bg-positive" style={{ width: `${buyPct}%` }} title={`매수: ${buy}`} />
        <div className="bg-warning" style={{ width: `${holdPct}%` }} title={`보유: ${hold}`} />
        <div className="bg-negative" style={{ width: `${sellPct}%` }} title={`매도: ${sell}`} />
      </div>
      <div className="flex justify-between text-xs text-text-secondary">
        <span className="text-positive">매수 {buy} ({buyPct.toFixed(0)}%)</span>
        <span className="text-warning">보유 {hold} ({holdPct.toFixed(0)}%)</span>
        <span className="text-negative">매도 {sell} ({sellPct.toFixed(0)}%)</span>
      </div>

      {targetMean ? (
        <div className="mt-3">
          <div className="text-xs text-text-secondary mb-1.5">목표가 범위</div>
          <div className="relative h-8 bg-border/50 rounded-lg overflow-hidden">
            {targetLow != null && targetHigh != null && targetHigh > targetLow ? (
              <div className="absolute top-1 bottom-1 bg-accent/20 rounded" style={{ left: `${Math.max(0, lowLeft)}%`, right: `${Math.max(0, 100 - highLeft)}%` }} />
            ) : null}
            <div className="absolute top-0 bottom-0 w-0.5 bg-text" style={{ left: `${Math.min(100, Math.max(0, currentLeft))}%` }} title={`현재가: ${currentPrice}`} />
          </div>
          <div className="flex justify-between text-[10px] text-text-secondary mt-1">
            <span>하단: {targetLow?.toLocaleString() ?? "미정"}</span>
            <span className="font-medium text-accent">평균: {targetMean.toLocaleString()}</span>
            <span>상단: {targetHigh?.toLocaleString() ?? "미정"}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}