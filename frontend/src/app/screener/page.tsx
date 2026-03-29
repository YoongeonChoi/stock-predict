import ScreenerPageClient from "@/components/pages/ScreenerPageClient";
import { getPublicScreenerSeed } from "@/lib/public-server-api";

export const revalidate = 0;

export default async function ScreenerPage() {
  const initialSeed = await getPublicScreenerSeed("KR", 10).catch(() => null);
  return <ScreenerPageClient initialSeed={initialSeed} />;
}
