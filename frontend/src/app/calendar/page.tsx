import CalendarPageClient from "@/components/pages/CalendarPageClient";
import { getPublicCalendar } from "@/lib/public-server-api";

export const revalidate = 0;

export default async function CalendarPage() {
  const today = new Date();
  const initialData = await getPublicCalendar("KR", today.getFullYear(), today.getMonth() + 1).catch(() => null);
  return <CalendarPageClient initialData={initialData} />;
}
