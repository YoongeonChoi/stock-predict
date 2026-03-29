import ScreenerPageClient from "@/components/pages/ScreenerPageClient";
import { getPublicScreenerSeed } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function ScreenerPage() {
  const initialSeed = await timeboxServerPromise(() => getPublicScreenerSeed("KR", 10), 4200, null);
  return <ScreenerPageClient initialSeed={initialSeed} />;
}
