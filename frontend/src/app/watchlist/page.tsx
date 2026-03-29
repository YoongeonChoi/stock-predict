import WatchlistPageClient from "@/components/pages/WatchlistPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function WatchlistPage() {
  const demoData = await timeboxServerPromise(() => getPublicOpportunities("KR", 5), 3200, null);
  return <WatchlistPageClient demoData={demoData} />;
}
