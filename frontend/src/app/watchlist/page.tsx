import WatchlistPageClient from "@/components/pages/WatchlistPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";

export default async function WatchlistPage() {
  const demoData = await getPublicOpportunities("KR", 5).catch(() => null);
  return <WatchlistPageClient demoData={demoData} />;
}
