import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PredictionLabDashboard from "@/components/PredictionLabDashboard";

vi.mock("recharts", () => {
  const Container = ({ children }: { children?: any }) => <div>{children}</div>;
  const Leaf = () => <div />;
  return {
    ResponsiveContainer: Container,
    BarChart: Container,
    LineChart: Container,
    CartesianGrid: Leaf,
    XAxis: Leaf,
    YAxis: Leaf,
    Tooltip: Leaf,
    Bar: Leaf,
    Line: Leaf,
  };
});

function predictionLabData() {
  return {
    generated_at: "2026-05-14T08:00:00",
    accuracy: {
      stored_predictions: 4,
      pending_predictions: 1,
      total_predictions: 3,
      within_range: 2,
      within_range_rate: 0.6667,
      direction_hits: 2,
      direction_accuracy: 0.6667,
      avg_error_pct: 1.2,
      avg_confidence: 62.4,
    },
    pipeline_health: {
      stored_predictions: 4,
      pending_predictions: 1,
      evaluated_predictions: 3,
      stale_pending_predictions: 0,
      last_checked_at: "2026-05-14T08:00:00",
      backfill_checked_reports: 0,
      backfill_updated_reports: 0,
      backfill_captured_predictions: 0,
    },
    coverage_breakdown: {
      by_scope: [],
      by_prediction_type: [],
      by_model_version: [],
    },
    pipeline_alerts: [],
    horizon_accuracy: [
      {
        prediction_type: "next_day",
        label: "1D",
        stored_predictions: 4,
        pending_predictions: 1,
        total_predictions: 3,
        direction_accuracy: 0.6667,
        within_range_rate: 0.6667,
        avg_error_pct: 1.2,
        avg_confidence: 62.4,
        current_method: "prior_only",
        fusion_profile_sample_count: 0,
        avg_blend_weight: 0,
        graph_coverage: 0,
        graph_context_used_rate: 0,
        prior_brier_delta: null,
        fusion_status: "bootstrapping",
      },
    ],
    empirical_calibration: [],
    breakdown: {
      by_country: [],
      by_scope: [],
      by_model: [],
    },
    fusion_profiles: [],
    graph_context_summary: {
      coverage_available: false,
      used_rate: 0,
      avg_coverage: 0,
      avg_score: 0,
      avg_peer_count: 0,
      records: 0,
      by_horizon: [],
    },
    fusion_status_summary: {
      active_model_version: "dist-studentt-v3.3-lfgraph",
      graph_coverage_available: false,
      avg_blend_weight: 0,
      method_mix: {
        prior_only: 1,
        learned_blended: 0,
        learned_blended_graph: 0,
      },
      horizons: [],
    },
    calibration: [],
    return_cohorts: [
      {
        prediction_type: "next_day",
        label: "1D",
        target_date: "2026-05-13",
        evaluated_total: 3,
        direction_accuracy: 0.6667,
        within_range_rate: 0.3333,
        avg_predicted_return_pct: 1.25,
        avg_realized_return_pct: -0.5,
        avg_return_error_pct: -1.75,
        avg_error_pct: 1.8,
        avg_confidence: 64.2,
        confidence_brier_score: 0.2144,
      },
    ],
    recent_trend: [],
    recent_records: [
      {
        id: 1,
        scope: "stock",
        symbol: "005930.KS",
        country_code: "KR",
        prediction_type: "next_day",
        prediction_label: "1D",
        target_date: "2026-05-13",
        reference_price: 100,
        predicted_close: 101,
        actual_close: 102,
        direction: "up",
        direction_hit: true,
        within_range: true,
        abs_error_pct: 1,
        confidence: 67,
        confidence_cap: 78,
        confidence_cap_reason: "bootstrap_profile_missing",
        empirical_profile_available: false,
        empirical_sample_count: 0,
        empirical_max_reliability_gap: null,
        empirical_brier_delta: null,
        up_probability: 61,
        model_version: "dist-studentt-v3.3-lfgraph",
        created_at: 1,
        evaluated_at: 2,
        fusion_method: "prior_only",
        fusion_blend_weight: 0,
        graph_context_used: false,
        graph_coverage: 0,
      },
    ],
    action_queue: [],
    failure_patterns: [],
    review_queue: [
      {
        id: 1,
        prediction_type: "next_day",
        prediction_label: "1D",
        scope: "stock",
        symbol: "005930.KS",
        country_code: "KR",
        target_date: "2026-05-13",
        direction: "up",
        direction_hit: true,
        within_range: true,
        abs_error_pct: 1,
        confidence: 67,
        fusion_method: "prior_only",
        graph_context_used: false,
        graph_coverage: 0,
        confidence_cap: 78,
        confidence_cap_reason: "bootstrap_profile_missing",
        empirical_profile_available: false,
        empirical_sample_count: 0,
        empirical_max_reliability_gap: null,
        empirical_brier_delta: null,
        review_kind: "clean-hit",
        review_summary: "1D 예측에서 005930.KS은 방향과 밴드를 모두 맞췄습니다.",
        stock_path: "/stock/005930.KS",
      },
    ],
    insights: ["검증 완료 표본을 기준으로 표시 confidence cap을 함께 확인합니다."],
  };
}

describe("PredictionLabDashboard", () => {
  it("최근 로그와 리뷰 큐에 confidence cap 사유를 표시한다", () => {
    render(<PredictionLabDashboard data={predictionLabData() as any} />);

    expect(screen.getByText(/표시 cap 78.0%/)).toBeInTheDocument();
    expect(screen.getAllByText(/bootstrap 보수 cap/).length).toBeGreaterThan(0);
    expect(screen.getByText(/cap 78.0 · bootstrap 보수 cap/)).toBeInTheDocument();
  });

  it("실현 수익률 cohort를 목표일별 검증 표로 표시한다", () => {
    render(<PredictionLabDashboard data={predictionLabData() as any} />);

    expect(screen.getByText("실현 수익률 cohort")).toBeInTheDocument();
    expect(screen.getByText("2026-05-13")).toBeInTheDocument();
    expect(screen.getByText("-0.50%")).toBeInTheDocument();
    expect(screen.getByText("-1.75%")).toBeInTheDocument();
    expect(screen.getByText("0.2144")).toBeInTheDocument();
  });
});
