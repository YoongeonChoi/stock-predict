import WatchlistTrackingPageClient from "@/components/pages/WatchlistTrackingPageClient";
import { getPublicStockDetail } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function WatchlistTrackingPage({
  params,
}: {
  params: { ticker: string };
}) {
  const initialTicker = decodeURIComponent(params.ticker);
  const initialData = await timeboxServerPromise(() => getPublicStockDetail(initialTicker), 6500, null);
  return <WatchlistTrackingPageClient initialTicker={initialTicker} initialData={initialData} />;
}
