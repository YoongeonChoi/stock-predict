"use client";

import type { HistoricalPatternForecast } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  forecast: HistoricalPatternForecast;
  priceKey: string;
}

export default function HistoricalPatternCard({ forecast, priceKey }: Props) {
  return (
    <div className="card">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-semibold">과거 유사 국면 예측</h2>
          <p className="text-sm text-text-secondary mt-1 leading-relaxed">{forecast.summary}</p>
        </div>
        <div className="self-start text-left sm:text-right">
          <div className="text-xs text-text-secondary">모델</div>
          <div className="font-mono text-sm">{forecast.model_version}</div>
          <div className="text-xs text-text-secondary mt-1">유사 국면 {forecast.analog_count}건</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {forecast.horizons.map((horizon) => (
          <div key={horizon.horizon_days} className="rounded-xl border border-border p-4 bg-border/20">
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">{horizon.horizon_days}거래일</div>
              <span className={`text-sm font-semibold ${changeColor(horizon.expected_return_pct)}`}>
                {formatPct(horizon.expected_return_pct)}
              </span>
            </div>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">상승 확률</span>
                <span>{horizon.up_probability.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">예상 가격</span>
                <span>{formatPrice(horizon.predicted_price, priceKey)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">예상 범위</span>
                <span>
                  {formatPrice(horizon.range_low, priceKey)} ~ {formatPrice(horizon.range_high, priceKey)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">중간값 수익률</span>
                <span>{formatPct(horizon.median_return_pct)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">평균 최대 낙폭</span>
                <span className={changeColor(horizon.avg_max_drawdown_pct)}>
                  {formatPct(horizon.avg_max_drawdown_pct)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">실현 변동성</span>
                <span>{horizon.realized_volatility_pct.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">신뢰도</span>
                <span>{horizon.confidence.toFixed(1)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-border p-4">
        <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-medium">가장 비슷했던 과거 장면</div>
            <div className="text-xs text-text-secondary mt-1">현재와 유사한 국면의 이후 수익률을 빠르게 비교할 수 있습니다.</div>
          </div>
          <div className="self-start text-xs text-text-secondary">현재 셋업: {forecast.feature_regime}</div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-sm">
          {forecast.analog_cases.map((item) => (
            <div key={item.date} className="rounded-lg bg-border/20 px-3 py-3">
              <div className="font-medium">{item.date}</div>
              <div className="text-xs text-text-secondary mt-1">유사도 {item.similarity.toFixed(3)}</div>
              <div className="mt-2 space-y-1">
                <div className={changeColor(item.return_5d ?? 0)}>5일 {formatPct(item.return_5d ?? 0)}</div>
                <div className={changeColor(item.return_20d ?? 0)}>20일 {formatPct(item.return_20d ?? 0)}</div>
                <div className={changeColor(item.return_60d ?? 0)}>60일 {formatPct(item.return_60d ?? 0)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
