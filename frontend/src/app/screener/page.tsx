"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { ScreenerResult } from "@/lib/api";
import { changeColor, formatMarketCap, formatPct, formatPrice } from "@/lib/utils";

type ScreenerFilters = {
  country: string;
  sector: string;
  marketCapMin: string;
  marketCapMax: string;
  priceMin: string;
  priceMax: string;
  peMax: string;
  pbMax: string;
  dividendMin: string;
  betaMax: string;
  revenueGrowthMin: string;
  roeMin: string;
  debtToEquityMax: string;
  avgVolumeMin: string;
  changePctMin: string;
  changePctMax: string;
  pctFrom52wHighMin: string;
  pctFrom52wHighMax: string;
  scoreMin: string;
  profitableOnly: boolean;
  sortBy: string;
  sortDir: string;
};

const DEFAULT_FILTERS: ScreenerFilters = {
  country: "KR",
  sector: "",
  marketCapMin: "",
  marketCapMax: "",
  priceMin: "",
  priceMax: "",
  peMax: "",
  pbMax: "",
  dividendMin: "",
  betaMax: "",
  revenueGrowthMin: "",
  roeMin: "",
  debtToEquityMax: "",
  avgVolumeMin: "",
  changePctMin: "",
  changePctMax: "",
  pctFrom52wHighMin: "",
  pctFrom52wHighMax: "",
  scoreMin: "",
  profitableOnly: false,
  sortBy: "market_cap",
  sortDir: "desc",
};

const PRESETS: Array<{ label: string; description: string; values: Partial<ScreenerFilters> }> = [
  {
    label: "저평가 배당",
    description: "낮은 밸류에이션과 배당을 함께 보는 조건",
    values: { peMax: "18", pbMax: "2", dividendMin: "2", betaMax: "1.2", sortBy: "dividend_yield" },
  },
  {
    label: "성장 퀄리티",
    description: "매출 성장과 ROE가 함께 강한 종목",
    values: { revenueGrowthMin: "10", roeMin: "12", debtToEquityMax: "120", profitableOnly: true, sortBy: "roe" },
  },
  {
    label: "모멘텀",
    description: "고점 근처에서 강세를 유지하는 종목",
    values: { changePctMin: "0", pctFrom52wHighMin: "-12", scoreMin: "60", sortBy: "score" },
  },
  {
    label: "눌림목",
    description: "고점 대비 눌렸지만 기초 체력이 남은 종목",
    values: { pctFrom52wHighMin: "-25", pctFrom52wHighMax: "-5", peMax: "25", roeMin: "10", profitableOnly: true, sortBy: "pct_from_52w_high", sortDir: "desc" },
  },
];

function buildParams(filters: ScreenerFilters): Record<string, string> {
  const params: Record<string, string> = {
    country: filters.country,
    sort_by: filters.sortBy,
    sort_dir: filters.sortDir,
    limit: "120",
  };
  if (filters.sector) params.sector = filters.sector;
  if (filters.marketCapMin) params.market_cap_min = filters.marketCapMin;
  if (filters.marketCapMax) params.market_cap_max = filters.marketCapMax;
  if (filters.priceMin) params.price_min = filters.priceMin;
  if (filters.priceMax) params.price_max = filters.priceMax;
  if (filters.peMax) params.pe_max = filters.peMax;
  if (filters.pbMax) params.pb_max = filters.pbMax;
  if (filters.dividendMin) params.dividend_yield_min = String(Number(filters.dividendMin) / 100);
  if (filters.betaMax) params.beta_max = filters.betaMax;
  if (filters.revenueGrowthMin) params.revenue_growth_min = filters.revenueGrowthMin;
  if (filters.roeMin) params.roe_min = filters.roeMin;
  if (filters.debtToEquityMax) params.debt_to_equity_max = filters.debtToEquityMax;
  if (filters.avgVolumeMin) params.avg_volume_min = filters.avgVolumeMin;
  if (filters.changePctMin) params.change_pct_min = filters.changePctMin;
  if (filters.changePctMax) params.change_pct_max = filters.changePctMax;
  if (filters.pctFrom52wHighMin) params.pct_from_52w_high_min = filters.pctFrom52wHighMin;
  if (filters.pctFrom52wHighMax) params.pct_from_52w_high_max = filters.pctFrom52wHighMax;
  if (filters.scoreMin) params.score_min = filters.scoreMin;
  if (filters.profitableOnly) params.profitable_only = "true";
  return params;
}

