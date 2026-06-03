import { Suspense } from "react";
import type { Metadata } from "next";

import PageHeader from "@/components/PageHeader";
import AuthPageClient from "@/components/auth/AuthPageClient";

export const metadata: Metadata = {
  title: "로그인 및 회원가입 | Stock Predict",
};

function AuthPageFallback() {
  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="계정"
        title="로그인 및 회원가입"
        description="보유 종목, 추천 결과, 자산 기준을 계정별로 안전하게 분리해 저장합니다."
        meta={<span className="info-chip">로그인</span>}
      />
      <section className="card !p-5">
        <div className="h-48 animate-pulse rounded-[8px] bg-surface-muted" aria-hidden="true" />
      </section>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<AuthPageFallback />}>
      <AuthPageClient />
    </Suspense>
  );
}
