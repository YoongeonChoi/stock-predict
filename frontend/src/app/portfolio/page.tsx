import PortfolioPageClient from "@/components/pages/PortfolioPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function PortfolioPage() {
  const demoData = await timeboxServerPromise(() => getPublicOpportunities("KR", 6), 3200, null);
  return <PortfolioPageClient demoData={demoData} />;
}
