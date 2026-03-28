import ArchivePageClient from "@/components/pages/ArchivePageClient";
import {
  getPublicArchive,
  getPublicPredictionAccuracy,
  getPublicResearchArchive,
  getPublicResearchStatus,
} from "@/lib/public-server-api";

export default async function ArchivePage() {
  const [archives, accuracy, researchReports, researchStatus] = await Promise.allSettled([
    getPublicArchive(),
    getPublicPredictionAccuracy(),
    getPublicResearchArchive("KR", 24),
    getPublicResearchStatus(),
  ]);

  return (
    <ArchivePageClient
      initialArchives={archives.status === "fulfilled" ? archives.value : []}
      initialAccuracy={accuracy.status === "fulfilled" ? accuracy.value : null}
      initialResearchReports={researchReports.status === "fulfilled" ? researchReports.value : []}
      initialResearchStatus={researchStatus.status === "fulfilled" ? researchStatus.value : null}
    />
  );
}
