import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

import { ApiError, ApiTimeoutError, emitAuthRequired, isAuthRequiredError } from "@/lib/api/errors";
import type { RequestOptions } from "@/lib/api/shared";

const API = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

export function apiPath(path: string): string {
  return API ? `${API}${path}` : path;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const client = getSupabaseBrowserClient();
  if (!client) {
    return {};
  }
  try {
    const {
      data: { session },
    } = await client.auth.getSession();
    if (!session?.access_token) {
      return {};
    }
    return {
      Authorization: `Bearer ${session.access_token}`,
    };
  } catch {
    return {};
  }
}

export async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 0, ...requestInit } = init;
  const authHeaders = await getAuthHeaders();
  const headers = new Headers(requestInit.headers || {});
  Object.entries(authHeaders).forEach(([key, value]) => {
    if (!headers.has(key)) {
      headers.set(key, value);
    }
  });

  const controller = new AbortController();
  if (requestInit.signal) {
    if (requestInit.signal.aborted) {
      controller.abort();
    } else {
      requestInit.signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  let timedOut = false;
  const timeoutHandle = timeoutMs > 0
    ? globalThis.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : null;

  let res: Response;
  try {
    res = await fetch(apiPath(path), {
      ...requestInit,
      headers,
      cache: requestInit.cache ?? "no-store",
      signal: controller.signal,
    });
  } catch (error) {
    if (timeoutHandle != null) {
      globalThis.clearTimeout(timeoutHandle);
    }
    if (timedOut && error instanceof Error && error.name === "AbortError") {
      throw new ApiTimeoutError(path, timeoutMs);
    }
    throw error;
  }
  if (timeoutHandle != null) {
    globalThis.clearTimeout(timeoutHandle);
  }
  if (!res.ok) {
    let info;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    const error = new ApiError(res.status, info, res.headers);
    if (isAuthRequiredError(error)) {
      emitAuthRequired({
        path,
        status: error.status,
        errorCode: error.errorCode,
        message: error.message,
        detail: error.detail,
        occurredAt: Date.now(),
      });
    }
    throw error;
  }
  return res.json();
}

export async function get<T>(path: string, init: RequestOptions = {}): Promise<T> {
  return request<T>(path, init);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}
