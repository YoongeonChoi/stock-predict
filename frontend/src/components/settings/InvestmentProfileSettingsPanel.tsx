"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { api, type InvestmentProfile, type InvestmentProfileCode, type InvestmentProfileOption } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";

const PROFILE_ORDER: InvestmentProfileCode[] = [
  "capital_preservation",
  "conservative",
  "balanced",
  "growth",
  "aggressive",
];

const FALLBACK_OPTIONS: InvestmentProfileOption[] = [
  {
    profile_code: "capital_preservation",
    profile_label: "원금보존형",
    description: "현금 비중과 하락 방어를 우선합니다.",
    risk_tolerance: 1,
    recommended_equity_pct: 58,
    cash_buffer_pct: 42,
    max_single_weight_pct: 9.5,
    optimization_style: "defensive",
  },
  {
    profile_code: "conservative",
    profile_label: "안정추구형",
    description: "확신도와 분산을 중시합니다.",
    risk_tolerance: 2,
    recommended_equity_pct: 70,
    cash_buffer_pct: 30,
    max_single_weight_pct: 11.5,
    optimization_style: "defensive",
  },
  {
    profile_code: "balanced",
    profile_label: "균형형",
    description: "수익과 리스크를 균형 있게 반영합니다.",
    risk_tolerance: 3,
    recommended_equity_pct: 82,
    cash_buffer_pct: 18,
    max_single_weight_pct: 14.5,
    optimization_style: "balanced",
  },
  {
    profile_code: "growth",
    profile_label: "성장추구형",
    description: "기대초과수익과 상승 확률을 더 중시합니다.",
    risk_tolerance: 4,
    recommended_equity_pct: 90,
    cash_buffer_pct: 10,
    max_single_weight_pct: 17.5,
    optimization_style: "offensive",
  },
  {
    profile_code: "aggressive",
    profile_label: "적극투자형",
    description: "높은 기회 점수를 더 적극 반영하되 손실 guard는 유지합니다.",
    risk_tolerance: 5,
    recommended_equity_pct: 94,
    cash_buffer_pct: 6,
    max_single_weight_pct: 21,
    optimization_style: "offensive",
  },
];

function sortOptions(options: InvestmentProfileOption[]) {
  return [...options].sort((left, right) => (
    PROFILE_ORDER.indexOf(left.profile_code) - PROFILE_ORDER.indexOf(right.profile_code)
  ));
}

function styleLabel(style: string) {
  if (style === "defensive") return "방어형";
  if (style === "offensive") return "공격형";
  return "균형형";
}

