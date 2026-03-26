"use client";

import PortfolioRecommendationPanel from "@/components/PortfolioRecommendationPanel";
import type {
  PortfolioConditionalRecommendationFilters,
  PortfolioConditionalRecommendationResponse,
  PortfolioRecommendationStyle,
} from "@/lib/api";

interface Props {
  data: PortfolioConditionalRecommendationResponse | null;
  filters: PortfolioConditionalRecommendationFilters;
  loading: boolean;
  running: boolean;
  onChange: (next: PortfolioConditionalRecommendationFilters) => void;
  onRun: () => void;
}

export default function PortfolioConditionalRecommendationPanel({
  data,
  filters,
  loading,
  running,
  onChange,
  onRun,
}: Props) {
  const options = data?.options ?? {
    countries: ["KR"],
    sectors: ["ALL"],
    styles: ["defensive", "balanced", "offensive"] as PortfolioRecommendationStyle[],
  };

  const controls = (
    <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
        <div className="min-w-0">
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">국가</label>
          <select
            value={filters.country_code}
            onChange={(e) => onChange({ ...filters, country_code: e.target.value })}
            className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
          >
            {options.countries.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-0">
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">섹터</label>
          <select
            value={filters.sector}
            onChange={(e) => onChange({ ...filters, sector: e.target.value })}
            className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
          >
            {options.sectors.map((item) => (
              <option key={item} value={item}>
                {item === "ALL" ? "전체 섹터" : item}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-0">
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">운영 성향</label>
          <select
            value={filters.style}
            onChange={(e) => onChange({ ...filters, style: e.target.value as PortfolioRecommendationStyle })}
            className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
          >
            <option value="defensive">방어형</option>
            <option value="balanced">균형형</option>
            <option value="offensive">공격형</option>
          </select>
        </div>
        <div className="min-w-0">
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">추천 수</label>
          <select
            value={filters.max_items}
            onChange={(e) => onChange({ ...filters, max_items: Number(e.target.value) })}
            className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
          >
            {[3, 4, 5, 6, 7, 8].map((item) => (
              <option key={item} value={item}>{item}개</option>
            ))}
          </select>
        </div>
        <div className="min-w-0">
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">최소 상승 확률</label>
          <select
            value={filters.min_up_probability}
            onChange={(e) => onChange({ ...filters, min_up_probability: Number(e.target.value) })}
            className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
          >
            {[50, 52, 54, 56, 58, 60, 62].map((item) => (
              <option key={item} value={item}>{item}%</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-3 text-sm text-text-secondary">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filters.exclude_holdings}
              onChange={(e) => onChange({ ...filters, exclude_holdings: e.target.checked })}
            />
            보유 종목 제외
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={filters.watchlist_only}
              onChange={(e) => onChange({ ...filters, watchlist_only: e.target.checked })}
            />
            워치리스트만 보기
          </label>
        </div>
        <button
          onClick={onRun}
          disabled={running}
          className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60 xl:w-auto"
        >
          {running ? "조건 추천 계산 중..." : "조건 추천 실행"}
        </button>
      </div>
    </div>
  );

  return (
    <PortfolioRecommendationPanel
      title="조건 추천"
      description="한국 시장 안에서 섹터, 성향, 최소 확률 조건을 정하면 그 범위 안에서 가장 효율적인 신규 비중안을 다시 계산합니다."
      loading={loading}
      budget={data?.budget}
      summary={data?.summary}
      recommendations={data?.recommendations}
      notes={data?.notes}
      marketView={data?.market_view}
      controls={controls}
      emptyMessage="현재 조건을 만족하는 추천 후보가 아직 충분하지 않습니다. 국가나 섹터를 넓히거나 최소 상승 확률을 조금 낮춰 다시 실행해 보세요."
    />
  );
}
