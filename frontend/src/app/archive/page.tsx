import ArchivePageClient from "@/components/pages/ArchivePageClient";
import {
  getPublicResearchArchive,
  getPublicResearchStatus,
} from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function ArchivePage() {
  const [researchReports, researchStatus] = await Promise.all([
    timeboxServerPromise(() => getPublicResearchArchive(undefined, 40), 3000, []),
    timeboxServerPromise(() => getPublicResearchStatus(), 3000, null),
  ]);

  return (
    <ArchivePageClient
      initialResearchReports={researchReports}
      initialResearchStatus={researchStatus}
    />
  );
}
