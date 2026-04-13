export const AUTH_REQUIRED_EVENT = "stockpredict:auth-required";

export interface ApiErrorInfo {
  error_code: string;
  message: string;
  detail?: string;
}

export interface AuthRequiredEventDetail {
  path: string;
  status: number;
  errorCode: string;
  message: string;
  detail: string;
  occurredAt: number;
}

export class ApiError extends Error {
  status: number;
  errorCode: string;
  detail: string;
  retryAfterSeconds: number | null;

  constructor(status: number, info: ApiErrorInfo, headers?: Headers) {
    super(info.message);
    this.status = status;
    this.errorCode = info.error_code || `HTTP-${status}`;
    this.detail = info.detail || "";
    const retryAfterHeader = headers?.get("Retry-After") || headers?.get("retry-after") || "";
    const retryAfterSeconds = Number.parseInt(retryAfterHeader, 10);
    this.retryAfterSeconds = Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0 ? retryAfterSeconds : null;
  }
}

export class ApiTimeoutError extends Error {
  path: string;
  timeoutMs: number;

  constructor(path: string, timeoutMs: number) {
    super(`${Math.round(timeoutMs / 1000)}초 안에 응답이 오지 않았습니다.`);
    this.name = "ApiTimeoutError";
    this.path = path;
    this.timeoutMs = timeoutMs;
  }
}

export function isApiErrorCode(error: unknown, code: string): error is ApiError {
  return error instanceof ApiError && error.errorCode === code;
}

export function getApiRetryAfterSeconds(error: unknown): number | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  if (error.retryAfterSeconds) {
    return error.retryAfterSeconds;
  }
  const match = `${error.detail} ${error.message}`.match(/(\d+)초\s*후/);
  if (!match) {
    return null;
  }
  const seconds = Number.parseInt(match[1] ?? "", 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export function isAuthRequiredError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.errorCode === "SP-6014");
}

export function emitAuthRequired(detail: AuthRequiredEventDetail) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent<AuthRequiredEventDetail>(AUTH_REQUIRED_EVENT, { detail }));
}

