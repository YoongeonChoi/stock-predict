"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { api, ApiTimeoutError } from "@/lib/api";
import type { CompositeScore, ForecastDeltaResponse, PivotPoints, TechSummary } from "@/lib/api";
import {
  reportErrorOnlyScreen,
  reportHydrationRefetchSuccess,
  reportHydrationRefetchTimeout,
  reportInitialSsrSuccess,
  reportPanelDegraded,
} from "@/lib/route-observability";
import type { PricePoint, StockDetail } from "@/lib/types";

const ROUTE_KEY = "/stock/[ticker]";
const QUICK_TIMEOUT_MS = 12_000;
const FULL_TIMEOUT_MS = 14_000;
export const STOCK_DETAIL_AUTO_RETRY_DELAYS_MS = [8_000, 30_000] as const;
const STOCK_DETAIL_SHELL_FALLBACK_REASONS = new Set(["stock_memory_guard", "stock_minimal_shell"]);

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "종목 상세를 불러오지 못했습니다.");
}

interface UseStockDetailFlowOptions {
  initialTicker: string;
  initialData?: StockDetail | null;
}

export function shouldUpgradeStockDetail(snapshot: StockDetail | null | undefined) {
  return Boolean(snapshot?.partial || snapshot?.weekly_trade_plan?.partial);
}

export function isStockDetailShellSnapshot(snapshot: StockDetail | null | undefined) {
  const fallbackReason = snapshot?.fallback_reason ?? null;
  const weeklyFallbackReason = snapshot?.weekly_trade_plan?.fallback_reason ?? null;
  return (
    STOCK_DETAIL_SHELL_FALLBACK_REASONS.has(fallbackReason ?? "")
    || STOCK_DETAIL_SHELL_FALLBACK_REASONS.has(weeklyFallbackReason ?? "")
  );
}

export function shouldAutoRetryStockDetail(
  snapshot: StockDetail | null | undefined,
  retryAttempt: number,
  retryLimit = STOCK_DETAIL_AUTO_RETRY_DELAYS_MS.length,
) {
  return Boolean(snapshot && retryAttempt < retryLimit && isStockDetailShellSnapshot(snapshot));
}

function hasWeeklyTradeNumbers(snapshot: StockDetail | null | undefined) {
  const plan = snapshot?.weekly_trade_plan;
  return Boolean(plan && (plan.buy_price != null || plan.sell_price != null || plan.stop_loss != null));
}

export function chooseUsefulStockDetailSnapshot(current: StockDetail | null, next: StockDetail) {
  if (!current) return next;
  if (isStockDetailShellSnapshot(next) && !isStockDetailShellSnapshot(current)) return current;
  if (hasWeeklyTradeNumbers(current) && !hasWeeklyTradeNumbers(next)) return current;
  if (!current.partial && next.partial) return current;
  return next;
}

