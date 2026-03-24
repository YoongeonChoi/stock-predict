"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import PageHeader from "@/components/PageHeader";
import PortfolioModelPanel from "@/components/PortfolioModelPanel";
import PortfolioEventRadar from "@/components/PortfolioEventRadar";
import PortfolioRiskPanel from "@/components/PortfolioRiskPanel";
import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import { ApiError, api } from "@/lib/api";
import type { PortfolioData, PortfolioEventRadarResponse, TickerResolution } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

const COLORS = ["#0f766e", "#2563eb", "#f59e0b", "#ef4444", "#7c3aed", "#ec4899", "#0891b2", "#65a30d"];

const TICKER_GUIDE = {
  KR: {
    label: "한국",
    placeholder: "005930",
    helper: "숫자 6자리만 입력해도 자동으로 `.KS` 또는 `.KQ` 형식으로 저장합니다.",
    examples: ["005930", "196170"],
  },
  US: {
    label: "미국",
    placeholder: "AAPL",
    helper: "미국 종목은 일반 티커 그대로 입력하면 됩니다.",
    examples: ["AAPL", "MSFT"],
  },
  JP: {
    label: "일본",
    placeholder: "7203",
    helper: "숫자 4자리를 입력하면 자동으로 `.T` 형식으로 저장합니다.",
    examples: ["7203", "6758"],
  },
} as const;

function getApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.detail) {
      return `${error.errorCode} · ${error.detail}`;
    }
    return `${error.errorCode} · ${error.message}`;
  }
  return fallback;
}

function riskLevelLabel(level: string) {
  if (level === "high") return "높음";
  if (level === "medium") return "보통";
  return "낮음";
}

function tradeActionLabel(action?: string | null) {
  if (action === "accumulate") return "분할 매수";
  if (action === "reduce_risk") return "리스크 축소";
  if (action === "breakout_watch") return "돌파 감시";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "avoid") return "관망";
  return "없음";
}

