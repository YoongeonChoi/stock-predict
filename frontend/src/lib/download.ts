"use client";

import { ApiError, apiPath, type ApiErrorInfo } from "@/lib/api";

function parseFilename(disposition: string | null, fallbackName: string): string {
  if (!disposition) return fallbackName;

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const basicMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
  if (basicMatch?.[1]) {
    return basicMatch[1];
  }

  return fallbackName;
}

export async function downloadApiFile(path: string, fallbackName: string): Promise<string> {
  const response = await fetch(apiPath(path), { cache: "no-store" });

  if (!response.ok) {
    let info: ApiErrorInfo;
    try {
      info = await response.json();
    } catch {
      info = { error_code: `HTTP-${response.status}`, message: response.statusText };
    }
    throw new ApiError(response.status, info);
  }

  const blob = await response.blob();
  const filename = parseFilename(response.headers.get("content-disposition"), fallbackName);
  const objectUrl = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  return filename;
}
