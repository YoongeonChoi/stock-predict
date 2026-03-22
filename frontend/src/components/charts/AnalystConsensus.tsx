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

export default function AnalystConsensus({ buy, hold, sell, targetLow, targetMean, targetHigh, currentPrice }: Props) {
  const total = buy + hold + sell;
  if (total === 0) return null;

  const buyPct = (buy / total) * 100;
  const holdPct = (hold / total) * 100;
  const sellPct = (sell / total) * 100;

  const consensus = buy > sell * 1.5 ? "Strong Buy" : buy > sell ? "Buy" : sell > buy * 1.5 ? "Strong Sell" : sell > buy ? "Sell" : "Hold";
  const consensusColor = consensus.includes("Buy") ? "text-positive" : consensus.includes("Sell") ? "text-negative" : "text-warning";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Analyst Consensus</span>
        <span className={`text-sm font-bold ${consensusColor}`}>{consensus}</span>
      </div>

      <div className="flex h-3 rounded-full overflow-hidden">
        <div className="bg-positive" style={{ width: `${buyPct}%` }} title={`Buy: ${buy}`} />
        <div className="bg-warning" style={{ width: `${holdPct}%` }} title={`Hold: ${hold}`} />
        <div className="bg-negative" style={{ width: `${sellPct}%` }} title={`Sell: ${sell}`} />
      </div>
      <div className="flex justify-between text-xs text-text-secondary">
        <span className="text-positive">Buy {buy} ({buyPct.toFixed(0)}%)</span>
        <span className="text-warning">Hold {hold} ({holdPct.toFixed(0)}%)</span>
        <span className="text-negative">Sell {sell} ({sellPct.toFixed(0)}%)</span>
      </div>

      {targetMean && (
        <div className="mt-3">
          <div className="text-xs text-text-secondary mb-1.5">Price Target Range</div>
          <div className="relative h-8 bg-border/50 rounded-lg">
            {targetLow && targetHigh && targetHigh > targetLow && (
              <>
                <div
                  className="absolute top-1 bottom-1 bg-accent/20 rounded"
                  style={{
                    left: `${Math.max(0, ((targetLow - (targetLow * 0.9)) / ((targetHigh * 1.1) - (targetLow * 0.9))) * 100)}%`,
                    right: `${Math.max(0, 100 - ((targetHigh - (targetLow * 0.9)) / ((targetHigh * 1.1) - (targetLow * 0.9))) * 100)}%`,
                  }}
                />
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-text"
                  style={{ left: `${((currentPrice - (targetLow * 0.9)) / ((targetHigh * 1.1) - (targetLow * 0.9))) * 100}%` }}
                  title={`Current: ${currentPrice}`}
                />
              </>
            )}
          </div>
          <div className="flex justify-between text-[10px] text-text-secondary mt-1">
            <span>Low: {targetLow?.toLocaleString()}</span>
            <span className="font-medium text-accent">Mean: {targetMean.toLocaleString()}</span>
            <span>High: {targetHigh?.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}