export default function InvestmentProfileSettingsPanel() {
  const { loading: authLoading, session } = useAuth();
  const { toast } = useToast();
  const [profile, setProfile] = useState<InvestmentProfile | null>(null);
  const [options, setOptions] = useState<InvestmentProfileOption[]>(FALLBACK_OPTIONS);
  const [selectedCode, setSelectedCode] = useState<InvestmentProfileCode>("balanced");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedOption = useMemo(
    () => options.find((option) => option.profile_code === selectedCode) ?? FALLBACK_OPTIONS[2],
    [options, selectedCode],
  );

  const load = useCallback(async () => {
    if (!session) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    const [profileResult, optionsResult] = await Promise.allSettled([
      api.getInvestmentProfile(),
      api.getInvestmentProfileOptions(),
    ]);

    if (optionsResult.status === "fulfilled") {
      setOptions(sortOptions(optionsResult.value.options));
    } else {
      setOptions(FALLBACK_OPTIONS);
    }

    if (profileResult.status === "fulfilled") {
      setProfile(profileResult.value);
      setSelectedCode(profileResult.value.profile_code);
    } else {
      console.error(profileResult.reason);
      setProfile(null);
      setSelectedCode("balanced");
      setErrorMessage(getUserFacingErrorMessage(profileResult.reason, "투자 성향을 불러오지 못했습니다."));
    }
    setLoading(false);
  }, [session]);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void load();
  }, [authLoading, load]);

  const save = async () => {
    if (!session) {
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    try {
      const saved = await api.updateInvestmentProfile({ profile_code: selectedCode });
      setProfile(saved);
      setSelectedCode(saved.profile_code);
      toast("투자 성향을 저장했습니다.", "success");
    } catch (error) {
      console.error(error);
      const message = getUserFacingErrorMessage(error, "투자 성향을 저장하지 못했습니다.");
      setErrorMessage(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || loading) {
    return (
      <WorkspaceLoadingCard
        title="투자 성향 설정을 불러오고 있습니다"
        message="계정별 추천 정책을 확인하는 중입니다."
        className="min-h-[220px]"
      />
    );
  }

  if (!session) {
    return (
      <WorkspaceStateCard
        eyebrow="로그인 필요"
        title="투자 성향은 로그인 후 저장할 수 있습니다"
        message="계정별 포트폴리오 추천에 쓰이는 설정이라 로그인 세션이 필요합니다."
        tone="warning"
      />
    );
  }

  return (
    <section className="card !p-5 space-y-5" aria-labelledby="investment-profile-title">
      <div className="section-heading">
        <div>
          <h2 id="investment-profile-title" className="section-title">투자 성향</h2>
          <p className="section-copy">저장된 성향은 포트폴리오 추천의 후보 기준, 현금 버퍼, 종목별 비중 상한에 반영됩니다.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {profile?.persisted ? (
            <span className="info-chip">{profile.profile_label}</span>
          ) : (
            <span className="info-chip">기본값</span>
          )}
          <span className="info-chip">{profile?.policy_version ?? "investment-policy-v1"}</span>
        </div>
      </div>

      {errorMessage ? (
        <WorkspaceStateCard
          eyebrow="투자 성향 지연"
          title="투자 성향 정보를 다시 확인해 주세요"
          message={errorMessage}
          tone="warning"
          actionLabel="다시 불러오기"
          onAction={load}
        />
      ) : null}

      <div className="grid gap-3 lg:grid-cols-5">
        {options.map((option) => {
          const inputId = `investment-profile-${option.profile_code}`;
          const selected = option.profile_code === selectedCode;
          return (
            <label
              key={option.profile_code}
              htmlFor={inputId}
              className={[
                "min-h-[188px] cursor-pointer rounded-[22px] border px-4 py-4 transition-colors focus-within:ring-2 focus-within:ring-accent/35",
                selected ? "border-accent bg-accent/5" : "border-border/75 bg-surface/45 hover:border-accent/35",
              ].join(" ")}
            >
              <input
                id={inputId}
                type="radio"
                name="investment-profile"
                value={option.profile_code}
                checked={selected}
                onChange={() => setSelectedCode(option.profile_code)}
                className="sr-only"
              />
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-text">{option.profile_label}</div>
                  <div className="mt-1 text-xs text-text-secondary">위험 선호 {option.risk_tolerance}단계</div>
                </div>
                <span className="rounded-full border border-border bg-white px-2 py-1 text-[11px] text-text-secondary">
                  {styleLabel(option.optimization_style)}
                </span>
              </div>
              <p className="mt-3 min-h-[48px] text-sm leading-6 text-text-secondary">{option.description}</p>
              <div className="mt-4 grid gap-2 text-[12px] text-text-secondary">
                <div className="flex justify-between gap-3">
                  <span>주식 비중</span>
                  <span className="font-mono font-semibold text-text">{option.recommended_equity_pct.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span>현금 버퍼</span>
                  <span className="font-mono font-semibold text-text">{option.cash_buffer_pct.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span>단일 종목</span>
                  <span className="font-mono font-semibold text-text">{option.max_single_weight_pct.toFixed(1)}%</span>
                </div>
              </div>
            </label>
          );
        })}
      </div>

      <div className="section-slab-subtle flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm leading-6 text-text-secondary">
          선택: <span className="font-semibold text-text">{selectedOption.profile_label}</span>
          <span className="mx-2 text-border">/</span>
          주식 {selectedOption.recommended_equity_pct.toFixed(0)}%, 현금 {selectedOption.cash_buffer_pct.toFixed(0)}%
        </div>
        <button
          type="button"
          onClick={save}
          disabled={saving || selectedCode === profile?.profile_code}
          className="ui-button-primary w-full sm:w-auto"
        >
          {saving ? "저장 중..." : "투자 성향 저장"}
        </button>
      </div>
    </section>
  );
}
