import HomeDashboardClient from "@/components/pages/HomeDashboardClient";
import {
  getPublicCountries,
  getPublicCountryReport,
  getPublicDailyBriefing,
  getPublicHeatmap,
  getPublicMarketIndicators,
  getPublicMarketMovers,
  getPublicOpportunities,
} from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function HomePage() {
  const [
    countries,
    indicators,
    briefing,
    heatmapData,
    movers,
    radarData,
    countryReport,
  ] = await Promise.all([
    timeboxServerPromise(() => getPublicCountries(), 2500, []),
    timeboxServerPromise(() => getPublicMarketIndicators(), 2800, []),
    timeboxServerPromise(() => getPublicDailyBriefing(), 3200, null),
    timeboxServerPromise(() => getPublicHeatmap("KR"), 2600, null),
    timeboxServerPromise(() => getPublicMarketMovers("KR"), 2600, null),
    timeboxServerPromise(() => getPublicOpportunities("KR", 12), 4200, null),
    timeboxServerPromise(() => getPublicCountryReport("KR"), 3200, null),
  ]);

  return (
    <HomeDashboardClient
      initialCountries={countries}
      initialIndicators={indicators}
      initialBriefing={briefing}
      initialHeatmap={heatmapData}
      initialMovers={movers}
      initialRadar={radarData}
      initialCountryReport={countryReport}
    />
  );
}
