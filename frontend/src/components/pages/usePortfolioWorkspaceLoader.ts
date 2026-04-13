"use client";

import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import { api, type PortfolioConditionalRecommendationFilters, type PortfolioConditionalRecommendationResponse, type PortfolioData, type PortfolioEventRadarResponse, type PortfolioOptimalRecommendationResponse } from "@/lib/api";
import { getUserFacingErrorMessage } from "@/lib/request-state";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";

const ROUTE_KEY = "/portfolio";

interface UsePortfolioWorkspaceLoaderOptions {
  hasSession: boolean;
  authLoading: boolean;
  data: PortfolioData | null;
  loading: boolean;
  portfolioLoadError: string | null;
  conditionalFilters: PortfolioConditionalRecommendationFilters;
  initialFilters: PortfolioConditionalRecommendationFilters;
  primaryTimeoutMs: number;
  panelTimeoutMs: number;
  onPortfolioLoaded: (next: PortfolioData) => void;
  setData: Dispatch<SetStateAction<PortfolioData | null>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setPortfolioLoadError: Dispatch<SetStateAction<string | null>>;
  setEventRadar: Dispatch<SetStateAction<PortfolioEventRadarResponse | null>>;
  setEventRadarError: Dispatch<SetStateAction<string | null>>;
  setConditionalRecommendation: Dispatch<SetStateAction<PortfolioConditionalRecommendationResponse | null>>;
  setConditionalError: Dispatch<SetStateAction<string | null>>;
  setOptimalRecommendation: Dispatch<SetStateAction<PortfolioOptimalRecommendationResponse | null>>;
  setOptimalError: Dispatch<SetStateAction<string | null>>;
  setConditionalLoading: Dispatch<SetStateAction<boolean>>;
  setOptimalLoading: Dispatch<SetStateAction<boolean>>;
  setEventRadarLoading: Dispatch<SetStateAction<boolean>>;
  toast: (message: string, tone?: "info" | "success" | "error") => void;
  formatApiErrorMessage: (error: unknown, fallback: string) => string;
}

