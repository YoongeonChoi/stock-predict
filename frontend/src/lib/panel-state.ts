export type PanelStatus = "idle" | "loading" | "ready" | "degraded";

export interface PanelState<T> {
  status: PanelStatus;
  data: T | null;
  error: string | null;
  updatedAt?: string | null;
}

export function idlePanel<T>(data: T | null = null): PanelState<T> {
  return { status: "idle", data, error: null, updatedAt: null };
}

export function loadingPanel<T>(data: T | null = null): PanelState<T> {
  return { status: "loading", data, error: null, updatedAt: null };
}

export function readyPanel<T>(data: T, updatedAt?: string | null): PanelState<T> {
  return { status: "ready", data, error: null, updatedAt: updatedAt ?? null };
}

export function degradedPanel<T>(error: string, data: T | null = null, updatedAt?: string | null): PanelState<T> {
  return { status: "degraded", data, error, updatedAt: updatedAt ?? null };
}

