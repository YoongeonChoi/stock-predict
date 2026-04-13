"use client";

import type { NextDayForecast } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

interface Props {
  forecast: NextDayForecast;
  assetLabel: string;
  priceKey: string;
}

function directionLabel(direction: NextDayForecast["direction"]) {
  if (direction === "up") return "상승 우위";
  if (direction === "down") return "하락 우위";
  return "중립";
}

function signalLabel(signal: "bullish" | "bearish" | "neutral") {
  if (signal === "bullish") return "긍정";
  if (signal === "bearish") return "부정";
  return "중립";
}

function scenarioLabel(name: string) {
  if (name === "Bull") return "상방";
  if (name === "Bear") return "하방";
  if (name === "Base") return "기준";
  return name;
}

function executionBiasMeta(bias: NextDayForecast["execution_bias"]) {
  if (bias === "press_long") {
    return { label: "추세 대응", tone: "bg-positive/10 text-positive" };
  }
  if (bias === "lean_long") {
    return { label: "상방 우세", tone: "bg-emerald-500/10 text-emerald-500" };
  }
  if (bias === "reduce_risk") {
    return { label: "리스크 관리", tone: "bg-amber-500/10 text-amber-500" };
  }
  if (bias === "capital_preservation") {
    return { label: "방어 우선", tone: "bg-negative/10 text-negative" };
  }
  return { label: "선별 대응", tone: "bg-border/60 text-text-secondary" };
}

