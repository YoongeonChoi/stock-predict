import { apiPath } from "@/lib/api";

type RouteEventName =
  | "initial_ssr_success"
  | "hydration_refetch_success"
  | "hydration_refetch_timeout"
  | "panel_degraded"
  | "session_recovery_attempt"
  | "session_recovery_failed"
  | "blank_screen"
  | "error_only_screen";

interface RouteEventPayload {
  route: string;
  event: RouteEventName;
  status?: "ok" | "warning" | "error";
  panel?: string;
  detail?: string;
  timeoutMs?: number;
}

function buildPayload(payload: RouteEventPayload) {
  return JSON.stringify({
    route: payload.route,
    event: payload.event,
    status: payload.status ?? "ok",
    panel: payload.panel ?? null,
    detail: payload.detail ?? null,
    timeout_ms: payload.timeoutMs ?? null,
    occurred_at: new Date().toISOString(),
  });
}

function fireEvent(payload: RouteEventPayload) {
  if (typeof window === "undefined") {
    return;
  }
  const body = buildPayload(payload);
  const url = apiPath("/api/diagnostics/event");

  try {
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
      return;
    }
  } catch {
    // fall through to fetch
  }

  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => undefined);
}

export function reportInitialSsrSuccess(route: string, detail?: string) {
  fireEvent({ route, event: "initial_ssr_success", detail });
}

export function reportHydrationRefetchSuccess(route: string, panel?: string) {
  fireEvent({ route, event: "hydration_refetch_success", panel });
}

export function reportHydrationRefetchTimeout(route: string, panel?: string, timeoutMs?: number) {
  fireEvent({ route, event: "hydration_refetch_timeout", status: "warning", panel, timeoutMs });
}

export function reportPanelDegraded(route: string, panel: string, detail?: string) {
  fireEvent({ route, event: "panel_degraded", status: "warning", panel, detail });
}

export function reportSessionRecoveryAttempt(route: string) {
  fireEvent({ route, event: "session_recovery_attempt" });
}

export function reportSessionRecoveryFailed(route: string, detail?: string) {
  fireEvent({ route, event: "session_recovery_failed", status: "error", detail });
}

export function reportBlankScreen(route: string, detail?: string) {
  fireEvent({ route, event: "blank_screen", status: "error", detail });
}

export function reportErrorOnlyScreen(route: string, detail?: string) {
  fireEvent({ route, event: "error_only_screen", status: "error", detail });
}
