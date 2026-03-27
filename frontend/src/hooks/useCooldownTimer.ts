"use client";

import { useEffect, useState } from "react";

function normalizeSeconds(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.ceil(value));
}

export function useCooldownTimer(initialSeconds = 0) {
  const [seconds, setSeconds] = useState(() => normalizeSeconds(initialSeconds));

  useEffect(() => {
    if (seconds <= 0) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setSeconds((value) => Math.max(0, value - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [seconds]);

  return {
    seconds,
    active: seconds > 0,
    start(nextSeconds: number) {
      setSeconds(normalizeSeconds(nextSeconds));
    },
    clear() {
      setSeconds(0);
    },
  };
}
