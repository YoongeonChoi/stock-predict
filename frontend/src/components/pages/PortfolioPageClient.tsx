"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import AuthGateCard from "@/components/AuthGateCard";
import { useAuth } from "@/components/AuthProvider";
import PortfolioConditionalRecommendationPanel from "@/components/PortfolioConditionalRecommendationPanel";
import PortfolioEventRadar from "@/components/PortfolioEventRadar";
import PortfolioModelPanel from "@/components/PortfolioModelPanel";
import PortfolioOptimalRecommendationPanel from "@/components/PortfolioOptimalRecommendationPanel";
import PortfolioRiskPanel from "@/components/PortfolioRiskPanel";
import TickerResolutionHint from "@/components/TickerResolutionHint";
import { useToast } from "@/components/Toast";
import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import { ApiError, api } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import type {
  PortfolioConditionalRecommendationFilters,
  PortfolioConditionalRecommendationResponse,
  PortfolioData,
  PortfolioEventRadarResponse,
  PortfolioHolding,
  PortfolioOptimalRecommendationResponse,
  PortfolioProfile,
  TickerResolution,
} from "@/lib/api";
import type { OpportunityRadarResponse } from "@/lib/types";
import { changeColor, formatPct, formatPrice } from "@/lib/utils";

const COLORS = ["#2563eb", "#0f172a", "#f59e0b", "#0ea5e9", "#22c55e", "#64748b", "#14b8a6", "#e11d48"];
const DEFAULT_RECOMMENDATION_FILTERS: PortfolioConditionalRecommendationFilters = {
  country_code: "KR",
  sector: "ALL",
  style: "balanced",
  max_items: 5,
  min_up_probability: 54,
  exclude_holdings: true,
  watchlist_only: false,
};

const TICKER_GUIDE = {
  KR: {
    label: "기본 입력 규칙",
    placeholder: "005930 또는 005930.KS",
    helper: "국내 종목은 숫자 6자리만 입력해도 표준 티커 형식으로 자동 해석합니다.",
  },
} as const;

interface HoldingFormState {
  ticker: string;
  buyPrice: string;
  quantity: string;
  buyDate: string;
  countryCode: string;
}

interface ProfileFormState {
  totalAssets: string;
  cashBalance: string;
  monthlyBudget: string;
}

const EMPTY_HOLDING_FORM: HoldingFormState = {
  ticker: "",
  buyPrice: "",
  quantity: "",
  buyDate: new Date().toISOString().slice(0, 10),
  countryCode: "KR",
};

function getApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.detail) {
      return `${error.errorCode} · ${error.detail}`;
    }
    return `${error.errorCode} · ${error.message}`;
  }
  return fallback;
}

function riskLevelLabel(level: string) {
  if (level === "high") return "높음";
  if (level === "medium") return "보통";
  return "낮음";
}

function tradeActionLabel(action?: string | null) {
  if (action === "accumulate") return "분할 매수";
  if (action === "reduce_risk") return "리스크 축소";
  if (action === "breakout_watch") return "돌파 감시";
  if (action === "wait_pullback") return "눌림 대기";
  if (action === "avoid") return "관망";
  return "없음";
}

function executionBiasLabel(bias?: string | null) {
  if (bias === "press_long") return "추세 대응";
  if (bias === "lean_long") return "상방 우세";
  if (bias === "reduce_risk") return "리스크 관리";
  if (bias === "capital_preservation") return "방어 우선";
  return "선별 대응";
}

function executionBiasTone(bias?: string | null) {
  if (bias === "press_long") return "text-positive bg-positive/10";
  if (bias === "lean_long") return "text-emerald-500 bg-emerald-500/10";
  if (bias === "reduce_risk") return "text-amber-500 bg-amber-500/10";
  if (bias === "capital_preservation") return "text-negative bg-negative/10";
  return "text-text-secondary bg-surface";
}

function formatAssetValue(value: number) {
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
}

function formatQuantity(value: number) {
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function SummaryMetric({
  label,
  value,
  tone = "text-text",
  helper,
}: {
  label: string;
  value: string;
  tone?: string;
  helper?: string;
}) {
  return (
    <div className="metric-card">
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`mt-3 text-2xl font-bold ${tone}`}>{value}</div>
      {helper ? <div className="mt-2 text-[11px] text-text-secondary">{helper}</div> : null}
    </div>
  );
}

