import ArchivePageClient from "@/components/pages/ArchivePageClient";
import {
  getPublicArchive,
  getPublicPredictionAccuracy,
  getPublicResearchArchive,
  getPublicResearchStatus,
} from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function ArchivePage() {
  const [archives, accuracy, researchReports, researchStatus] = await Promise.all([
    timeboxServerPromise(() => getPublicArchive(), 2500, []),
    timeboxServerPromise(() => getPublicPredictionAccuracy(), 2600, null),
    timeboxServerPromise(() => getPublicResearchArchive("KR", 24), 3000, []),
    timeboxServerPromise(() => getPublicResearchStatus(), 3000, null),
  ]);

  return (
    <ArchivePageClient
      initialArchives={archives}
      initialAccuracy={accuracy}
      initialResearchReports={researchReports}
      initialResearchStatus={researchStatus}
    />
  );
}
