import "server-only";

export async function timeboxServerPromise<T>(
  loader: () => Promise<T>,
  timeoutMs: number,
  fallback: T,
): Promise<T> {
  let timeoutId: NodeJS.Timeout | null = null;
  const guarded = loader().catch(() => fallback);
  const timeout = new Promise<T>((resolve) => {
    timeoutId = setTimeout(() => resolve(fallback), timeoutMs);
  });

  try {
    return await Promise.race([guarded, timeout]);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}
