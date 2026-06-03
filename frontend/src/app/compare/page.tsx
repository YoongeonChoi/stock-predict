import { Suspense } from "react";
import type { Metadata } from "next";

import PageHeader from "@/components/PageHeader";
import ComparePageClient from "@/components/pages/ComparePageClient";

export const metadata: Metadata = {
  title: "종목 비교 | Stock Predict",
};

function ComparePageFallback() {
  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="시장 탐색"
        title="종목 비교"
        description="종목 2~4개 나란히 비교하면서 가격, 밸류에이션, 성장 지표, 종합 점수를 같은 축에서 한 번에 봅니다."
        meta={
          <>
            <span className="status-token">2-4개 종목</span>
            <span className="status-token">공통 지표 정렬</span>
          </>
        }
      />
      <section className="card !p-5">
        <div className="h-32 animate-pulse rounded-[8px] bg-surface-muted" aria-hidden="true" />
      </section>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<ComparePageFallback />}>
      <ComparePageClient />
    </Suspense>
  );
}