function buildProfileForm(profile?: PortfolioProfile | null): ProfileFormState {
  return {
    totalAssets: profile?.total_assets ? String(profile.total_assets) : "",
    cashBalance: profile?.cash_balance ? String(profile.cash_balance) : "",
    monthlyBudget: profile?.monthly_budget ? String(profile.monthly_budget) : "",
  };
}

interface PortfolioPageClientProps {
  demoData?: OpportunityRadarResponse | null;
}

export default function PortfolioPageClient({ demoData = null }: PortfolioPageClientProps) {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [portfolioLoadError, setPortfolioLoadError] = useState<string | null>(null);
  const [submittingHolding, setSubmittingHolding] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [formError, setFormError] = useState("");
  const [profileError, setProfileError] = useState("");
  const [holdingForm, setHoldingForm] = useState<HoldingFormState>(EMPTY_HOLDING_FORM);
  const [profileForm, setProfileForm] = useState<ProfileFormState>(buildProfileForm(null));
  const [editingHoldingId, setEditingHoldingId] = useState<number | null>(null);
  const [resolution, setResolution] = useState<TickerResolution | null>(null);
  const [eventRadar, setEventRadar] = useState<PortfolioEventRadarResponse | null>(null);
  const [conditionalFilters, setConditionalFilters] = useState<PortfolioConditionalRecommendationFilters>(DEFAULT_RECOMMENDATION_FILTERS);
  const [conditionalRecommendation, setConditionalRecommendation] = useState<PortfolioConditionalRecommendationResponse | null>(null);
  const [optimalRecommendation, setOptimalRecommendation] = useState<PortfolioOptimalRecommendationResponse | null>(null);
  const [conditionalLoading, setConditionalLoading] = useState(true);
  const [conditionalRunning, setConditionalRunning] = useState(false);
  const [optimalLoading, setOptimalLoading] = useState(true);
  const [eventRadarLoading, setEventRadarLoading] = useState(true);
  const { toast } = useToast();
  const { session, loading: authLoading } = useAuth();

  const activeGuide = TICKER_GUIDE[holdingForm.countryCode as keyof typeof TICKER_GUIDE] ?? TICKER_GUIDE.KR;
  const summary = data?.summary;
  const hasHoldings = Boolean(summary && summary.holding_count > 0);
  const mixedCountries = useMemo(() => false, []);
  const demoPreviewItems = (demoData?.opportunities || []).slice(0, 2);

  const loadPortfolio = async (showFailureToast = false) => {
    if (!session) {
      return;
    }
    try {
      const next = await api.getPortfolio();
      setData(next);
      setProfileForm(buildProfileForm(next.profile));
      setPortfolioLoadError(null);
    } catch (error) {
      console.error(error);
      setPortfolioLoadError(getUserFacingErrorMessage(error, "포트폴리오를 다시 불러오지 못했습니다."));
      if (showFailureToast) {
        toast(getApiErrorMessage(error, "포트폴리오를 다시 불러오지 못했습니다."), "error");
      }
    }
  };

  const refreshSupportPanels = async (filters: PortfolioConditionalRecommendationFilters = conditionalFilters) => {
    if (!session) {
      return;
    }
    setConditionalLoading(true);
    setOptimalLoading(true);
    setEventRadarLoading(true);
    const [eventResult, conditionalResult, optimalResult] = await Promise.allSettled([
      api.getPortfolioEventRadar(14),
      api.getPortfolioConditionalRecommendation(filters),
      api.getPortfolioOptimalRecommendation(),
    ]);

    if (eventResult.status === "fulfilled") {
      setEventRadar(eventResult.value);
    }
    if (conditionalResult.status === "fulfilled") {
      setConditionalRecommendation(conditionalResult.value);
    }
    if (optimalResult.status === "fulfilled") {
      setOptimalRecommendation(optimalResult.value);
    }

    setConditionalLoading(false);
    setOptimalLoading(false);
    setEventRadarLoading(false);
  };
  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!session) {
      setLoading(false);
      setConditionalLoading(false);
      setOptimalLoading(false);
      setEventRadarLoading(false);
      return;
    }

    const loadWorkspace = async () => {
      setLoading(true);
      const [portfolioResult, eventResult, conditionalResult, optimalResult] = await Promise.allSettled([
        api.getPortfolio(),
        api.getPortfolioEventRadar(14),
        api.getPortfolioConditionalRecommendation(DEFAULT_RECOMMENDATION_FILTERS),
        api.getPortfolioOptimalRecommendation(),
      ]);

      if (portfolioResult.status === "fulfilled") {
        setData(portfolioResult.value);
        setProfileForm(buildProfileForm(portfolioResult.value.profile));
        setPortfolioLoadError(null);
      } else {
        console.error(portfolioResult.reason);
        setPortfolioLoadError(
          getUserFacingErrorMessage(
            portfolioResult.reason,
            "포트폴리오를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          ),
        );
      }
      if (eventResult.status === "fulfilled") {
        setEventRadar(eventResult.value);
      } else {
        console.error(eventResult.reason);
      }
      if (conditionalResult.status === "fulfilled") {
        setConditionalRecommendation(conditionalResult.value);
      } else {
        console.error(conditionalResult.reason);
      }
      if (optimalResult.status === "fulfilled") {
        setOptimalRecommendation(optimalResult.value);
      } else {
        console.error(optimalResult.reason);
      }

      setConditionalLoading(false);
      setOptimalLoading(false);
      setEventRadarLoading(false);
      setLoading(false);
    };

    loadWorkspace();
  }, [authLoading, session]);

  useEffect(() => {
    const trimmed = holdingForm.ticker.trim();
    if (!trimmed) {
      setResolution(null);
      return;
    }
    const timer = setTimeout(() => {
      api.resolveTicker(trimmed, holdingForm.countryCode).then(setResolution).catch(() => setResolution(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [holdingForm.ticker, holdingForm.countryCode]);

  const resetHoldingForm = () => {
    setHoldingForm(EMPTY_HOLDING_FORM);
    setEditingHoldingId(null);
    setFormError("");
    setResolution(null);
  };

  const submitHolding = async () => {
    const trimmedTicker = holdingForm.ticker.trim();
    const parsedBuyPrice = Number(holdingForm.buyPrice);
    const parsedQuantity = Number(holdingForm.quantity);

    if (!trimmedTicker) {
      const message = "티커를 먼저 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }
    if (!Number.isFinite(parsedBuyPrice) || parsedBuyPrice <= 0) {
      const message = "매수가는 0보다 큰 숫자로 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      const message = "수량은 0보다 큰 숫자로 입력해 주세요.";
      setFormError(message);
      toast(message, "error");
      return;
    }

    setSubmittingHolding(true);
    setFormError("");
    try {
      const payload = {
        ticker: trimmedTicker.toUpperCase(),
        buy_price: parsedBuyPrice,
        quantity: parsedQuantity,
        buy_date: holdingForm.buyDate,
        country_code: holdingForm.countryCode,
      };
      const saved = editingHoldingId != null
        ? await api.updatePortfolioHolding(editingHoldingId, payload)
        : await api.addPortfolioHolding(payload);
      await loadPortfolio();
      await refreshSupportPanels();
      resetHoldingForm();
      toast(
        editingHoldingId != null
          ? `${saved.name} (${saved.ticker}) 보유 종목 정보를 수정했습니다.`
          : `${saved.name} (${saved.ticker}) 종목을 포트폴리오에 추가했습니다.`,
        "success",
      );
    } catch (error) {
      console.error(error);
      const message = getApiErrorMessage(error, "보유 종목 저장 중 문제가 발생했습니다.");
      setFormError(message);
      toast(message, "error");
    } finally {
      setSubmittingHolding(false);
    }
  };

  const saveProfile = async () => {
    setSavingProfile(true);
    setProfileError("");
    try {
      const nextProfile = await api.updatePortfolioProfile({
        total_assets: Number(profileForm.totalAssets || 0),
        cash_balance: Number(profileForm.cashBalance || 0),
        monthly_budget: Number(profileForm.monthlyBudget || 0),
      });
      setProfileForm(buildProfileForm(nextProfile));
      await loadPortfolio();
      toast("자산 관리 기준을 저장했습니다.", "success");
    } catch (error) {
      console.error(error);
      const message = getApiErrorMessage(error, "자산 관리 설정을 저장하지 못했습니다.");
      setProfileError(message);
      toast(message, "error");
    } finally {
      setSavingProfile(false);
    }
  };

  const startEdit = (holding: PortfolioHolding) => {
    setEditingHoldingId(holding.id);
    setHoldingForm({
      ticker: holding.ticker,
      buyPrice: String(holding.buy_price),
      quantity: String(holding.quantity),
      buyDate: holding.buy_date,
      countryCode: holding.country_code,
    });
    setFormError("");
  };

  const removeHolding = async (id: number) => {
    try {
      await api.removePortfolioHolding(id);
      if (editingHoldingId === id) {
        resetHoldingForm();
      }
      await loadPortfolio();
      await refreshSupportPanels();
      toast("보유 종목을 삭제했습니다.", "info");
    } catch (error) {
      console.error(error);
      toast(getApiErrorMessage(error, "보유 종목을 삭제하지 못했습니다."), "error");
    }
  };

  const runConditionalRecommendation = async () => {
    setConditionalRunning(true);
    setConditionalLoading(true);
    try {
      const response = await api.getPortfolioConditionalRecommendation(conditionalFilters);
      setConditionalRecommendation(response);
    } catch (error) {
      console.error(error);
      toast(getApiErrorMessage(error, "조건 추천을 계산하지 못했습니다."), "error");
    } finally {
      setConditionalRunning(false);
      setConditionalLoading(false);
    }
  };

  if (!session) {
    return (
      <AuthGateCard
        title="포트폴리오는 로그인 후 관리합니다"
        description="총자산, 보유 종목, 추천 결과를 계정별로 분리 저장하려면 먼저 로그인해 주세요."
        nextPath="/portfolio"
        previewTitle="공개 레이더 기반 포트폴리오 미리보기"
        preview={
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="metric-card">
                <div className="text-xs text-text-secondary">리스크 버짓</div>
                <div className="mt-3 text-2xl font-bold text-text">주식 82%</div>
                <div className="mt-2 text-[11px] text-text-secondary">공개 KR 레이더 기준 기본 예시</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">관찰 후보</div>
                <div className="mt-3 text-2xl font-bold text-text">{demoData?.opportunities.slice(0, 3).length ?? 0}개</div>
                <div className="mt-2 text-[11px] text-text-secondary">상위 후보만 먼저 미리보기</div>
              </div>
              <div className="metric-card">
                <div className="text-xs text-text-secondary">로그인 후 가능</div>
                <div className="mt-3 text-lg font-semibold text-text">저장 · 추적 · 추천</div>
                <div className="mt-2 text-[11px] text-text-secondary">보유 종목과 추천을 계정별로 연결</div>
              </div>
            </div>
            <div className="grid gap-3">
              {(demoData?.opportunities || []).slice(0, 3).map((item) => (
                <div key={`portfolio-demo-${item.ticker}`} className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <div className="font-medium text-text">{item.name}</div>
                      <div className="mt-1 text-xs text-text-secondary">
                        {item.ticker} · {item.sector} · 레이더 미리보기
                      </div>
                      <div className="mt-2 text-sm leading-6 text-text-secondary">
                        공개 레이더 상위 후보를 먼저 보여주고, 로그인 후에는 실제 보유 종목 기준 추천과 비중 조정을 이어갑니다.
                      </div>
                    </div>
                    <div className="grid shrink-0 grid-cols-2 gap-3 text-sm md:min-w-[220px]">
                      <div>
                        <div className="text-[11px] text-text-secondary">현재가</div>
                        <div className="font-semibold text-text">{formatPrice(item.current_price, item.country_code)}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-text-secondary">등락률</div>
                        <div className={changeColor(item.change_pct ?? 0)}>{formatPct(item.change_pct)}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-text-secondary">레이더 점수</div>
                        <div className="font-semibold text-text">{item.opportunity_score?.toFixed(1) ?? "대기"}</div>
                      </div>
                      <div>
                        <div className="text-[11px] text-text-secondary">국가</div>
                        <div className="font-semibold text-text">{item.country_code}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        }
      />
    );
  }

  if (loading) {
    return (
      <div className="page-shell space-y-5">
        <section className="card !p-5 space-y-3">
          <div className="section-heading">
            <div>
              <h1 className="section-title text-2xl">포트폴리오</h1>
              <p className="section-copy">총자산, 보유 종목, 추천 패널을 계정 기준으로 순서대로 준비합니다.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="info-chip">계정별 자산</span>
              <span className="info-chip">불러오는 중</span>
            </div>
          </div>
        </section>
        <WorkspaceLoadingCard
          title="자산 요약과 보유 비중을 계산하고 있습니다"
          message="총자산, 예수금, 보유 평가액을 먼저 읽어 운영 요약으로 다시 묶는 중입니다."
          className="min-h-[180px]"
        />
        <WorkspaceLoadingCard
          title="보유 종목과 추천 패널을 준비하고 있습니다"
          message="보유 종목, 이벤트 레이더, 조건 추천을 같은 작업 흐름으로 채우는 중입니다."
          className="min-h-[260px]"
        />
      </div>
    );
  }

  if (!data && portfolioLoadError) {
    return (
      <div className="page-shell space-y-5">
        <section className="card !p-5 space-y-3">
          <div className="section-heading">
            <div>
              <h1 className="section-title text-2xl">포트폴리오</h1>
              <p className="section-copy">총자산과 보유 종목을 먼저 정리하고, 추천은 마지막에 확인합니다.</p>
            </div>
          </div>
        </section>
        <section className="workspace-grid">
          <WorkspaceStateCard
            eyebrow="포트폴리오 지연"
            title="계정 자산 워크스페이스를 아직 불러오지 못했습니다"
            message={portfolioLoadError}
            tone="warning"
            className="min-h-[240px]"
            actionLabel="포트폴리오 다시 불러오기"
            onAction={() => {
              setLoading(true);
              setPortfolioLoadError(null);
              void loadPortfolio(true).finally(() => setLoading(false));
            }}
          />
          <div className="workspace-stack">
            <div className="workspace-panel-tight space-y-3">
              <div className="text-sm font-semibold text-text">지금 확인할 것</div>
              <div className="text-sm leading-6 text-text-secondary">
                계정 세션은 살아 있지만 자산 요약이나 보유 종목 응답이 아직 도착하지 않았습니다. 다시 불러오기로 계정 포트폴리오를 새로 요청하고, 실패가 길어지면 네트워크나 백엔드 상태를 먼저 확인합니다.
              </div>
              <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                <span className="info-chip">총자산 → 보유 종목 → 추천 순서 유지</span>
                <span className="info-chip">계정별 데이터 분리</span>
              </div>
            </div>
            {demoPreviewItems.length > 0 ? (
              <div className="workspace-panel-tight space-y-3">
                <div className="text-sm font-semibold text-text">공개 레이더 미리보기</div>
                <div className="space-y-2">
                  {demoPreviewItems.map((item) => (
                    <Link key={`portfolio-recovery-${item.ticker}`} href={`/stock/${encodeURIComponent(item.ticker)}`} className="block rounded-2xl border border-border/70 bg-surface/60 px-3 py-3 transition-colors hover:border-accent/35">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="font-medium text-text">{item.name}</div>
                          <div className="mt-1 text-xs text-text-secondary">{item.ticker} · {item.sector}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-sm text-text">{formatPrice(item.current_price, item.country_code)}</div>
                          <div className={`mt-1 text-xs ${changeColor(item.change_pct ?? 0)}`}>{formatPct(item.change_pct)}</div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <section className="workspace-grid">
        <div className="card !p-5 space-y-5">
          <div className="section-heading">
            <div>
              <h1 className="section-title text-2xl">포트폴리오</h1>
              <p className="section-copy">총자산과 보유 종목을 먼저 정리하고, 추천은 마지막에 확인합니다.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="info-chip">보유 종목 {summary?.holding_count ?? 0}개</span>
              <span className="info-chip">투입 가능 자금 {formatAssetValue(summary?.deployable_cash ?? 0)}</span>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <SummaryMetric label="총자산" value={formatAssetValue(summary?.total_assets ?? 0)} helper="사용자 기준 통화" />
            <SummaryMetric label="총매입금액" value={formatAssetValue(summary?.total_invested ?? 0)} helper={`${summary?.holding_count ?? 0}개 종목`} />
            <SummaryMetric label="주식 평가액" value={formatAssetValue(summary?.total_current ?? 0)} helper={`${(summary?.stock_ratio_pct ?? 0).toFixed(1)}%`} />
            <SummaryMetric label="예수금" value={formatAssetValue(summary?.cash_balance ?? 0)} helper={`${(summary?.cash_ratio_pct ?? 0).toFixed(1)}%`} />
            <SummaryMetric label="투입 가능 자금" value={formatAssetValue(summary?.deployable_cash ?? 0)} helper={`월 추가 자금 ${formatAssetValue(summary?.monthly_budget ?? 0)}`} />
            <SummaryMetric
              label="평가 손익"
              value={`${(summary?.total_pnl ?? 0) >= 0 ? "+" : ""}${formatAssetValue(summary?.total_pnl ?? 0)}`}
              tone={changeColor(summary?.total_pnl ?? 0)}
              helper={`${formatPct(summary?.total_pnl_pct ?? 0)} · 총자산 대비 ${formatPct(summary?.unrealized_pnl_pct_of_assets ?? 0)}`}
            />
          </div>

          <div className="rounded-[22px] border border-border/70 bg-surface/50 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold">자산 구성</div>
                <div className="mt-1 text-xs text-text-secondary">주식, 예수금, 미분류 자산 비중입니다.</div>
              </div>
              <div className="text-xs text-text-secondary">미분류 자산 {formatAssetValue(summary?.other_assets ?? 0)}</div>
            </div>
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-border/40">
              <div className="flex h-full w-full">
                <div className="bg-accent" style={{ width: `${summary?.stock_ratio_pct ?? 0}%` }} />
                <div className="bg-sky-500/80" style={{ width: `${summary?.cash_ratio_pct ?? 0}%` }} />
                <div className="bg-slate-400/80" style={{ width: `${summary?.other_assets_ratio_pct ?? 0}%` }} />
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-secondary">
              <span className="info-chip">주식 {(summary?.stock_ratio_pct ?? 0).toFixed(1)}%</span>
              <span className="info-chip">예수금 {(summary?.cash_ratio_pct ?? 0).toFixed(1)}%</span>
              <span className="info-chip">미분류 {(summary?.other_assets_ratio_pct ?? 0).toFixed(1)}%</span>
            </div>
            <div className="mt-3 space-y-2 text-xs text-text-secondary">
              {summary && summary.asset_gap > 0 ? <div>총자산 기준에서 아직 분류되지 않은 자산이 {formatAssetValue(summary.asset_gap)} 남아 있습니다.</div> : null}
              {summary && summary.asset_gap < 0 ? <div className="text-amber-600">현재 보유 주식 평가액과 예수금 합계가 입력한 총자산보다 큽니다. 총자산 값을 다시 맞춰 주세요.</div> : null}
              {mixedCountries ? <div>여러 시장을 함께 보유 중이면 총자산과 예수금은 사용자가 정한 기준 통화로 직접 관리하는 방식으로 해석합니다.</div> : null}
            </div>
          </div>
        </div>

        <div className="card !p-5 space-y-4 h-fit xl:sticky xl:top-5">
          <div>
            <h2 className="section-title">총자산 설정</h2>
          </div>
          <div className="space-y-3">
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">총자산</label>
              <input value={profileForm.totalAssets} onChange={(e) => setProfileForm((prev) => ({ ...prev, totalAssets: e.target.value }))} type="number" min="0" step="0.01" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">예수금</label>
              <input value={profileForm.cashBalance} onChange={(e) => setProfileForm((prev) => ({ ...prev, cashBalance: e.target.value }))} type="number" min="0" step="0.01" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">월 추가 자금</label>
              <input value={profileForm.monthlyBudget} onChange={(e) => setProfileForm((prev) => ({ ...prev, monthlyBudget: e.target.value }))} type="number" min="0" step="0.01" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
            </div>
          </div>
          {profileError ? <div className="rounded-2xl border border-negative/20 bg-negative/5 px-4 py-3 text-sm text-negative">{profileError}</div> : null}
          <button onClick={saveProfile} disabled={savingProfile} className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60">
            {savingProfile ? "자산 기준 저장 중..." : "자산 기준 저장"}
          </button>
        </div>
      </section>
      <section className="card !p-5 space-y-5">
        <div className="section-heading">
          <div>
            <h2 className="section-title">보유 종목 관리</h2>
          </div>
          {editingHoldingId != null ? <button onClick={resetHoldingForm} className="action-chip-secondary">수정 취소</button> : null}
        </div>

        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-[minmax(0,1.1fr)_180px_140px_180px_auto]">
          <div className="min-w-0">
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">티커</label>
            <input value={holdingForm.ticker} onChange={(e) => setHoldingForm((prev) => ({ ...prev, ticker: e.target.value }))} placeholder={activeGuide.placeholder} className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
          </div>
          <div>
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">매수가</label>
            <input value={holdingForm.buyPrice} onChange={(e) => setHoldingForm((prev) => ({ ...prev, buyPrice: e.target.value }))} type="number" min="0" step="0.01" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
          </div>
          <div>
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">수량</label>
            <input value={holdingForm.quantity} onChange={(e) => setHoldingForm((prev) => ({ ...prev, quantity: e.target.value }))} type="number" min="0" step="0.01" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
          </div>
          <div>
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">매수일</label>
            <input value={holdingForm.buyDate} onChange={(e) => setHoldingForm((prev) => ({ ...prev, buyDate: e.target.value }))} type="date" className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm" />
          </div>
          <div className="flex items-end">
            <button onClick={submitHolding} disabled={submittingHolding} className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60">
              {submittingHolding ? "저장 중..." : editingHoldingId != null ? "보유 종목 수정" : "보유 종목 추가"}
            </button>
          </div>
        </div>

        <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-3 space-y-2">
          <div className="text-xs text-text-secondary">{activeGuide.label}: {activeGuide.helper}</div>
          <TickerResolutionHint resolution={resolution} />
          {formError ? <div className="rounded-2xl border border-negative/20 bg-negative/5 px-4 py-3 text-sm text-negative">{formError}</div> : null}
        </div>
      </section>

      <section className="card !p-0 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <h2 className="section-title">보유 종목</h2>
        </div>
        {hasHoldings ? (
          <div className="overflow-x-auto px-2 pb-2 pt-1 md:px-3">
            <table className="w-full min-w-[1080px] text-sm">
              <thead>
                <tr className="border-b border-border bg-surface/40 text-left text-text-secondary">
                  <th className="px-4 py-3">종목</th>
                  <th className="px-4 py-3">매수 정보</th>
                  <th className="px-4 py-3 text-right">평가 / 비중</th>
                  <th className="px-4 py-3 text-right">손익</th>
                  <th className="px-4 py-3">리스크 / 시그널</th>
                  <th className="px-4 py-3">실행</th>
                  <th className="px-4 py-3 text-right">관리</th>
                </tr>
              </thead>
              <tbody>
                {data?.holdings.map((holding) => (
                  <tr key={holding.id} className="border-b border-border/30 align-top hover:bg-border/10">
                    <td className="px-4 py-3">
                      <Link href={`/stock/${holding.ticker}`} className="hover:text-accent">
                        <div className="font-medium">{holding.name}</div>
                        <div className="mt-1 text-[11px] text-text-secondary">{holding.ticker} · {holding.country_code} · {holding.sector}</div>
                      </Link>
                      {holding.market_regime_label ? <div className="mt-2 text-[11px] text-text-secondary">{holding.market_regime_label}</div> : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-[11px] text-text-secondary">매수일 {holding.buy_date}</div>
                      <div className="mt-2 font-mono text-xs">매수가 {formatPrice(holding.buy_price, holding.country_code)}</div>
                      <div className="mt-1 text-xs text-text-secondary">수량 {formatQuantity(holding.quantity)}주</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-mono font-semibold">{formatPrice(holding.current_price, holding.country_code)}</div>
                      <div className="mt-1 text-[11px] text-text-secondary">평가액 {formatAssetValue(holding.current_value)}</div>
                      <div className="mt-1 text-[11px] text-text-secondary">비중 {holding.weight_pct.toFixed(1)}%</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className={`font-mono font-semibold ${changeColor(holding.pnl)}`}>{holding.pnl >= 0 ? "+" : ""}{formatAssetValue(holding.pnl)}</div>
                      <div className={`mt-1 text-[11px] ${changeColor(holding.pnl_pct)}`}>{formatPct(holding.pnl_pct)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className={`font-semibold ${holding.risk_level === "high" ? "text-red-500" : holding.risk_level === "medium" ? "text-yellow-500" : "text-emerald-500"}`}>{riskLevelLabel(holding.risk_level)}</div>
                      <div className="mt-1 text-[11px] text-text-secondary">리스크 점수 {holding.risk_score.toFixed(1)} · 변동성 {holding.realized_volatility_pct.toFixed(1)}%</div>
                      <div className="mt-1 text-[11px] text-text-secondary">상승 확률 {holding.up_probability != null ? `${holding.up_probability.toFixed(1)}%` : "없음"}</div>
                      <div className={`mt-2 inline-flex rounded-full px-2 py-1 text-[11px] font-medium ${executionBiasTone(holding.execution_bias)}`}>{executionBiasLabel(holding.execution_bias)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold">{tradeActionLabel(holding.trade_action)}</div>
                      <div className="mt-1 text-[11px] text-text-secondary">{holding.trade_setup || "설정된 셋업 없음"}</div>
                      {holding.risk_flags.length > 0 ? <div className="mt-2 max-w-[220px] text-[11px] text-amber-600">{holding.risk_flags[0]}</div> : null}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-3 text-xs">
                        <button onClick={() => startEdit(holding)} className="text-accent hover:underline">수정</button>
                        <button onClick={() => removeHolding(holding.id)} className="text-negative hover:underline">삭제</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-12 text-center text-text-secondary">
            <p className="text-lg">아직 등록된 보유 종목이 없습니다.</p>
            <p className="mt-2 text-sm">총자산과 첫 종목을 입력하면 운영 화면이 채워집니다.</p>
          </div>
        )}
      </section>
      {data && data.allocation.by_sector.length > 0 ? (
        <section className="grid gap-5 xl:grid-cols-2">
          <div className="card !p-5">
            <div className="section-heading">
              <div>
                <h2 className="section-title">섹터 비중</h2>
              </div>
            </div>
            <div className="mt-5 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_sector} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(entry) => entry.name.slice(0, 10)}>
                    {data.allocation.by_sector.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => value.toLocaleString()} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card !p-5">
            <div className="section-heading">
              <div>
                <h2 className="section-title">국가 비중</h2>
              </div>
            </div>
            <div className="mt-5 h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data.allocation.by_country} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={(entry) => entry.name}>
                    {data.allocation.by_country.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(value: number) => value.toLocaleString()} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>
      ) : null}

      {hasHoldings && data ? <PortfolioRiskPanel risk={data.risk} stressTest={data.stress_test} /> : null}
      {hasHoldings && data ? <PortfolioModelPanel model={data.model_portfolio} /> : null}
      {hasHoldings && eventRadar && !eventRadarLoading ? <PortfolioEventRadar data={eventRadar} /> : null}

      <section className="space-y-5">
        <div className="section-heading">
          <div>
            <h2 className="section-title">추천</h2>
            <p className="section-copy">늘릴 종목과 방어 행동을 함께 보고, 검증 기준은 예측 연구실에서 같은 척도로 확인합니다.</p>
          </div>
          <Link href="/lab" className="action-chip-secondary">
            검증 기준 보기
          </Link>
        </div>
        <div className="workspace-grid-balanced">
          <div className="min-w-0">
            <PortfolioConditionalRecommendationPanel
              data={conditionalRecommendation}
              filters={conditionalFilters}
              loading={conditionalLoading}
              running={conditionalRunning}
              onChange={setConditionalFilters}
              onRun={runConditionalRecommendation}
            />
          </div>
          <div className="min-w-0">
            <PortfolioOptimalRecommendationPanel data={optimalRecommendation} loading={optimalLoading} />
          </div>
        </div>
      </section>
    </div>
  );
}

