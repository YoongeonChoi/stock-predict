"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import PortfolioRiskPanel from "@/components/PortfolioRiskPanel";
import { api } from "@/lib/api";
import type { PortfolioData } from "@/lib/api";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

const COLORS = ["#0f766e", "#2563eb", "#f59e0b", "#ef4444", "#7c3aed", "#ec4899", "#0891b2", "#65a30d"];

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
  const [ticker, setTicker] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [qty, setQty] = useState("");
  const [buyDate, setBuyDate] = useState(new Date().toISOString().slice(0, 10));
  const [countryCode, setCountryCode] = useState("KR");

  const load = () => {
    setLoading(true);
    api.getPortfolio().then(setData).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const addHolding = async () => {
    if (!ticker || !buyPrice || !qty) return;
    try {
      await api.addPortfolioHolding({
        ticker: ticker.toUpperCase(),
        buy_price: Number(buyPrice),
        quantity: Number(qty),
        buy_date: buyDate,
        country_code: countryCode,
      });
      setTicker("");
      setBuyPrice("");
      setQty("");
      load();
    } catch (error) {
      console.error(error);
    }
  };

  const remove = async (id: number) => {
    await api.removePortfolioHolding(id);
    load();
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

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">포트폴리오</h1>
        <p className="text-text-secondary mt-1">보유 종목 손익과 위험도를 함께 보고, 다음 거래일 시그널까지 한 번에 점검합니다.</p>
      </div>

      <div className="card !p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-text-secondary block mb-1">티커</label>
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="005930" className="w-28 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">매수가</label>
          <input value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} placeholder="70000" type="number" className="w-28 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">수량</label>
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="10" type="number" className="w-24 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">매수일</label>
          <input value={buyDate} onChange={(e) => setBuyDate(e.target.value)} type="date" className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm" />
        </div>
        <div>
          <label className="text-xs text-text-secondary block mb-1">국가</label>
          <select value={countryCode} onChange={(e) => setCountryCode(e.target.value)} className="px-3 py-1.5 rounded-lg bg-surface border border-border text-sm">
            <option value="KR">KR</option>
            <option value="US">US</option>
            <option value="JP">JP</option>
          </select>
        </div>
        <button onClick={addHolding} className="px-6 py-1.5 rounded-lg bg-accent text-white text-sm font-medium hover:opacity-90">보유 종목 추가</button>
      </div>

      {summary && summary.holding_count > 0 ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">총 투자금</div>
              <div className="font-bold font-mono">{summary.total_invested.toLocaleString()}</div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">현재 평가액</div>
              <div className="font-bold font-mono">{summary.total_current.toLocaleString()}</div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">평가 손익</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl)}`}>{summary.total_pnl >= 0 ? "+" : ""}{summary.total_pnl.toLocaleString()}</div>
            </div>
            <div className="card !p-3 text-center">
              <div className="text-xs text-text-secondary">수익률</div>
              <div className={`font-bold font-mono ${changeColor(summary.total_pnl_pct)}`}>{formatPct(summary.total_pnl_pct)}</div>
            </div>
          </div>

          <PortfolioRiskPanel risk={data!.risk} stressTest={data!.stress_test} />
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1280px]">
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
        <div className="card text-center text-text-secondary py-12">
          <p className="text-lg mb-2">아직 등록된 보유 종목이 없습니다</p>
          <p className="text-sm">위 입력창으로 종목을 추가하면 손익, 위험도, 포지션 관리 시그널을 함께 볼 수 있습니다.</p>
        </div>
      )}
    </div>
  );
}
