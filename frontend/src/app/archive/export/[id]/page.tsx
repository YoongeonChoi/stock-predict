import ArchiveExportPageClient from "@/components/pages/ArchiveExportPageClient";

export const revalidate = 0;
export const dynamic = "force-dynamic";

export default function ArchiveExportPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const initialReportId = Number(params.id);
  const initialFormat = Array.isArray(searchParams?.format)
    ? searchParams?.format[0]
    : searchParams?.format;

  return (
    <ArchiveExportPageClient
      initialReportId={initialReportId}
      initialFormat={initialFormat}
    />
  );
}
