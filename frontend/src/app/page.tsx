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

export default async function HomePage() {
  const [
    countries,
    indicators,
    briefing,
    heatmapData,
    movers,
    radarData,
    countryReport,
  ] = await Promise.allSettled([
    getPublicCountries(),
    getPublicMarketIndicators(),
    getPublicDailyBriefing(),
    getPublicHeatmap("KR"),
    getPublicMarketMovers("KR"),
    getPublicOpportunities("KR", 8),
    getPublicCountryReport("KR"),
  ]);

  return (
    <HomeDashboardClient
      initialCountries={countries.status === "fulfilled" ? countries.value : []}
      initialIndicators={indicators.status === "fulfilled" ? indicators.value : []}
      initialBriefing={briefing.status === "fulfilled" ? briefing.value : null}
      initialHeatmap={heatmapData.status === "fulfilled" ? heatmapData.value : null}
      initialMovers={movers.status === "fulfilled" ? movers.value : null}
      initialRadar={radarData.status === "fulfilled" ? radarData.value : null}
      initialCountryReport={countryReport.status === "fulfilled" ? countryReport.value : null}
    />
  );
}
