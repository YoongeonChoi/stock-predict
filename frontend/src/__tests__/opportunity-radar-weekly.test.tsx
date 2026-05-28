import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import OpportunityRadarBoard from "@/components/OpportunityRadarBoard";
import type { OpportunityRadarResponse } from "@/lib/types";

function radarData(): OpportunityRadarResponse {
  return {
    country_code: "KR",
    snapshot_id: "test",
    generated_at: "2026-05-28T09:00:00+09:00",
    fallback_tier: "full",
    market_regime: {
      label: "중립",
      stance: "neutral",
      trend: "range",
      volatility: "normal",
      breadth: "mixed",
      score: 50,
      conviction: 50,
      summary: "중립 국면",
      playbook: [],
      warnings: [],
      signals: [],
    },
    universe_size: 200,
    total_scanned: 200,
    quote_available_count: 200,
    detailed_scanned_count: 1,
    actionable_count: 1,
    bullish_count: 1,
    universe_source: "kr_top200",
    universe_note: "대표 종목 기준",
    next_day_focus: null,
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
  };
}

describe("OpportunityRadarBoard weekly plan compatibility", () => {
  it("weekly_trade_plan이 없어도 기존 후보 카드를 렌더링한다", () => {
    render(<OpportunityRadarBoard data={radarData()} compact />);

    expect(screen.getByText("삼성전자")).toBeInTheDocument();
    expect(screen.queryByText("이번 주 매수·매도")).not.toBeInTheDocument();
  });

  it("weekly_trade_plan이 있으면 선택적으로 매수·매도 요약을 표시한다", () => {
    const data = radarData();
    data.opportunities[0].weekly_trade_plan = {
      horizon_days: 5,
      target_date: "2026-06-04",
      reference_date: "2026-05-28",
      reference_price: 70000,
      action: "accumulate",
      buy_price: 69000,
      buy_zone_low: 68000,
      buy_zone_high: 70000,
      sell_price: 73500,
      sell_zone_low: 73000,
      sell_zone_high: 74500,
      stop_loss: 66500,
      expected_return_pct: 3.2,
      expected_excess_return_pct: 1.4,
      p_up: 64.2,
      p_flat: 19.5,
      p_down: 16.3,
      confidence: 71,
      risk_reward_estimate: 1.6,
      evidence: [],
      source_freshness: [],
      partial: false,
      fallback_reason: null,
      data_quality: "정상",
    };

    render(<OpportunityRadarBoard data={data} compact />);

    expect(screen.getByText("이번 주 매수·매도")).toBeInTheDocument();
    expect(screen.getByText("₩69,000")).toBeInTheDocument();
    expect(screen.getByText("₩73,500")).toBeInTheDocument();
  });
});
