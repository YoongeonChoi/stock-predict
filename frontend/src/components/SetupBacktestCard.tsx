"use client";

import type { SetupBacktest } from "@/lib/types";
import { changeColor, formatPct } from "@/lib/utils";

interface Props {
  backtest: SetupBacktest;
}

export default function SetupBacktestCard({ backtest }: Props) {
  return (
    <div className="card">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-semibold">셋업 백테스트</h2>
          <p className="text-sm text-text-secondary mt-1 leading-relaxed">{backtest.summary}</p>
        </div>
        <div className="self-start text-left sm:text-right">
          <div className="text-xs text-text-secondary">셋업</div>
          <div className="font-medium">{backtest.setup_label}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs text-text-secondary">표본 수</div>
          <div className="text-lg font-semibold mt-1">{backtest.sample_size}</div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs text-text-secondary">{backtest.forward_horizon_days}일 승률</div>
          <div className="text-lg font-semibold mt-1">{backtest.win_rate.toFixed(1)}%</div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs text-text-secondary">평균 수익률</div>
          <div className={`text-lg font-semibold mt-1 ${changeColor(backtest.avg_return_pct)}`}>
            {formatPct(backtest.avg_return_pct)}
          </div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs text-text-secondary">신뢰도</div>
          <div className="text-lg font-semibold mt-1">{backtest.confidence.toFixed(1)}</div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5 text-sm">
        <div className="rounded-xl bg-border/20 p-3">
          <div className="text-xs text-text-secondary">중간값 수익률</div>
          <div className={`font-semibold mt-1 ${changeColor(backtest.median_return_pct)}`}>
            {formatPct(backtest.median_return_pct)}
          </div>
        </div>
        <div className="rounded-xl bg-border/20 p-3">
          <div className="text-xs text-text-secondary">평균 최대 낙폭</div>
          <div className={`font-semibold mt-1 ${changeColor(backtest.avg_max_drawdown_pct)}`}>
            {formatPct(backtest.avg_max_drawdown_pct)}
          </div>
        </div>
        <div className="rounded-xl bg-border/20 p-3">
          <div className="text-xs text-text-secondary">최고 수익</div>
          <div className={`font-semibold mt-1 ${changeColor(backtest.best_return_pct)}`}>
            {formatPct(backtest.best_return_pct)}
          </div>
        </div>
        <div className="rounded-xl bg-border/20 p-3">
          <div className="text-xs text-text-secondary">최저 수익</div>
          <div className={`font-semibold mt-1 ${changeColor(backtest.worst_return_pct)}`}>
            {formatPct(backtest.worst_return_pct)}
          </div>
        </div>
        <div className="rounded-xl bg-border/20 p-3">
          <div className="text-xs text-text-secondary">프로핏 팩터</div>
          <div className="font-semibold mt-1">
            {backtest.profit_factor != null ? backtest.profit_factor.toFixed(2) : "없음"}
          </div>
        </div>
      </div>
    </div>
  );
}
