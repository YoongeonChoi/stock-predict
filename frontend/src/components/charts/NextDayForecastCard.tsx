"use client";

import type { NextDayForecast } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  forecast: NextDayForecast;
  assetLabel: string;
  priceKey: string;
}

export default function NextDayForecastCard({ forecast, assetLabel, priceKey }: Props) {
  const flow = forecast.flow_signal;
  const directionTone =
    forecast.direction === "up"
      ? "text-positive"
      : forecast.direction === "down"
        ? "text-negative"
        : "text-warning";

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="font-semibold">Next Trading Day Forecast</h2>
          <p className="text-xs text-text-secondary mt-1">
            {forecast.reference_date} close 기준, {forecast.target_date} 예상
          </p>
        </div>
        <div className="text-right">
          <div className={`text-sm font-semibold uppercase tracking-wide ${directionTone}`}>
            {forecast.direction}
          </div>
          <div className="text-xs text-text-secondary mt-1">
            Confidence {forecast.confidence.toFixed(0)} / 100
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div className="p-3 rounded-lg bg-border/40">
          <div className="text-[11px] text-text-secondary">Reference</div>
          <div className="font-bold">{formatPrice(forecast.reference_price, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-accent/10">
          <div className="text-[11px] text-text-secondary">Predicted Close</div>
          <div className="font-bold">{formatPrice(forecast.predicted_close, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-positive/10">
          <div className="text-[11px] text-text-secondary">Predicted High</div>
          <div className="font-bold text-positive">{formatPrice(forecast.predicted_high, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-negative/10">
          <div className="text-[11px] text-text-secondary">Predicted Low</div>
          <div className="font-bold text-negative">{formatPrice(forecast.predicted_low, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-border/40">
          <div className="text-[11px] text-text-secondary">Up Probability</div>
          <div className={`font-bold ${forecast.up_probability >= 50 ? "text-positive" : "text-negative"}`}>
            {forecast.up_probability.toFixed(1)}%
          </div>
          <div className={`text-[11px] mt-1 ${changeColor(forecast.predicted_return_pct)}`}>
            {formatPct(forecast.predicted_return_pct)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-text-secondary mb-2">Top Drivers</div>
          <div className="space-y-2">
            {forecast.drivers.map((driver) => (
              <div key={driver.name} className="rounded-lg border border-border px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{driver.name}</span>
                  <span className={`text-xs font-medium ${
                    driver.signal === "bullish"
                      ? "text-positive"
                      : driver.signal === "bearish"
                        ? "text-negative"
                        : "text-warning"
                  }`}>
                    {driver.signal}
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{driver.detail}</div>
                <div className="text-[11px] text-text-secondary mt-1">
                  contribution {(driver.contribution * 100).toFixed(1)}bp, weight {(driver.weight * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-lg border border-border px-3 py-3">
            <div className="text-xs font-medium text-text-secondary mb-1">{assetLabel} Model Note</div>
            <div className="text-sm leading-relaxed text-text-secondary">{forecast.confidence_note}</div>
          </div>

          <div className="rounded-lg border border-border px-3 py-3">
            <div className="text-xs font-medium text-text-secondary mb-2">News / Flow Signals</div>
            <div className="text-sm text-text-secondary mb-2">
              Headline sentiment {forecast.news_sentiment.toFixed(2)} / raw signal {forecast.raw_signal.toFixed(2)}
            </div>
            {flow && flow.available ? (
              <div className="text-sm space-y-1">
                <div>Foreign: {flow.foreign_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
                <div>Institution: {flow.institutional_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
                <div>Retail: {flow.retail_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
              </div>
            ) : (
              <div className="text-sm text-text-secondary">Verified investor flow unavailable for this market.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
