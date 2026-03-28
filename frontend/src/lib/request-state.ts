import { ApiError, ApiTimeoutError } from "@/lib/api";

const CONNECTION_MESSAGE =
  "서버 연결이 아직 준비되지 않았습니다. 백엔드가 깨어나는 중이거나 네트워크가 잠시 끊겼을 수 있습니다. 잠시 후 다시 시도해 주세요.";

function normalizeMessage(message: string) {
  return message.trim().replace(/\s+/g, " ");
}

export function isConnectionError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  const message = normalizeMessage(error.message).toLowerCase();
  return (
    message.includes("failed to fetch") ||
    message.includes("network request failed") ||
    message.includes("load failed") ||
    message.includes("networkerror when attempting to fetch resource")
  );
}

export function getConnectionErrorMessage() {
  return CONNECTION_MESSAGE;
}

export function getUserFacingErrorMessage(
  error: unknown,
  fallback: string,
  options: {
    includeCode?: boolean;
    timeoutMessage?: string;
  } = {},
) {
  const { includeCode = false, timeoutMessage = fallback } = options;

  if (error instanceof ApiError) {
    if (error.errorCode === "SP-5018") {
      return timeoutMessage;
    }

    const baseMessage = error.detail || error.message || fallback;
    return includeCode ? `${error.errorCode} · ${baseMessage}` : baseMessage;
  }

  if (error instanceof ApiTimeoutError) {
    return timeoutMessage;
  }

  if (isConnectionError(error)) {
    return CONNECTION_MESSAGE;
  }

  if (error instanceof Error && normalizeMessage(error.message)) {
    return fallback;
  }

  return fallback;
}
