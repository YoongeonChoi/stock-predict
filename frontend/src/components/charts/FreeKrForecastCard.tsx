"use client";

import type { FreeKrForecast } from "@/lib/types";
import { changeColor, formatPrice } from "@/lib/utils";

interface Props {
  forecast: FreeKrForecast;
  assetLabel: string;
  priceKey: string;
}

function regimeLabel(regime: FreeKrForecast["regime"]) {
  if (regime === "risk_on") return "리스크 온";
  if (regime === "risk_off") return "리스크 오프";
  return "중립";
}

function regimeTone(regime: FreeKrForecast["regime"]) {
  if (regime === "risk_on") return "bg-positive/10 text-positive";
  if (regime === "risk_off") return "bg-negative/10 text-negative";
  return "bg-border/60 text-text-secondary";
}

function signalTone(signal: "bullish" | "bearish" | "neutral") {
  if (signal === "bullish") return "text-positive";
  if (signal === "bearish") return "text-negative";
  return "text-text-secondary";
}

function formatRawReturn(value: number) {
  const pct = value * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export default function FreeKrForecastCard({ forecast, assetLabel, priceKey }: Props) {
  const sourcesUsed = forecast.data_sources.filter((item) => item.used);
  const sourcesPending = forecast.data_sources.filter((item) => item.configured && !item.used);

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <h2 className="font-semibold">무료 KR 확률 엔진</h2>
          <p className="text-xs text-text-secondary mt-1">
            {forecast.reference_date} 종가 기준으로 계산한 {assetLabel}의 확률 분포 요약입니다.
          </p>
        </div>
        <div className="text-right">
          <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${regimeTone(forecast.regime)}`}>
            {regimeLabel(forecast.regime)}
          </span>
          <div className="text-xs text-text-secondary mt-2">모델 {forecast.model_version}</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4 text-[11px]">
        <span className="px-2 py-1 rounded-full bg-border/50 text-text-secondary">
          기준가 {formatPrice(forecast.reference_price, priceKey)}
        </span>
        <span className="px-2 py-1 rounded-full bg-border/50 text-text-secondary">
          사용 소스 {sourcesUsed.length}개
        </span>
        {sourcesPending.length > 0 ? (
          <span className="px-2 py-1 rounded-full bg-amber-500/10 text-amber-500">
            대기 중 보강 {sourcesPending.length}개
          </span>
        ) : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
        {forecast.horizons.map((horizon) => (
          <div key={horizon.horizon_days} className="rounded-xl border border-border px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs text-text-secondary">{horizon.horizon_days}거래일</div>
                <div className="text-[11px] text-text-secondary mt-1">{horizon.target_date}</div>
              </div>
              <div className="text-xs text-text-secondary">신뢰 {horizon.confidence.toFixed(0)}/100</div>
            </div>

            <div className="mt-3">
              <div className="text-[11px] text-text-secondary">중심 가격 (q50)</div>
              <div className="text-lg font-bold">{formatPrice(horizon.price_q50, priceKey)}</div>
              <div className={`text-sm mt-1 ${changeColor(horizon.mean_return_raw * 100)}`}>
                기대 {formatRawReturn(horizon.mean_return_raw)}
              </div>
              <div className="text-[11px] text-text-secondary mt-1">
                초과수익 {formatRawReturn(horizon.mean_return_excess)}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 mt-4 text-center">
              <div className="rounded-lg bg-negative/10 px-2 py-2">
                <div className="text-[11px] text-text-secondary">하방</div>
                <div className="font-semibold text-negative">{horizon.p_down.toFixed(1)}%</div>
              </div>
              <div className="rounded-lg bg-border/50 px-2 py-2">
                <div className="text-[11px] text-text-secondary">중립</div>
                <div className="font-semibold">{horizon.p_flat.toFixed(1)}%</div>
              </div>
              <div className="rounded-lg bg-positive/10 px-2 py-2">
                <div className="text-[11px] text-text-secondary">상방</div>
                <div className="font-semibold text-positive">{horizon.p_up.toFixed(1)}%</div>
              </div>
            </div>

            <div className="mt-4 text-xs text-text-secondary space-y-1">
              <div>q10 ~ q90: {formatPrice(horizon.price_q10, priceKey)} ~ {formatPrice(horizon.price_q90, priceKey)}</div>
              <div>예상 변동성: {(horizon.vol_forecast * 100).toFixed(2)}%</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border px-4 py-4">
          <div className="text-xs font-medium text-text-secondary mb-3">핵심 근거</div>
          <div className="space-y-3">
            {forecast.evidence.map((item) => (
              <div key={item.key} className="rounded-lg border border-border/70 px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-sm">{item.label}</div>
                  <div className={`text-xs font-medium ${signalTone(item.signal)}`}>
                    {item.contribution >= 0 ? "+" : ""}{item.contribution.toFixed(3)}
                  </div>
                </div>
                <div className="text-xs text-text-secondary mt-1">{item.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-border px-4 py-4">
            <div className="text-xs font-medium text-text-secondary mb-3">장세 확률</div>
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(forecast.regime_probs).map(([key, value]) => (
                <div key={key} className="rounded-lg bg-border/40 px-3 py-3 text-center">
                  <div className="text-[11px] text-text-secondary">{regimeLabel(key as FreeKrForecast["regime"])}</div>
                  <div className="font-semibold mt-1">{value.toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border px-4 py-4">
            <div className="text-xs font-medium text-text-secondary mb-3">데이터 소스</div>
            <div className="space-y-2">
              {forecast.data_sources.map((item) => (
                <div key={item.name} className="flex items-start justify-between gap-3 text-sm">
                  <div>
                    <div className="font-medium">{item.name}</div>
                    <div className="text-xs text-text-secondary mt-1">{item.note}</div>
                  </div>
                  <div className="text-right text-xs">
                    <div className={item.used ? "text-positive" : item.configured ? "text-amber-500" : "text-text-secondary"}>
                      {item.used ? `${item.item_count}건 반영` : item.configured ? "대기" : "미설정"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border px-4 py-4">
            <div className="text-xs font-medium text-text-secondary mb-2">엔진 메모</div>
            <p className="text-sm text-text-secondary leading-relaxed">{forecast.summary}</p>
            <p className="text-xs text-text-secondary leading-relaxed mt-3">{forecast.confidence_note}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
