"use client";

import Link from "next/link";

import type { SystemDiagnostics } from "@/lib/api";

interface Props {
  diagnostics: SystemDiagnostics;
  frontendVersion: string;
}

function statusTone(status: string) {
  if (status === "ok") return "text-positive bg-positive/10";
  if (status === "starting") return "text-warning bg-warning/10";
  return "text-negative bg-negative/10";
}

function statusLabel(status: string) {
  if (status === "ok") return "정상";
  if (status === "starting") return "시작 중";
  if (status === "configured") return "설정됨";
  if (status === "available") return "사용 가능";
  if (status === "best_effort") return "가능 범위 반영";
  if (status === "missing") return "미설정";
  return "주의";
}

export default function SystemStatusCard({ diagnostics, frontendVersion }: Props) {
  const primaryModel = diagnostics.forecast_models[0];
  const criticalSources = diagnostics.data_sources.slice(0, 4);
  const versionsAligned = frontendVersion === diagnostics.version;

  return (
    <div className="card !p-4">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 mb-4">
        <div>
          <h2 className="font-semibold text-lg">시스템 준비 상태</h2>
          <p className="text-sm text-text-secondary mt-1">
            API v{diagnostics.version} · 예측 모델 {diagnostics.forecast_models.map((item) => item.version).join(" / ") || "N/A"}
          </p>
        </div>
        <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold tracking-wide ${statusTone(diagnostics.status)}`}>
          {statusLabel(diagnostics.status)}
        </div>
      </div>

      <div className="flex items-center justify-end mb-4">
        <Link href="/lab" className="text-sm text-accent hover:underline">
          예측 연구실 열기
        </Link>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary">프론트 배포 버전</div>
          <div className="mt-1 text-lg font-semibold text-text">v{frontendVersion}</div>
          <div className="mt-2 text-xs leading-5 text-text-secondary">
            현재 브라우저에 내려온 UI 빌드 버전입니다.
          </div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary">백엔드 배포 버전</div>
          <div className="mt-1 text-lg font-semibold text-text">v{diagnostics.version}</div>
          <div className="mt-2 text-xs leading-5 text-text-secondary">
            시스템 진단과 `/api/health`가 보고하는 API 버전입니다.
          </div>
        </div>
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary">운영 반영 상태</div>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${
                versionsAligned ? "bg-positive/10 text-positive" : "bg-warning/10 text-warning"
              }`}
            >
              {versionsAligned ? "프론트·백엔드 버전 일치" : "배포 전파 확인 필요"}
            </span>
          </div>
          <div className="mt-2 text-xs leading-5 text-text-secondary">
            {versionsAligned
              ? "현재 화면과 API가 같은 릴리즈 버전을 사용 중입니다."
              : "머지 직후에는 프론트와 백엔드 버전이 잠시 어긋날 수 있습니다. 운영 반영 대기 스크립트나 health를 다시 확인해 주세요."}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">예측 스냅샷</div>
          {diagnostics.prediction_accuracy ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <span>저장된 예측</span>
                <span className="font-semibold">{diagnostics.prediction_accuracy.stored_predictions}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>방향 적중률</span>
                <span className="font-semibold">{(diagnostics.prediction_accuracy.direction_accuracy * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>밴드 적중률</span>
                <span className="font-semibold">{(diagnostics.prediction_accuracy.within_range_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between gap-3">
                <span>평균 오차</span>
                <span className="font-semibold">{diagnostics.prediction_accuracy.avg_error_pct.toFixed(2)}%</span>
              </div>
            </div>
          ) : (
            <div className="text-sm text-text-secondary">
              {diagnostics.prediction_accuracy_error || "아직 정확도 이력이 충분히 쌓이지 않았습니다."}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">시작 작업</div>
          <div className="space-y-2">
            {diagnostics.startup_tasks.map((task) => (
              <div key={task.name} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium">{task.name}</div>
                  <div className="text-xs text-text-secondary mt-1">{task.detail}</div>
                </div>
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide ${statusTone(task.status)}`}>
                  {statusLabel(task.status)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">핵심 데이터 소스</div>
          <div className="space-y-2">
            {criticalSources.map((source) => (
              <div key={source.name} className="rounded-lg bg-border/30 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm">{source.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide ${statusTone(source.configured ? "ok" : "degraded")}`}>
                    {statusLabel(source.status)}
                  </span>
                </div>
                <div className="text-xs text-text-secondary mt-1">{source.purpose}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {primaryModel ? (
        <div className="mt-4 rounded-xl border border-border p-3">
          <div className="text-xs font-medium text-text-secondary mb-2">예측 모델</div>
          <div className="space-y-3">
            {diagnostics.forecast_models.map((model) => (
              <div key={`${model.name}-${model.version}`} className="rounded-lg bg-border/20 px-3 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm">{model.name}</span>
                  <span className="text-xs text-text-secondary">{model.version}</span>
                </div>
                <div className="text-sm mt-1">지원 시장: {model.markets.join(", ")}</div>
                <div className="text-xs text-text-secondary mt-1">핵심 신호: {model.signals.slice(0, 5).join(", ")}</div>
                <div className="text-xs text-text-secondary mt-2">{model.notes.join(" ")}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