function executionBiasLabel(bias?: string | null) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: string | null) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
}

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [ticker, setTicker] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [qty, setQty] = useState("");
  const [buyDate, setBuyDate] = useState(new Date().toISOString().slice(0, 10));
  const [countryCode, setCountryCode] = useState("KR");
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const [eventRadar, setEventRadar] = useState<PortfolioEventRadarResponse | null>(null);
  const { toast } = useToast();

  const load = async (showFailureToast = false) => {
    setLoading(true);
    try {
      const next = await api.getPortfolio();
      setData(next);
    } catch (error) {
      console.error(error);
      if (showFailureToast) {
        toast(getApiErrorMessage(error, "포트폴리오를 다시 불러오지 못했습니다."), "error");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    api.getPortfolio()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
    api.getPortfolioEventRadar(14).then(setEventRadar).catch(console.error);
  }, []);

  useEffect(() => {
    const trimmed = ticker.trim();
    if (!trimmed) {
      setResolution(null);
      return;
    }
    const timer = setTimeout(() => {
      api.resolveTicker(trimmed, countryCode).then(setResolution).catch(() => setResolution(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [ticker, countryCode]);

  const addHolding = async () => {
    const trimmedTicker = ticker.trim();
    const parsedBuyPrice = Number(buyPrice);
    const parsedQty = Number(qty);

    if (!trimmedTicker) {
      const message = "티커를 먼저 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }
    if (!Number.isFinite(parsedBuyPrice) || parsedBuyPrice <= 0) {
      const message = "매수가는 0보다 큰 숫자로 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }
    if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
      const message = "수량은 0보다 큰 숫자로 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }

    setSubmitting(true);
    setFormError("");
    try {
      const saved = await api.addPortfolioHolding({
        ticker: trimmedTicker.toUpperCase(),
        buy_price: parsedBuyPrice,
        quantity: parsedQty,
        buy_date: buyDate,
        country_code: countryCode,
      });
      setTicker("");
      setBuyPrice("");
      setQty("");
      await load();
      const radar = await api.getPortfolioEventRadar(14).catch(() => null);
      if (radar) setEventRadar(radar);
      setResolution(null);
      toast(`${saved.name} (${saved.ticker}) 종목을 포트폴리오에 추가했습니다.`, "success");
    } catch (error) {
      console.error(error);
      const message = getApiErrorMessage(error, "보유 종목 추가 중 문제가 발생했습니다.");
      setFormError(message);
      toast(message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.removePortfolioHolding(id);
      toast("보유 종목을 삭제했습니다.", "info");
      await load();
      const radar = await api.getPortfolioEventRadar(14).catch(() => null);
      if (radar) setEventRadar(radar);
    } catch (error) {
      console.error(error);
      toast(getApiErrorMessage(error, "보유 종목을 삭제하지 못했습니다."), "error");
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-border rounded w-48" />
        <div className="h-40 bg-border rounded" />
        <div className="h-64 bg-border rounded" />
      </div>
    );
  }

  const summary = data?.summary;
  const activeGuide = TICKER_GUIDE[countryCode as keyof typeof TICKER_GUIDE] ?? TICKER_GUIDE.KR;

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Portfolio Workspace"
        title="포트폴리오"
        description="보유 종목 손익, 위험도, 다음 거래일 시그널을 한 화면에서 보고 실제 운영과 리밸런싱까지 이어지도록 정리했습니다."
        meta={
          <>
            <span className="info-chip">보유 종목 {summary?.holding_count ?? 0}개</span>
            <span className="info-chip">리스크 + 모델 비중 동시 확인</span>
          </>
        }
      />

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.85fr)]">
        <div className="card !p-5">
          <div className="section-heading">
            <div>
              <h2 className="section-title">보유 종목 추가</h2>
              <p className="section-copy">티커, 매수가, 수량을 입력하면 손익과 다음 거래일 시그널을 바로 포트폴리오에 반영합니다.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="info-chip">자동 티커 보정</span>
              <span className="info-chip">추가 즉시 리스크 재계산</span>
            </div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1.15fr)_minmax(180px,1fr)_140px_180px_130px]">
            <div className="min-w-0">
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">티커</label>
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder={activeGuide.placeholder}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">매수가</label>
              <input
                value={buyPrice}
                onChange={(e) => setBuyPrice(e.target.value)}
                placeholder="70000"
                type="number"
                min="0"
                step="0.01"
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">수량</label>
              <input
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                placeholder="10"
                type="number"
                min="0"
                step="0.01"
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">매수일</label>
              <input
                value={buyDate}
                onChange={(e) => setBuyDate(e.target.value)}
                type="date"
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">국가</label>
              <select
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              >
                <option value="KR">KR</option>
                <option value="US">US</option>
                <option value="JP">JP</option>
              </select>
            </div>
          </div>
          <div className="mt-4 space-y-3 border-t border-border/70 pt-4">
            <div className="flex flex-wrap gap-2">
              <span className="info-chip">{activeGuide.label} 예시: {activeGuide.examples.join(", ")}</span>
              <span className="info-chip">매수 후 바로 손익/리스크 갱신</span>
            </div>
            <p className="text-sm text-text-secondary">{activeGuide.helper}</p>
            {formError ? (
              <div className="rounded-2xl border border-negative/20 bg-negative/5 px-4 py-3 text-sm text-negative">
                {formError}
              </div>
            ) : (
              <div className="rounded-2xl border border-border/70 bg-surface/45 px-4 py-3 text-sm text-text-secondary">
                한국은 `005930`, 일본은 `7203`, 미국은 `AAPL`처럼 입력하면 저장 시 Yahoo 조회 형식으로 자동 맞춰집니다.
              </div>
            )}
            <TickerResolutionHint resolution={resolution} />
            <div className="flex justify-end">
              <button
                onClick={addHolding}
                disabled={submitting}
                className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60 md:w-auto"
              >
                {submitting ? "추가 중..." : "보유 종목 추가"}
              </button>
            </div>
          </div>
        </div>

        <div className="card !p-5 space-y-4">
          <div>
            <h2 className="section-title">입력 가이드</h2>
            <p className="section-copy">국가별 티커 체계를 자동 보정하지만, 추가 전에 어떤 규칙으로 들어가는지 바로 볼 수 있게 정리했습니다.</p>
          </div>
          <div className="space-y-3">
            {Object.entries(TICKER_GUIDE).map(([code, item]) => (
              <div key={code} className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{item.label}</div>
                  <div className="text-xs text-text-secondary">{code}</div>
                </div>
                <div className="mt-2 text-sm text-text-secondary">{item.examples.join(", ")} 형식을 인식합니다.</div>
              </div>
            ))}
          </div>
          <div className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">추가 후 동작</div>
            <div className="mt-3 space-y-2 text-sm text-text-secondary">
              <p>입력한 종목은 저장 직후 손익, 리스크 점수, 다음 거래일 시그널 계산에 반영됩니다.</p>
              <p>기존에 로컬 티커만 저장된 종목도 이제 포트폴리오 화면에서 자동으로 표준 티커로 다시 해석합니다.</p>
            </div>
          </div>
        </div>
      </div>

      {summary && summary.holding_count > 0 ? (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <div className="metric-card text-center">
              <div className="text-xs text-text-secondary">총 투자금</div>
              <div className="font-bold font-mono">{summary.total_invested.toLocaleString()}</div>
            </div>
            <div className="metric-card text-center">
              <div className="text-xs text-text-secondary">현재 평가액</div>
              <div className="font-bold font-mono">{summary.total_current.toLocaleString()}</div>
            </div>
            <div className="metric-card text-center">
              <div className="text-xs text-text-secondary">평가 손익</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl)}`}>{summary.total_pnl >= 0 ? "+" : ""}{summary.total_pnl.toLocaleString()}</div>
            </div>
            <div className="metric-card text-center">
              <div className="text-xs text-text-secondary">수익률</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl_pct)}`}>{formatPct(summary.total_pnl_pct)}</div>
            </div>
          </div>

          <PortfolioRiskPanel risk={data!.risk} stressTest={data!.stress_test} />
          <PortfolioModelPanel model={data!.model_portfolio} />
          {eventRadar ? <PortfolioEventRadar data={eventRadar} /> : null}
        </>
      ) : null}

      {data && data.allocation.by_sector.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">섹터 비중</h3>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_sector} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={84} label={(entry) => entry.name.slice(0, 10)}>
                    {data.allocation.by_sector.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => value.toLocaleString()} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card">
            <h3 className="font-semibold mb-3 text-sm">국가 비중</h3>
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_country} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={84} label={(entry) => entry.name}>
                    {data.allocation.by_country.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => value.toLocaleString()} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : null}

      {data && data.holdings.length > 0 ? (
        <div className="card !p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="font-semibold">보유 종목 인텔리전스</h2>
            <p className="text-xs text-text-secondary mt-1">각 종목의 손익, 위험도, 단기 시그널, 실행 아이디어를 한 표에서 비교합니다.</p>
          </div>
          <div className="overflow-x-auto px-2 pb-2 pt-1 md:px-3">
            <table className="w-full min-w-[1180px] text-sm">
              <thead>
                <tr className="text-left text-text-secondary border-b border-border bg-surface/40">
                  <th className="px-4 py-3">종목</th>
                  <th className="px-4 py-3 text-right">비중</th>
                  <th className="px-4 py-3 text-right">가격</th>
                  <th className="px-4 py-3 text-right">손익</th>
                  <th className="px-4 py-3 text-right">위험</th>
                  <th className="px-4 py-3 text-right">예측</th>
                  <th className="px-4 py-3">액션</th>
                  <th className="px-4 py-3 text-right">플랜</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((holding) => (
                  <tr key={holding.id} className="border-b border-border/30 align-top hover:bg-border/10">
                    <td className="px-4 py-3">
                      <Link href={`/stock/${holding.ticker}`} className="hover:text-accent">
                        <div className="font-medium">{holding.name}</div>
                        <div className="text-[11px] text-text-secondary">{holding.ticker} · {holding.country_code} · {holding.sector}</div>
                      </Link>
                      {holding.market_regime_label ? <div className="text-[11px] text-text-secondary mt-1">{holding.market_regime_label}</div> : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-semibold">{holding.weight_pct.toFixed(1)}%</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.quantity}주</div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      <div>{formatPrice(holding.current_price, holding.country_code)}</div>
                      <div className="text-[11px] text-text-secondary mt-1">매수가 {formatPrice(holding.buy_price, holding.country_code)}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-mono font-semibold ${changeColor(holding.pnl)}`}>{holding.pnl >= 0 ? "+" : ""}{holding.pnl.toLocaleString()}</div>
                      <div className={`text-[11px] mt-1 ${changeColor(holding.pnl_pct)}`}>{formatPct(holding.pnl_pct)}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-semibold ${holding.risk_level === "high" ? "text-red-500" : holding.risk_level === "medium" ? "text-yellow-500" : "text-emerald-500"}`}>{riskLevelLabel(holding.risk_level)}</div>
                      <div className="text-[11px] text-text-secondary mt-1">점수 {holding.risk_score.toFixed(1)} · 변동성 {holding.realized_volatility_pct.toFixed(1)}%</div>
                      <div className="text-[11px] text-text-secondary mt-1">DD {holding.max_drawdown_pct.toFixed(1)}%{holding.beta != null ? ` · β ${holding.beta.toFixed(2)}` : ""}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-semibold ${changeColor(holding.predicted_return_pct ?? 0)}`}>{holding.predicted_return_pct != null ? formatPct(holding.predicted_return_pct) : "없음"}</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.up_probability != null ? `상승 확률 ${holding.up_probability.toFixed(1)}%` : "예측 없음"}</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.forecast_date ?? ""}</div>
                      <div className={`inline-flex mt-2 px-2 py-1 rounded-full text-[11px] font-medium ${executionBiasTone(holding.execution_bias)}`}>
                        {executionBiasLabel(holding.execution_bias)}
                      </div>
                      {(holding.bull_probability != null || holding.bear_probability != null) ? (
                        <div className="text-[11px] text-text-secondary mt-2">
                          상방 {holding.bull_probability?.toFixed(1) ?? "-"}% / 하방 {holding.bear_probability?.toFixed(1) ?? "-"}%
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold">{tradeActionLabel(holding.trade_action)}</div>
                      <div className="text-[11px] text-text-secondary mt-1">{holding.trade_setup || "설정된 셋업 없음"}</div>
                      {holding.risk_flags.length > 0 ? (
                        <div className="text-[11px] text-amber-600 mt-2 max-w-[220px]">{holding.risk_flags[0]}</div>
                      ) : null}
                      {holding.thesis.length > 0 ? <div className="text-[11px] text-text-secondary mt-2 max-w-[220px]">{holding.thesis[0]}</div> : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="text-[11px] text-text-secondary">진입</div>
                      <div className="font-mono text-xs">{holding.entry_low != null && holding.entry_high != null ? `${formatPrice(holding.entry_low, holding.country_code)} - ${formatPrice(holding.entry_high, holding.country_code)}` : "미정"}</div>
                      <div className="text-[11px] text-text-secondary mt-2">손절 / 1차 목표</div>
                      <div className="font-mono text-xs">{holding.stop_loss != null ? formatPrice(holding.stop_loss, holding.country_code) : "미정"} / {holding.take_profit_1 != null ? formatPrice(holding.take_profit_1, holding.country_code) : "미정"}</div>
                      {(holding.bull_case_price != null || holding.bear_case_price != null) ? (
                        <>
                          <div className="text-[11px] text-text-secondary mt-2">상방 / 기준 / 하방</div>
                          <div className="font-mono text-xs">
                            {holding.bull_case_price != null ? formatPrice(holding.bull_case_price, holding.country_code) : "미정"} / {holding.base_case_price != null ? formatPrice(holding.base_case_price, holding.country_code) : "미정"} / {holding.bear_case_price != null ? formatPrice(holding.bear_case_price, holding.country_code) : "미정"}
                          </div>
                        </>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => remove(holding.id)} className="text-xs text-negative hover:underline">삭제</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="card text-center text-text-secondary py-12">
            <p className="text-lg mb-2">아직 등록된 보유 종목이 없습니다</p>
            <p className="text-sm">위 입력창으로 종목을 추가하면 손익, 위험도, 포지션 관리 시그널을 함께 볼 수 있습니다.</p>
          </div>
          {data ? <PortfolioModelPanel model={data.model_portfolio} /> : null}
        </div>
      )}
    </div>
  );
}
