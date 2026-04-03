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

function toError(error: unknown): Error {
  if (error instanceof Error) return error;
  return new Error(typeof error === "string" ? error : "종목 상세를 불러오지 못했습니다.");
}

interface UseStockDetailFlowOptions {
  initialTicker: string;
  initialData?: StockDetail | null;
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
        console.error(err);
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
      try {
        const next = await api.getStockDetail(normalizedTicker, { timeoutMs: FULL_TIMEOUT_MS, preferFull: true });
        if (cancelled) return;
        setStock((current) => {
          if (!current) return next;
          if (!current.partial && next.partial) return current;
          return next;
        });
        setError(null);
        reportHydrationRefetchSuccess(ROUTE_KEY, "stock_detail_full");
      } catch (err) {
        if (!cancelled) {
          console.error(err);
          if (err instanceof ApiTimeoutError) {
            reportHydrationRefetchTimeout(ROUTE_KEY, "stock_detail_full", FULL_TIMEOUT_MS);
          } else {
            reportPanelDegraded(ROUTE_KEY, "stock_detail_full", toError(err).message);
          }
        }
      }
    };

    const startDetailFlow = async () => {
      if (!initialData) {
        const quick = await loadQuickDetail();
        if (quick?.partial) {
          void upgradeToFullDetail();
        }
        return;
      }

      setLoading(false);
      if (initialData.partial) {
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
        console.error(nextError);
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
        console.error(nextError);
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
        console.error(nextError);
        reportPanelDegraded(ROUTE_KEY, "forecast_delta", toError(nextError).message);
      });

    return () => {
      cancelled = true;
    };
  }, [initialData, normalizedTicker]);

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
