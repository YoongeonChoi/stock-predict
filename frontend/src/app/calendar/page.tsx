import CalendarPageClient from "@/components/pages/CalendarPageClient";
import { getPublicCalendar } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function CalendarPage() {
  const today = new Date();
  const initialData = await timeboxServerPromise(
    () => getPublicCalendar("KR", today.getFullYear(), today.getMonth() + 1),
    3200,
    null,
  );
  return <CalendarPageClient initialData={initialData} />;
}
