"use client";

import { useEffect, useState } from "react";

import ErrorBanner from "@/components/ErrorBanner";
import PageHeader from "@/components/PageHeader";
import PredictionLabDashboard from "@/components/PredictionLabDashboard";
import { api } from "@/lib/api";
import type { PredictionLabResponse } from "@/lib/api";

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "알 수 없는 오류가 발생했습니다.");
}

export default function LabPage() {
  const [data, setData] = useState<PredictionLabResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    api.getPredictionLab(40, true)
      .then(setData)
      .catch((err) => {
        console.error(err);
        setError(toError(err));
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-shell">
      <PageHeader
        eyebrow="Prediction Lab"
        title="예측 연구실"
        description="예측 방향 적중률, 밴드 적중률, 평균 오차, 보정 상태를 같은 기준으로 묶어 사후 검증 흐름을 더 또렷하게 정리했습니다."
        meta={
          <>
            <span className="info-chip">방향 적중률</span>
            <span className="info-chip">밴드 적중률</span>
            <span className="info-chip">Calibration 추적</span>
          </>
        }
      />

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {loading ? (
        <div className="animate-pulse space-y-4">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">{[1, 2, 3, 4, 5].map((item) => <div key={item} className="h-28 rounded-xl bg-border" />)}</div>
          <div className="h-96 rounded-xl bg-border" />
          <div className="h-96 rounded-xl bg-border" />
        </div>
      ) : data ? (
        <PredictionLabDashboard data={data} />
      ) : (
        <div className="card text-text-secondary">예측 연구실 데이터를 아직 불러오지 못했습니다.</div>
      )}
    </div>
  );
}
