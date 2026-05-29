import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  STOCK_DETAIL_AUTO_RETRY_DELAYS_MS,
  useStockDetailFlow,
} from "@/components/pages/useStockDetailFlow";
import { api } from "@/lib/api";
import type { StockDetail } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getStockDetail: vi.fn(),
      getTechSummary: vi.fn(),
      getPivotPoints: vi.fn(),
      getStockForecastDelta: vi.fn(),
      getStockChart: vi.fn(),
    },
  };
});

vi.mock("@/lib/route-observability", () => ({
  reportErrorOnlyScreen: vi.fn(),
  reportHydrationRefetchSuccess: vi.fn(),
  reportHydrationRefetchTimeout: vi.fn(),
  reportInitialSsrSuccess: vi.fn(),
  reportPanelDegraded: vi.fn(),
}));

function stockSnapshot(overrides: Partial<StockDetail> = {}): StockDetail {
  return {
    ticker: "005930.KS",
    name: "삼성전자",
    country_code: "KR",
    sector: "Technology",
    industry: "Semiconductors",
    market_cap: 0,
    current_price: 70000,
    change_pct: 0,
    financials: [],
    peer_comparisons: [],
    dividend: {},
    analyst_ratings: { buy: 0, hold: 0, sell: 0 },
    earnings_history: [],
    price_history: [],
    technical: { ma_20: [], ma_60: [], rsi_14: [], macd: [], dates: [] },
    score: {
      total: 50,
      valuation: 50,
      growth: 50,
      profitability: 50,
      momentum: 50,
      risk: 50,
      quality: 50,
    },
    buy_sell_guide: {
      buy_price: 69000,
      sell_price: 76000,
      stop_loss: 66000,
      buy_zone: [68000, 70000],
      sell_zone: [75000, 77000],
    },
    ...overrides,
  } as StockDetail;
}

function shellSnapshot(): StockDetail {
  return stockSnapshot({
    partial: true,
    fallback_reason: "stock_memory_guard",
    weekly_trade_plan: {
      partial: true,
      fallback_reason: "stock_memory_guard",
    },
  } as Partial<StockDetail>);
}

function numericSnapshot(): StockDetail {
  return stockSnapshot({
    partial: true,
    fallback_reason: "stock_quick_distributional",
    weekly_trade_plan: {
      horizon_days: 5,
      target_date: "2026-06-05",
      reference_date: "2026-05-29",
      reference_price: 70000,
      action: "wait_pullback",
      buy_price: 68200,
      buy_zone_low: 67500,
      buy_zone_high: 69000,
      sell_price: 73500,
      sell_zone_low: 72800,
      sell_zone_high: 74200,
      stop_loss: 66100,
      expected_return_pct: 4.2,
      p_up: 63.5,
      p_flat: 19.5,
      p_down: 17,
      confidence: 52,
      risk_reward_estimate: 1.7,
      evidence: [],
      source_freshness: [],
      partial: true,
      fallback_reason: "stock_quick_distributional",
      data_quality: "quick",
    },
  });
}

function FlowProbe({ initialData }: { initialData: StockDetail }) {
  const { stock } = useStockDetailFlow({ initialTicker: "005930.KS", initialData });
  return (
    <div>
      <span>{stock?.fallback_reason ?? "complete"}</span>
      <span>{stock?.weekly_trade_plan?.buy_price ?? "no-buy"}</span>
    </div>
  );
}

async function flushReactUpdates() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("stock detail shell auto retry", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(api.getStockDetail).mockReset();
    vi.mocked(api.getTechSummary).mockResolvedValue(null as never);
    vi.mocked(api.getPivotPoints).mockResolvedValue(null as never);
    vi.mocked(api.getStockForecastDelta).mockResolvedValue(null as never);
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("full 업그레이드 뒤에도 shell이면 지연 재조회로 숫자 판단을 채운다", async () => {
    vi.mocked(api.getStockDetail)
      .mockResolvedValueOnce(shellSnapshot())
      .mockResolvedValueOnce(numericSnapshot());

    render(<FlowProbe initialData={shellSnapshot()} />);

    await flushReactUpdates();
    expect(api.getStockDetail).toHaveBeenCalledTimes(1);
    expect(screen.getByText("no-buy")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(STOCK_DETAIL_AUTO_RETRY_DELAYS_MS[0]);
    });
    await flushReactUpdates();

    expect(api.getStockDetail).toHaveBeenCalledTimes(2);
    expect(screen.getByText("68200")).toBeInTheDocument();
  });

  it("shell 재조회는 quick warm 승격 시간대까지 여러 번 이어진다", async () => {
    vi.mocked(api.getStockDetail)
      .mockResolvedValueOnce(shellSnapshot())
      .mockResolvedValueOnce(shellSnapshot())
      .mockResolvedValueOnce(numericSnapshot());

    render(<FlowProbe initialData={shellSnapshot()} />);

    await flushReactUpdates();
    expect(api.getStockDetail).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(STOCK_DETAIL_AUTO_RETRY_DELAYS_MS[0]);
    });
    await flushReactUpdates();
    expect(api.getStockDetail).toHaveBeenCalledTimes(2);
    expect(screen.getByText("no-buy")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(STOCK_DETAIL_AUTO_RETRY_DELAYS_MS[1]);
    });
    await flushReactUpdates();

    expect(api.getStockDetail).toHaveBeenCalledTimes(3);
    expect(screen.getByText("68200")).toBeInTheDocument();
  });
});
