"use client";

import { useEffect, useState } from "react";

import PredictionLabDashboard from "@/components/PredictionLabDashboard";
import ErrorBanner from "@/components/ErrorBanner";
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
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Prediction Lab</h1>
        <p className="text-text-secondary mt-1">실전 예측 엔진의 검증, 보정, 연구 지표를 한곳에서 확인하는 공간입니다.</p>
      </div>

      {error ? <ErrorBanner error={error} onRetry={() => window.location.reload()} /> : null}

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
            {[1, 2, 3, 4, 5].map((item) => <div key={item} className="h-28 bg-border rounded-xl" />)}
          </div>
          <div className="h-96 bg-border rounded-xl" />
          <div className="h-96 bg-border rounded-xl" />
        </div>
      ) : data ? (
        <PredictionLabDashboard data={data} />
      ) : (
        <div className="card text-text-secondary">Prediction Lab 데이터가 아직 준비되지 않았습니다.</div>
      )}
    </div>
  );
}

