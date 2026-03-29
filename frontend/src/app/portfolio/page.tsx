import PortfolioPageClient from "@/components/pages/PortfolioPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";

export const revalidate = 0;

export default async function PortfolioPage() {
  const demoData = await getPublicOpportunities("KR", 6).catch(() => null);
  return <PortfolioPageClient demoData={demoData} />;
}