export function usePortfolioWorkspaceLoader({
  hasSession,
  authLoading,
  data,
  loading,
  portfolioLoadError,
  conditionalFilters,
  initialFilters,
  primaryTimeoutMs,
  panelTimeoutMs,
  onPortfolioLoaded,
  setData,
  setLoading,
  setPortfolioLoadError,
  setEventRadar,
  setEventRadarError,
  setConditionalRecommendation,
  setConditionalError,
  setOptimalRecommendation,
  setOptimalError,
  setConditionalLoading,
  setOptimalLoading,
  setEventRadarLoading,
  toast,
  formatApiErrorMessage,
}: UsePortfolioWorkspaceLoaderOptions) {
  const loadPortfolio = async (showFailureToast = false) => {
    if (!hasSession) {
      return;
    }
    try {
      const next = await api.getPortfolio({ timeoutMs: primaryTimeoutMs });
      onPortfolioLoaded(next);
      setPortfolioLoadError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "portfolio_workspace");
    } catch (error) {
      console.error(error);
      const message = getUserFacingErrorMessage(error, "포트폴리오를 다시 불러오지 못했습니다.");
      setPortfolioLoadError(message);
      reportPanelDegraded(ROUTE_KEY, "portfolio_workspace", message);
      if (showFailureToast) {
        toast(formatApiErrorMessage(error, "포트폴리오를 다시 불러오지 못했습니다."), "error");
      }
    }
  };

  const refreshSupportPanels = async (filters: PortfolioConditionalRecommendationFilters = conditionalFilters) => {
    if (!hasSession) {
      return;
    }
    setConditionalLoading(true);
    setOptimalLoading(true);
    setEventRadarLoading(true);
    const [eventResult, conditionalResult, optimalResult] = await Promise.allSettled([
      api.getPortfolioEventRadar(14, { timeoutMs: panelTimeoutMs }),
      api.getPortfolioConditionalRecommendation(filters, { timeoutMs: panelTimeoutMs }),
      api.getPortfolioOptimalRecommendation({ timeoutMs: panelTimeoutMs }),
    ]);

    if (eventResult.status === "fulfilled") {
      setEventRadar(eventResult.value);
      setEventRadarError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "event_radar");
    } else {
      console.error(eventResult.reason);
      const message = getUserFacingErrorMessage(eventResult.reason, "이벤트 레이더를 다시 불러오지 못했습니다.");
      setEventRadarError(message);
      reportPanelDegraded(ROUTE_KEY, "event_radar", message);
    }

    if (conditionalResult.status === "fulfilled") {
      setConditionalRecommendation(conditionalResult.value);
      setConditionalError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "conditional_recommendation");
    } else {
      console.error(conditionalResult.reason);
      const message = getUserFacingErrorMessage(conditionalResult.reason, "조건 추천을 다시 불러오지 못했습니다.");
      setConditionalError(message);
      reportPanelDegraded(ROUTE_KEY, "conditional_recommendation", message);
    }

    if (optimalResult.status === "fulfilled") {
      setOptimalRecommendation(optimalResult.value);
      setOptimalError(null);
      reportHydrationRefetchSuccess(ROUTE_KEY, "optimal_recommendation");
    } else {
      console.error(optimalResult.reason);
      const message = getUserFacingErrorMessage(optimalResult.reason, "최적 추천을 다시 불러오지 못했습니다.");
      setOptimalError(message);
      reportPanelDegraded(ROUTE_KEY, "optimal_recommendation", message);
    }

    setConditionalLoading(false);
    setOptimalLoading(false);
    setEventRadarLoading(false);
  };

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!hasSession) {
      reportInitialSsrSuccess(ROUTE_KEY);
      setData(null);
      setEventRadar(null);
      setConditionalRecommendation(null);
      setOptimalRecommendation(null);
      setLoading(false);
      setConditionalLoading(false);
      setOptimalLoading(false);
      setEventRadarLoading(false);
      setPortfolioLoadError(null);
      setEventRadarError(null);
      setConditionalError(null);
      setOptimalError(null);
      return;
    }

    const loadWorkspace = async () => {
      setLoading(true);
      const [portfolioResult, eventResult, conditionalResult, optimalResult] = await Promise.allSettled([
        api.getPortfolio({ timeoutMs: primaryTimeoutMs }),
        api.getPortfolioEventRadar(14, { timeoutMs: panelTimeoutMs }),
        api.getPortfolioConditionalRecommendation(initialFilters, { timeoutMs: panelTimeoutMs }),
        api.getPortfolioOptimalRecommendation({ timeoutMs: panelTimeoutMs }),
      ]);

      if (portfolioResult.status === "fulfilled") {
        onPortfolioLoaded(portfolioResult.value);
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
        setEventRadarError(null);
      } else {
        console.error(eventResult.reason);
        setEventRadarError(
          getUserFacingErrorMessage(eventResult.reason, "포트폴리오 이벤트 레이더를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."),
        );
      }

      if (conditionalResult.status === "fulfilled") {
        setConditionalRecommendation(conditionalResult.value);
        setConditionalError(null);
      } else {
        console.error(conditionalResult.reason);
        setConditionalError(
          getUserFacingErrorMessage(conditionalResult.reason, "조건 추천을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."),
        );
      }

      if (optimalResult.status === "fulfilled") {
        setOptimalRecommendation(optimalResult.value);
        setOptimalError(null);
      } else {
        console.error(optimalResult.reason);
        setOptimalError(
          getUserFacingErrorMessage(optimalResult.reason, "최적 추천을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."),
        );
      }

      setConditionalLoading(false);
      setOptimalLoading(false);
      setEventRadarLoading(false);
      setLoading(false);
    };

    void loadWorkspace();
  }, [
    authLoading,
    hasSession,
    initialFilters,
    onPortfolioLoaded,
    panelTimeoutMs,
    primaryTimeoutMs,
    setConditionalError,
    setConditionalLoading,
    setConditionalRecommendation,
    setData,
    setEventRadar,
    setEventRadarError,
    setEventRadarLoading,
    setLoading,
    setOptimalError,
    setOptimalLoading,
    setOptimalRecommendation,
    setPortfolioLoadError,
  ]);

  useEffect(() => {
    if (!loading && hasSession && data) {
      reportInitialSsrSuccess(ROUTE_KEY);
    }
  }, [data, hasSession, loading]);

  useEffect(() => {
    if (!loading && hasSession && portfolioLoadError && !data) {
      reportErrorOnlyScreen(ROUTE_KEY, portfolioLoadError);
    }
  }, [data, hasSession, loading, portfolioLoadError]);

  return {
    loadPortfolio,
    refreshSupportPanels,
  };
}
