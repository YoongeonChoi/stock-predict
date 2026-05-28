import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import WeeklyTradePlanCard from "@/components/WeeklyTradePlanCard";
import type { WeeklyTradePlan } from "@/lib/types";

const PLAN: WeeklyTradePlan = {
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
  confidence: 71.4,
  risk_reward_estimate: 1.62,
  evidence: [
    {
      key: "distribution",
      label: "5거래일 분포",
      signal: "bullish",
      detail: "상승 확률이 우세합니다.",
    },
  ],
  source_freshness: [
    {
      name: "가격·거래량",
      status: "fresh",
      item_count: 63,
      note: "최신 가격을 반영했습니다.",
      updated_at: "2026-05-28",
    },
  ],
  partial: false,
  fallback_reason: null,
  data_quality: "5거래일 분포와 공개 데이터를 함께 반영했습니다.",
};

describe("WeeklyTradePlanCard", () => {
  it("대표 매수가·매도가·손절가를 첫 판단으로 렌더링한다", () => {
    render(<WeeklyTradePlanCard plan={PLAN} priceKey="KR" assetLabel="삼성전자" />);

    expect(screen.getByText("이번 주 판단")).toBeInTheDocument();
    expect(screen.getByText("분할 매수")).toBeInTheDocument();
    expect(screen.getByText("₩69,000")).toBeInTheDocument();
    expect(screen.getByText("₩73,500")).toBeInTheDocument();
    expect(screen.getByText("₩66,500")).toBeInTheDocument();
    expect(screen.getByText("64.2%")).toBeInTheDocument();
    expect(screen.getByText(/5거래일 분포와 공개 데이터를/)).toBeInTheDocument();
  });

  it("partial 응답과 긴 한국어 데이터 품질 메모를 숨기지 않는다", () => {
    render(
      <WeeklyTradePlanCard
        plan={{
          ...PLAN,
          action: "wait_pullback",
          partial: true,
          data_quality:
            "정밀 소스 일부가 제한돼 확보된 5거래일 분포와 가격·변동성 신호를 우선 반영했고, 추가 데이터가 들어오면 판단을 갱신합니다.",
        }}
        priceKey="KR"
      />,
    );

    expect(screen.getByText("눌림 대기")).toBeInTheDocument();
    expect(screen.getByText("부분 응답")).toBeInTheDocument();
    expect(screen.getByText(/추가 데이터가 들어오면 판단을 갱신합니다/)).toBeInTheDocument();
  });

  it("공식 리서치와 IB 메타데이터 근거가 뒤쪽에 있어도 첫 판단 카드에 노출된다", () => {
    render(
      <WeeklyTradePlanCard
        plan={{
          ...PLAN,
          evidence: [
            { key: "distribution", label: "5거래일 분포", signal: "neutral", detail: "분포 요약" },
            { key: "price_band", label: "가격·ATR", signal: "neutral", detail: "가격 요약" },
            { key: "market_regime", label: "시장 국면", signal: "neutral", detail: "시장 요약" },
            { key: "flow", label: "수급", signal: "neutral", detail: "수급 요약" },
            { key: "event", label: "뉴스·공시 이벤트", signal: "neutral", detail: "이벤트 요약" },
            {
              key: "official_research",
              label: "공식 리서치",
              signal: "bullish",
              detail: "공식·허용 리서치 메타데이터 2건을 확인했습니다.",
            },
            { key: "fused", label: "통합 판단", signal: "neutral", detail: "통합 요약" },
          ],
          source_freshness: [
            { name: "가격·거래량", status: "fresh", item_count: 63, note: "가격 반영", updated_at: "2026-05-28" },
            { name: "펀더멘털", status: "fresh", item_count: 1, note: "재무 반영" },
            { name: "ECOS 거시", status: "not_configured", item_count: 0, note: "키 없음" },
            { name: "KOSIS 거시", status: "partial", item_count: 2, note: "일부 반영" },
            { name: "OpenDART 공시", status: "fresh", item_count: 3, note: "공시 반영" },
            { name: "뉴스 메타데이터", status: "fresh", item_count: 6, note: "뉴스 반영" },
            { name: "PyKRX 수급", status: "fresh", item_count: 5, note: "수급 반영" },
            { name: "증권사 컨센서스", status: "fresh", item_count: 1, note: "컨센서스 반영" },
            { name: "공식 리서치·IB 메타데이터", status: "fresh", item_count: 2, note: "허용 메타데이터 반영" },
          ],
        }}
        priceKey="KR"
      />,
    );

    expect(screen.getByText("공식 리서치")).toBeInTheDocument();
    expect(screen.getByText(/공식·허용 리서치 메타데이터 2건/)).toBeInTheDocument();
    expect(screen.getByText(/공식 리서치·IB 메타데이터 반영/)).toBeInTheDocument();
    expect(screen.getByText("8/9개 소스 반영")).toBeInTheDocument();
  });
});