export default function NextDayForecastCard({ forecast, assetLabel, priceKey }: Props) {
  const flow = forecast.flow_signal;
  const scenarios = forecast.scenarios ?? [];
  const riskFlags = forecast.risk_flags ?? [];
  const execution = executionBiasMeta(forecast.execution_bias);
  const rangePct = forecast.reference_price
    ? ((forecast.predicted_high - forecast.predicted_low) / forecast.reference_price) * 100
    : 0;
  const directionTone =
    forecast.direction === "up"
      ? "text-positive"
      : forecast.direction === "down"
        ? "text-negative"
        : "text-warning";

  return (
    <div className="card">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-semibold">다음 거래일 예측</h2>
          <p className="text-xs text-text-secondary mt-1">
            {forecast.reference_date} 종가 기준, {forecast.target_date} 예상 시나리오입니다.
          </p>
        </div>
        <div className="self-start text-left sm:text-right">
          <div className={`text-sm font-semibold tracking-wide ${directionTone}`}>
            {directionLabel(forecast.direction)}
          </div>
          <div className="text-xs text-text-secondary mt-1">
            신뢰도 {forecast.confidence.toFixed(0)} / 100
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4 text-[11px]">
        <span className="px-2 py-1 rounded-full bg-border/50 text-text-secondary">
          모델 {forecast.model_version}
        </span>
        <span className="px-2 py-1 rounded-full bg-border/50 text-text-secondary">
          예상 변동 폭 {rangePct.toFixed(2)}%
        </span>
        <span className={`px-2 py-1 rounded-full ${execution.tone}`}>
          실행 바이어스 {execution.label}
        </span>
        <span className="px-2 py-1 rounded-full bg-border/50 text-text-secondary">
          수급 {flow?.available ? "검증 반영" : "중립 처리"}
        </span>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-5">
        <div className="p-3 rounded-lg bg-border/40">
          <div className="text-[11px] text-text-secondary">기준가</div>
          <div className="font-bold">{formatPrice(forecast.reference_price, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-accent/10">
          <div className="text-[11px] text-text-secondary">예상 종가</div>
          <div className="font-bold">{formatPrice(forecast.predicted_close, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-positive/10">
          <div className="text-[11px] text-text-secondary">예상 고가</div>
          <div className="font-bold text-positive">{formatPrice(forecast.predicted_high, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-negative/10">
          <div className="text-[11px] text-text-secondary">예상 저가</div>
          <div className="font-bold text-negative">{formatPrice(forecast.predicted_low, priceKey)}</div>
        </div>
        <div className="p-3 rounded-lg bg-border/40">
          <div className="text-[11px] text-text-secondary">상승 확률</div>
          <div className={`font-bold ${forecast.up_probability >= 50 ? "text-positive" : "text-negative"}`}>
            {forecast.up_probability.toFixed(1)}%
          </div>
          <div className={`text-[11px] mt-1 ${changeColor(forecast.predicted_return_pct)}`}>
            {formatPct(forecast.predicted_return_pct)}
          </div>
        </div>
      </div>

      {scenarios.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {scenarios.map((scenario) => {
            const scenarioReturnPct = forecast.reference_price
              ? ((scenario.price / forecast.reference_price) - 1) * 100
              : 0;

            return (
              <div key={scenario.name} className="rounded-lg border border-border px-3 py-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-xs text-text-secondary">{scenarioLabel(scenario.name)} 시나리오</div>
                    <div className="font-bold mt-1">{formatPrice(scenario.price, priceKey)}</div>
                  </div>
                  <div className="text-left sm:text-right">
                    <div className="text-sm font-semibold">{scenario.probability.toFixed(1)}%</div>
                    <div className={`text-[11px] mt-1 ${changeColor(scenarioReturnPct)}`}>
                      {formatPct(scenarioReturnPct)}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-text-secondary mt-2 leading-relaxed">{scenario.description}</div>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-medium text-text-secondary mb-2">핵심 드라이버</div>
          <div className="space-y-2">
            {forecast.drivers.map((driver) => (
              <div key={driver.name} className="rounded-lg border border-border px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{driver.name}</span>
                  <span
                    className={`text-xs font-medium ${
                      driver.signal === "bullish"
                        ? "text-positive"
                        : driver.signal === "bearish"
                          ? "text-negative"
                          : "text-warning"
                    }`}
                  >
                    {signalLabel(driver.signal)}
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{driver.detail}</div>
                <div className="text-[11px] text-text-secondary mt-1">
                  기여도 {(driver.contribution * 100).toFixed(1)}bp, 가중치 {(driver.weight * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-lg border border-border px-3 py-3">
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-xs font-medium text-text-secondary">{assetLabel} 실행 해석</div>
              <span className={`self-start px-2 py-1 rounded-full text-[11px] font-medium ${execution.tone}`}>
                {execution.label}
              </span>
            </div>
            <div className="text-sm leading-relaxed text-text-secondary">
              {forecast.execution_note || "방향성 우위가 크지 않아 확인 신호가 더 필요합니다."}
            </div>
          </div>

          <div className="rounded-lg border border-border px-3 py-3">
            <div className="text-xs font-medium text-text-secondary mb-1">{assetLabel} 모델 메모</div>
            <div className="text-sm leading-relaxed text-text-secondary">{forecast.confidence_note}</div>
          </div>

          {riskFlags.length > 0 ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-3">
              <div className="text-xs font-medium text-amber-600 mb-2">리스크 플래그</div>
              <div className="space-y-2">
                {riskFlags.map((flag) => (
                  <div key={flag} className="text-sm text-text-secondary">
                    {flag}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="rounded-lg border border-border px-3 py-3">
            <div className="text-xs font-medium text-text-secondary mb-2">뉴스 / 수급 신호</div>
            <div className="text-sm text-text-secondary mb-2">
              뉴스 심리 {forecast.news_sentiment.toFixed(2)} / 합성 원신호 {forecast.raw_signal.toFixed(2)}
            </div>
            {flow && flow.available ? (
              <div className="text-sm space-y-1">
                <div>외국인: {flow.foreign_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
                <div>기관: {flow.institutional_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
                <div>개인: {flow.retail_net_buy?.toLocaleString() ?? "N/A"} {flow.unit}</div>
              </div>
            ) : (
              <div className="text-sm text-text-secondary">이 시장에서는 검증 가능한 수급 데이터가 부족해 중립 처리했습니다.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
