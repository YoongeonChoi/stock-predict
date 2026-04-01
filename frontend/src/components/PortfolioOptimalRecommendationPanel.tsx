"use client";

import PortfolioRecommendationPanel from "@/components/PortfolioRecommendationPanel";
import type { PortfolioOptimalRecommendationResponse } from "@/lib/api";

interface Props {
  data: PortfolioOptimalRecommendationResponse | null;
  loading: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
}

export default function PortfolioOptimalRecommendationPanel({ data, loading, errorMessage = null, onRetry }: Props) {
  return (
    <PortfolioRecommendationPanel
      title="최적 추천"
      description="현재 포트폴리오의 과대집중도와 각 시장의 체제를 함께 보고, 지금 기준으로 가장 효율적인 신규 자금 배분안을 자동으로 계산합니다."
      loading={loading}
      budget={data?.budget}
      summary={data?.summary}
      recommendations={data?.recommendations}
      notes={data?.notes}
      marketView={data?.market_view}
      emptyMessage="지금은 신규 자금을 급하게 배분하기보다 기존 포지션 관리가 우선으로 보입니다. 더 강한 셋업이 쌓일 때까지 관망하는 편이 낫습니다."
      errorMessage={errorMessage}
      onRetry={onRetry}
    />
  );
}
