import type { ReactNode } from "react";
import Link from "next/link";

import PageHeader from "@/components/PageHeader";

interface AuthGateCardProps {
  title: string;
  description: string;
  nextPath: string;
  preview?: ReactNode;
  previewTitle?: string;
}

export default function AuthGateCard({
  title,
  description,
  nextPath,
  preview = null,
  previewTitle = "로그인 전 미리보기",
}: AuthGateCardProps) {
  const authHref = `/auth?next=${encodeURIComponent(nextPath)}`;

  return (
    <div className="page-shell space-y-5">
      <PageHeader
        eyebrow="계정"
        title={title}
        description={description}
        meta={<span className="info-chip">계정별 데이터 분리</span>}
        actions={
          <>
            <Link href={authHref} className="action-chip-primary">
              로그인하기
            </Link>
            <Link href={`/auth?mode=signup&next=${encodeURIComponent(nextPath)}`} className="action-chip-secondary">
              회원가입
            </Link>
          </>
        }
      />
      <section className="card !p-5 space-y-3">
        <div className="text-sm font-semibold text-text">로그인이 필요한 이유</div>
        <div className="text-sm leading-7 text-text-secondary">
          관심종목, 포트폴리오, 추천 결과는 이제 계정별로 완전히 분리됩니다. 로그인 후에는 다른 사용자와 데이터가 섞이지 않도록
          Supabase 계정 기준으로 저장됩니다.
        </div>
      </section>
      {preview ? (
        <section className="card !p-5 space-y-4">
          <div>
            <div className="text-sm font-semibold text-text">{previewTitle}</div>
            <div className="mt-1 text-sm leading-6 text-text-secondary">
              공개 데이터 기준으로 먼저 읽어 볼 수 있는 흐름만 보여줍니다. 로그인하면 저장, 추적, 추천 반영이 바로 연결됩니다.
            </div>
          </div>
          {preview}
        </section>
      ) : null}
    </div>
  );
}
