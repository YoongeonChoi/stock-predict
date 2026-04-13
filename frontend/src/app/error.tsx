"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-text">
          페이지를 불러오는 중 문제가 발생했습니다
        </h2>
        <p className="text-sm text-text-secondary">
          일시적인 오류일 수 있습니다. 잠시 뒤 다시 시도해 주세요.
        </p>
      </div>
      <button
        onClick={reset}
        className="rounded-xl bg-accent px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
      >
        다시 시도
      </button>
    </div>
  );
}
