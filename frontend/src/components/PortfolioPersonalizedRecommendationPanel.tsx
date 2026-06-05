"use client";

import PortfolioRecommendationPanel from "@/components/PortfolioRecommendationPanel";
import type { PortfolioPersonalizedRecommendationResponse } from "@/lib/api";

interface Props {
  data: PortfolioPersonalizedRecommendationResponse | null;
  loading: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
}

export default function PortfolioPersonalizedRecommendationPanel({ data, loading, errorMessage = null, onRetry }: Props) {
  return (
    <PortfolioRecommendationPanel
      title="개인화 추천"
      description="설정에 저장한 투자 성향을 기준으로 후보 통과 기준, 현금 버퍼, 목표 비중을 조정합니다."
      loading={loading}
      budget={data?.budget}
      recommendationPolicy={data?.recommendation_policy}
      summary={data?.summary}
      recommendations={data?.recommendations}
      notes={data?.notes}
      marketView={data?.market_view}
      emptyMessage="현재 투자 성향 기준을 통과하는 신규 후보가 충분하지 않습니다. 설정에서 성향을 바꾸거나 시장 후보가 더 쌓인 뒤 다시 확인해 보세요."
      errorMessage={errorMessage}
      onRetry={onRetry}
    />
  );
}