function average(values: Array<number | null | undefined>) {
  const valid = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (valid.length === 0) return null;
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

export default function ScreenerPage() {
  const [filters, setFilters] = useState<ScreenerFilters>(DEFAULT_FILTERS);
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const runSearch = async (nextFilters: ScreenerFilters = filters) => {
    setLoading(true);
    setSearched(true);
    try {
      const data = await api.getScreener(buildParams(nextFilters));
      setResults(data.results);
      setSectors(data.sectors);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSearch(DEFAULT_FILTERS);
  }, []);

  const applyPreset = async (values: Partial<ScreenerFilters>) => {
    const next = { ...DEFAULT_FILTERS, ...filters, ...values };
    setFilters(next);
    await runSearch(next);
  };

  const resetFilters = async () => {
    setFilters(DEFAULT_FILTERS);
    await runSearch(DEFAULT_FILTERS);
  };

  const digest = useMemo(() => {
    const profitable = results.filter((item) => (item.profit_margins ?? 0) > 0).length;
    const positiveMomentum = results.filter((item) => (item.change_pct ?? 0) > 0).length;
    return {
      avgRoe: average(results.map((item) => item.roe)),
      avgDividend: average(results.map((item) => (item.dividend_yield ?? 0) * 100)),
      profitable,
      positiveMomentum,
    };
  }, [results]);

  return (
    <div className="page-shell">
      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div>
            <h1 className="section-title text-2xl">스크리너</h1>
            <p className="section-copy">국가, 밸류, 퀄리티, 모멘텀, 리스크 조건을 함께 써서 실제 투자 후보군을 압축합니다.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="info-chip">결과 {results.length}개</span>
            <span className="info-chip">흑자 {digest.profitable}개</span>
            {digest.avgRoe != null ? <span className="info-chip">평균 ROE {digest.avgRoe.toFixed(1)}%</span> : null}
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-4">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => applyPreset(preset.values)}
              className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 text-left transition-colors hover:border-accent/35"
            >
              <div className="font-medium text-text">{preset.label}</div>
              <div className="mt-2 text-sm leading-6 text-text-secondary">{preset.description}</div>
            </button>
          ))}
        </div>
      </section>

      <section className="card !p-5 space-y-5">
        <div className="section-heading gap-4">
          <div>
            <h2 className="section-title">조건 설정</h2>
            <p className="section-copy">필터는 4개 묶음으로 나누고, 한 번에 너무 많은 좌우 분산이 생기지 않도록 2열 중심으로 정리했습니다.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={resetFilters} className="action-chip-secondary">기본값으로 되돌리기</button>
            <button onClick={() => runSearch()} className="action-chip-primary">조건 검색</button>
          </div>
        </div>

        <div className="grid gap-4 2xl:grid-cols-2">
          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">시장 / 규모</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">국가</label>
                <select value={filters.country} onChange={(e) => setFilters((prev) => ({ ...prev, country: e.target.value }))} className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm">
                  <option value="KR">KR</option>
                  <option value="US">US</option>
                  <option value="JP">JP</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">섹터</label>
                <select value={filters.sector} onChange={(e) => setFilters((prev) => ({ ...prev, sector: e.target.value }))} className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm">
                  <option value="">전체 섹터</option>
                  {sectors.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">시총 최소</label>
                <input value={filters.marketCapMin} onChange={(e) => setFilters((prev) => ({ ...prev, marketCapMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">시총 최대</label>
                <input value={filters.marketCapMax} onChange={(e) => setFilters((prev) => ({ ...prev, marketCapMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">가격 최소</label>
                <input value={filters.priceMin} onChange={(e) => setFilters((prev) => ({ ...prev, priceMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">가격 최대</label>
                <input value={filters.priceMax} onChange={(e) => setFilters((prev) => ({ ...prev, priceMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
            </div>
          </div>

          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">밸류 / 배당</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최대 P/E</label>
                <input value={filters.peMax} onChange={(e) => setFilters((prev) => ({ ...prev, peMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최대 P/B</label>
                <input value={filters.pbMax} onChange={(e) => setFilters((prev) => ({ ...prev, pbMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 배당 %</label>
                <input value={filters.dividendMin} onChange={(e) => setFilters((prev) => ({ ...prev, dividendMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최대 베타</label>
                <input value={filters.betaMax} onChange={(e) => setFilters((prev) => ({ ...prev, betaMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
            </div>
          </div>

          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">퀄리티 / 성장</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 매출 성장 %</label>
                <input value={filters.revenueGrowthMin} onChange={(e) => setFilters((prev) => ({ ...prev, revenueGrowthMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 ROE %</label>
                <input value={filters.roeMin} onChange={(e) => setFilters((prev) => ({ ...prev, roeMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최대 부채비율</label>
                <input value={filters.debtToEquityMax} onChange={(e) => setFilters((prev) => ({ ...prev, debtToEquityMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 평균 거래량</label>
                <input value={filters.avgVolumeMin} onChange={(e) => setFilters((prev) => ({ ...prev, avgVolumeMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <label className="inline-flex items-center gap-2 rounded-2xl border border-border px-4 py-3 text-sm text-text-secondary md:col-span-2">
                <input type="checkbox" checked={filters.profitableOnly} onChange={(e) => setFilters((prev) => ({ ...prev, profitableOnly: e.target.checked }))} />
                흑자 기업만 보기
              </label>
            </div>
          </div>

          <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-text-secondary">모멘텀 / 리스크</div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 등락률 %</label>
                <input value={filters.changePctMin} onChange={(e) => setFilters((prev) => ({ ...prev, changePctMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최대 등락률 %</label>
                <input value={filters.changePctMax} onChange={(e) => setFilters((prev) => ({ ...prev, changePctMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">52주 고점 대비 최소 %</label>
                <input value={filters.pctFrom52wHighMin} onChange={(e) => setFilters((prev) => ({ ...prev, pctFrom52wHighMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div>
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">52주 고점 대비 최대 %</label>
                <input value={filters.pctFrom52wHighMax} onChange={(e) => setFilters((prev) => ({ ...prev, pctFrom52wHighMax: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
              <div className="md:col-span-2">
                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 종합 점수</label>
                <input value={filters.scoreMin} onChange={(e) => setFilters((prev) => ({ ...prev, scoreMin: e.target.value }))} type="number" className="w-full rounded-2xl border border-border bg-surface/70 px-4 py-3 text-sm" />
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="metric-card">
            <div className="text-xs text-text-secondary">흑자 종목</div>
            <div className="mt-2 text-2xl font-bold text-text">{digest.profitable}</div>
            <div className="mt-1 text-[11px] text-text-secondary">전체 결과 중</div>
          </div>
          <div className="metric-card">
            <div className="text-xs text-text-secondary">상승 종목</div>
            <div className="mt-2 text-2xl font-bold text-text">{digest.positiveMomentum}</div>
            <div className="mt-1 text-[11px] text-text-secondary">당일 플러스 종목</div>
          </div>
          <div className="metric-card">
            <div className="text-xs text-text-secondary">평균 배당</div>
            <div className="mt-2 text-2xl font-bold text-text">{digest.avgDividend != null ? `${digest.avgDividend.toFixed(1)}%` : "-"}</div>
            <div className="mt-1 text-[11px] text-text-secondary">현재 결과 기준</div>
          </div>
          <div className="metric-card">
            <div className="text-xs text-text-secondary">정렬 기준</div>
            <div className="mt-2 text-lg font-semibold text-text">{filters.sortBy}</div>
            <div className="mt-1 text-[11px] text-text-secondary">{filters.sortDir === "desc" ? "내림차순" : "오름차순"}</div>
          </div>
        </div>
      </section>

      <section className="card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <div className="section-heading gap-4">
            <div>
              <h2 className="section-title">결과</h2>
              <p className="section-copy">정렬을 바꿔 후보의 성격을 빠르게 비교할 수 있습니다.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setFilters((prev) => ({ ...prev, sortBy: "score", sortDir: "desc" }))} className="action-chip-secondary">점수</button>
              <button onClick={() => setFilters((prev) => ({ ...prev, sortBy: "roe", sortDir: "desc" }))} className="action-chip-secondary">ROE</button>
              <button onClick={() => setFilters((prev) => ({ ...prev, sortBy: "dividend_yield", sortDir: "desc" }))} className="action-chip-secondary">배당</button>
              <button onClick={() => setFilters((prev) => ({ ...prev, sortBy: "pct_from_52w_high", sortDir: "desc" }))} className="action-chip-secondary">고점 대비</button>
              <button onClick={() => runSearch()} className="action-chip-primary">정렬 적용</button>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto px-2 pb-2 pt-1 md:px-3">
          <table className="w-full min-w-[1240px] text-sm">
            <thead>
              <tr className="border-b border-border bg-surface/40 text-left text-text-secondary">
                <th className="px-4 py-3">종목</th>
                <th className="px-4 py-3 text-right">현재가</th>
                <th className="px-4 py-3 text-right">등락률</th>
                <th className="px-4 py-3 text-right">시총</th>
                <th className="px-4 py-3 text-right">P/E / P/B</th>
                <th className="px-4 py-3 text-right">배당 / ROE</th>
                <th className="px-4 py-3 text-right">성장 / 부채</th>
                <th className="px-4 py-3 text-right">52주 고점 대비</th>
                <th className="px-4 py-3 text-right">점수</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-text-secondary">조건을 계산하는 중입니다.</td>
                </tr>
              ) : results.length > 0 ? (
                results.map((stock) => (
                  <tr key={stock.ticker} className="border-b border-border/30 hover:bg-border/10">
                    <td className="px-4 py-3">
                      <Link href={`/stock/${encodeURIComponent(stock.ticker)}`} className="font-medium text-text hover:text-accent">
                        {stock.name}
                      </Link>
                      <div className="mt-1 text-[11px] text-text-secondary">{stock.ticker} · {stock.country_code} · {stock.sector}</div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{formatPrice(stock.current_price, stock.country_code)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${changeColor(stock.change_pct ?? 0)}`}>{formatPct(stock.change_pct ?? 0)}</td>
                    <td className="px-4 py-3 text-right">{formatMarketCap(stock.market_cap)}</td>
                    <td className="px-4 py-3 text-right">{stock.pe_ratio?.toFixed(1) ?? "-"} / {stock.pb_ratio?.toFixed(1) ?? "-"}</td>
                    <td className="px-4 py-3 text-right">{stock.dividend_yield != null ? `${(stock.dividend_yield * 100).toFixed(1)}%` : "-"} / {stock.roe != null ? `${stock.roe.toFixed(1)}%` : "-"}</td>
                    <td className="px-4 py-3 text-right">{stock.revenue_growth != null ? `${stock.revenue_growth.toFixed(1)}%` : "-"} / {stock.debt_to_equity != null ? stock.debt_to_equity.toFixed(0) : "-"}</td>
                    <td className={`px-4 py-3 text-right ${changeColor(stock.pct_from_52w_high ?? 0)}`}>{stock.pct_from_52w_high?.toFixed(1)}%</td>
                    <td className="px-4 py-3 text-right font-semibold">{stock.score?.toFixed(1) ?? "-"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-text-secondary">
                    {searched ? "조건에 맞는 종목이 없습니다. 필터를 조금 완화해 보세요." : "검색을 시작하면 결과가 여기에 표시됩니다."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