export function useStockDetailFlow({
  initialTicker,
  initialData = null,
}: UseStockDetailFlowOptions) {
  const normalizedTicker = useMemo(() => decodeURIComponent(initialTicker), [initialTicker]);
  const initialReportedRef = useRef(false);
  const errorOnlyReportedRef = useRef(false);
  const [stock, setStock] = useState<StockDetail | null>(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<Error | null>(null);
  const [techSummary, setTechSummary] = useState<TechSummary | null>(null);
  const [pivotPoints, setPivotPoints] = useState<PivotPoints | null>(null);
  const [forecastDelta, setForecastDelta] = useState<ForecastDeltaResponse | null>(null);
  const [chartPeriod, setChartPeriod] = useState("3mo");
  const [chartData, setChartData] = useState<PricePoint[]>([]);
  const [fullUpgradePending, setFullUpgradePending] = useState(false);
  const [autoRetryAttempt, setAutoRetryAttempt] = useState(0);

  useEffect(() => {
    if (!normalizedTicker) return;
    let cancelled = false;
    initialReportedRef.current = false;
    errorOnlyReportedRef.current = false;
    setStock(initialData);
    setError(null);
    setTechSummary(null);
    setPivotPoints(null);
    setForecastDelta(null);
    setChartData([]);
    setChartPeriod("3mo");
    setLoading(!initialData);
    setFullUpgradePending(false);
    setAutoRetryAttempt(0);

    const loadQuickDetail = async (): Promise<StockDetail | null> => {
      try {
        const next = await api.getStockDetail(normalizedTicker, { timeoutMs: QUICK_TIMEOUT_MS, preferFull: false });
        if (cancelled) return null;
        setStock(next);
        setError(null);
        reportHydrationRefetchSuccess(ROUTE_KEY, "stock_detail_quick");
        return next;
      } catch (err) {
        if (cancelled) return null;
        console.warn(err);
        if (err instanceof ApiTimeoutError) {
          reportHydrationRefetchTimeout(ROUTE_KEY, "stock_detail_quick", QUICK_TIMEOUT_MS);
        } else {
          reportPanelDegraded(ROUTE_KEY, "stock_detail_quick", toError(err).message);
        }
        if (!initialData) {
          setError(toError(err));
        }
        return null;
      } finally {
        if (!cancelled && !initialData) {
          setLoading(false);
        }
      }
    };

    const upgradeToFullDetail = async () => {
      setFullUpgradePending(true);
      try {
        const next = await api.getStockDetail(normalizedTicker, { timeoutMs: FULL_TIMEOUT_MS, preferFull: true });
        if (cancelled) return;
        setStock((current) => chooseUsefulStockDetailSnapshot(current, next));
        setError(null);
        reportHydrationRefetchSuccess(ROUTE_KEY, "stock_detail_full");
      } catch (err) {
        if (!cancelled) {
          console.warn(err);
          if (err instanceof ApiTimeoutError) {
            reportHydrationRefetchTimeout(ROUTE_KEY, "stock_detail_full", FULL_TIMEOUT_MS);
          } else {
            reportPanelDegraded(ROUTE_KEY, "stock_detail_full", toError(err).message);
          }
        }
      } finally {
        if (!cancelled) {
          setFullUpgradePending(false);
        }
      }
    };

    const startDetailFlow = async () => {
      if (!initialData) {
        const quick = await loadQuickDetail();
        if (shouldUpgradeStockDetail(quick)) {
          void upgradeToFullDetail();
        }
        return;
      }

      setLoading(false);
      if (shouldUpgradeStockDetail(initialData)) {
        void upgradeToFullDetail();
      }
    };

    void startDetailFlow();

    api.getTechSummary(normalizedTicker)
      .then((next) => {
        if (!cancelled) {
          setTechSummary(next);
          reportHydrationRefetchSuccess(ROUTE_KEY, "technical_summary");
        }
      })
      .catch((nextError) => {
        console.warn(nextError);
        reportPanelDegraded(ROUTE_KEY, "technical_summary", toError(nextError).message);
      });

    api.getPivotPoints(normalizedTicker)
      .then((next) => {
        if (!cancelled) {
          setPivotPoints(next);
          reportHydrationRefetchSuccess(ROUTE_KEY, "pivot_points");
        }
      })
      .catch((nextError) => {
        console.warn(nextError);
        reportPanelDegraded(ROUTE_KEY, "pivot_points", toError(nextError).message);
      });

    api.getStockForecastDelta(normalizedTicker)
      .then((next) => {
        if (!cancelled) {
          setForecastDelta(next);
          reportHydrationRefetchSuccess(ROUTE_KEY, "forecast_delta");
        }
      })
      .catch((nextError) => {
        console.warn(nextError);
        reportPanelDegraded(ROUTE_KEY, "forecast_delta", toError(nextError).message);
      });

    return () => {
      cancelled = true;
    };
  }, [initialData, normalizedTicker]);

  useEffect(() => {
    if (!normalizedTicker || loading || fullUpgradePending) return;
    if (!shouldAutoRetryStockDetail(stock, autoRetryAttempt)) return;

    const delayMs = STOCK_DETAIL_AUTO_RETRY_DELAYS_MS[autoRetryAttempt];
    let cancelled = false;
    const retryHandle = window.setTimeout(() => {
      setAutoRetryAttempt((attempt) => attempt + 1);
      api.getStockDetail(normalizedTicker, { timeoutMs: FULL_TIMEOUT_MS, preferFull: true })
        .then((next) => {
          if (cancelled) return;
          setStock((current) => chooseUsefulStockDetailSnapshot(current, next));
          setError(null);
          reportHydrationRefetchSuccess(ROUTE_KEY, "stock_detail_shell_retry");
        })
        .catch((err) => {
          if (cancelled) return;
          console.warn(err);
          if (err instanceof ApiTimeoutError) {
            reportHydrationRefetchTimeout(ROUTE_KEY, "stock_detail_shell_retry", FULL_TIMEOUT_MS);
          } else {
            reportPanelDegraded(ROUTE_KEY, "stock_detail_shell_retry", toError(err).message);
          }
        });
    }, delayMs);

    return () => {
      cancelled = true;
      window.clearTimeout(retryHandle);
    };
  }, [autoRetryAttempt, fullUpgradePending, loading, normalizedTicker, stock]);

  useEffect(() => {
    if (!initialReportedRef.current && (initialData || stock)) {
      reportInitialSsrSuccess(ROUTE_KEY);
      initialReportedRef.current = true;
    }
  }, [initialData, stock]);

  useEffect(() => {
    if (!errorOnlyReportedRef.current && !loading && !stock && error) {
      reportErrorOnlyScreen(ROUTE_KEY, error.message);
      errorOnlyReportedRef.current = true;
    }
  }, [error, loading, stock]);

  const changeChartPeriod = async (period: string) => {
    if (!normalizedTicker) return;
    setChartPeriod(period);
    try {
      const response = await api.getStockChart(normalizedTicker, period);
      setChartData(response.data);
    } catch {
      setChartData([]);
    }
  };

  const composite = (stock as (StockDetail & { composite_score?: CompositeScore }) | null)?.composite_score ?? null;

  return {
    normalizedTicker,
    stock,
    loading,
    error,
    techSummary,
    pivotPoints,
    forecastDelta,
    chartPeriod,
    chartData,
    changeChartPeriod,
    composite,
  };
}
