import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RadarPageClient, {
  RADAR_AUTO_RETRY_DELAYS_MS,
  shouldAutoRetryRadarSnapshot,
  type RadarSnapshot,
} from "@/components/pages/RadarPageClient";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getMarketOpportunities: vi.fn(),
    },
  };
});

vi.mock("@/lib/route-observability", () => ({
  reportErrorOnlyScreen: vi.fn(),
  reportHydrationRefetchSuccess: vi.fn(),
  reportInitialSsrSuccess: vi.fn(),
  reportPanelDegraded: vi.fn(),
}));

function baseRadarSnapshot(overrides: Partial<RadarSnapshot> = {}): RadarSnapshot {
  return {
    country_code: "KR",
    snapshot_id: "test-radar",
    generated_at: "2026-05-29T09:00:00+09:00",
    fallback_tier: "placeholder",
    market_regime: {
      label: "KR 빠른 스냅샷",
      stance: "neutral",
      trend: "range",
      volatility: "normal",
      breadth: "mixed",
      score: 50,
      conviction: 38,
      summary: "대표 후보 계산을 준비하고 있습니다.",
      playbook: [],
      warnings: [],
      signals: [],
    },
    universe_size: 200,
    total_scanned: 0,
    quote_available_count: 0,
    detailed_scanned_count: 0,
    actionable_count: 0,
    bullish_count: 0,
    universe_source: "fallback",
    universe_note: "대표 후보 기준 placeholder를 먼저 제공합니다.",
    next_day_focus: null,
    opportunities: [],
    partial: true,
    fallback_reason: "opportunity_startup_guard",
    ...overrides,
  };
}

function usableRadarSnapshot(): RadarSnapshot {
  return baseRadarSnapshot({
    snapshot_id: "test-radar-usable",
    fallback_tier: "quick",
    universe_source: "kr_top200",
    universe_note: "fresh quick 후보를 먼저 반환합니다.",
    total_scanned: 200,
    quote_available_count: 180,
    actionable_count: 1,
    bullish_count: 1,
    fallback_reason: "opportunity_quick_response",
    opportunities: [
      {
        rank: 1,
        ticker: "005930.KS",
        name: "삼성전자",
        sector: "반도체",
        country_code: "KR",
        current_price: 70000,
        change_pct: 1.2,
        opportunity_score: 76,
        quant_score: 68,
        up_probability: 61,
        confidence: 66,
        predicted_return_pct: 2.4,
        target_horizon_days: 20,
        setup_label: "눌림목",
        action: "wait_pullback",
        execution_bias: "stay_selective",
        regime_tailwind: "mixed",
        risk_reward_estimate: 1.4,
        thesis: ["진입 조건 확인이 필요합니다."],
        risk_flags: [],
        forecast_date: "2026-06-18",
      },
    ],
  });
}

async function flushReactUpdates() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("RadarPageClient placeholder recovery", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(api.getMarketOpportunities).mockReset();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("placeholder 응답이면 백엔드 quick warm-up 뒤 자동 재조회한다", async () => {
    vi.mocked(api.getMarketOpportunities)
      .mockResolvedValueOnce(baseRadarSnapshot({ snapshot_id: "placeholder-after-hydration" }))
      .mockResolvedValueOnce(usableRadarSnapshot());

    render(<RadarPageClient initialData={baseRadarSnapshot()} />);

    await flushReactUpdates();
    expect(api.getMarketOpportunities).toHaveBeenCalledTimes(1);
    expect(screen.getByText("첫 판단 스레드 준비 중")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(RADAR_AUTO_RETRY_DELAYS_MS[0]);
    });

    await flushReactUpdates();
    expect(api.getMarketOpportunities).toHaveBeenCalledTimes(2);
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
  });

  it("자동 재조회는 placeholder, 비로딩, 제한 횟수 안에서만 예약한다", () => {
    const placeholder = baseRadarSnapshot();
    const usable = usableRadarSnapshot();

    expect(shouldAutoRetryRadarSnapshot(placeholder, false, 0)).toBe(true);
    expect(shouldAutoRetryRadarSnapshot(placeholder, true, 0)).toBe(false);
    expect(shouldAutoRetryRadarSnapshot(usable, false, 0)).toBe(false);
    expect(shouldAutoRetryRadarSnapshot(placeholder, false, RADAR_AUTO_RETRY_DELAYS_MS.length)).toBe(false);
  });
});
