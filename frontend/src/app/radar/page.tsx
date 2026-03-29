import RadarPageClient from "@/components/pages/RadarPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";

export const revalidate = 0;

export default async function RadarPage() {
  const initialData = await getPublicOpportunities("KR", 12).catch(() => null);
  return <RadarPageClient initialData={initialData} />;
}
