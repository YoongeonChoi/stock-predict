import RadarPageClient from "@/components/pages/RadarPageClient";
import { getPublicOpportunities } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function RadarPage() {
  const initialData = await timeboxServerPromise(() => getPublicOpportunities("KR", 12), 4200, null);
  return <RadarPageClient initialData={initialData} />;
}
