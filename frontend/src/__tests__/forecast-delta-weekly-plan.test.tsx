import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ForecastDeltaCard from "@/components/ForecastDeltaCard";
import type { ForecastDeltaResponse } from "@/lib/api";

const DATA: ForecastDeltaResponse = {
  generated_at: "2026-05-28T15:00:00+09:00",
  ticker: "005930.KS",
  summary: {
    available: true,
    current_direction: "up",
    current_direction_label: "상승",
    up_probability_delta: 2.5,
    confidence_delta: 1.2,
    predicted_close_delta_pct: 0.8,
    direction_changed: false,
    hit_rate: 60,
    message: "직전 저장값 대비 상방 확률이 상승했습니다.",
  },
  history: [
    {
      target_date: "2026-05-29",
      reference_date: "2026-05-28",
      reference_price: 70000,
      predicted_close: 71400,
      predicted_low: 69000,
      predicted_high: 73000,
      up_probability: 62,
      confidence: 66,
      direction: "up",
      direction_label: "상승",
      actual_close: null,
      direction_hit: null,
      model_version: "dist-studentt-v3.3-lfgraph",
      created_at: 1,
    },
  ],
  weekly_plan: {
    available: true,
    evaluated_count: 1,
    target_hit_rate: 100,
    stop_hit_rate: 0,
    message: "최근 5거래일 실행안 1건 중 목표 구간 도달 1건, 손절 접촉 0건을 기록했습니다.",
    history: [
      {
        target_date: "2026-06-04",
        reference_date: "2026-05-28",
        action: "accumulate",
        buy_price: 69000,
        sell_price: 73500,
        stop_loss: 66500,
        window_low: 68200,
        window_high: 73800,
        actual_close: 73200,
        buy_zone_touched: true,
        sell_zone_touched: true,
        stop_loss_touched: false,
        actual_return_pct: 4.5,
        outcome: "target_zone_touched",
        outcome_label: "목표 구간 도달",
        confidence: 71,
        up_probability: 64,
        model_version: "dist-studentt-v3.3-lfgraph",
        created_at: 2,
      },
    ],
  },
};

describe("ForecastDeltaCard weekly plan execution", () => {
  it("5거래일 매수·매도 실행안 검증 결과를 렌더링한다", () => {
    render(<ForecastDeltaCard data={DATA} priceKey="KR" />);

    expect(screen.getByText("이번 주 판단 검증")).toBeInTheDocument();
    expect(screen.getByText("목표 100.0%")).toBeInTheDocument();
    expect(screen.getByText("손절 0.0%")).toBeInTheDocument();
    expect(screen.getByText(/목표일 2026-06-04/)).toBeInTheDocument();
    expect(screen.getByText("매수 접촉")).toBeInTheDocument();
    expect(screen.getByText("목표 접촉")).toBeInTheDocument();
    expect(screen.getByText("미접촉")).toBeInTheDocument();
  });
});
