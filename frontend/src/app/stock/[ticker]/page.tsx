import StockPageClient from "@/components/pages/StockPageClient";
import { getPublicStockDetail } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";

export const revalidate = 0;

export default async function StockPage({
  params,
}: {
  params: { ticker: string };
}) {
  const initialTicker = decodeURIComponent(params.ticker);
<<<<<<< HEAD
  const initialData = await timeboxServerPromise(() => getPublicStockDetail(initialTicker), 9000, null);
=======
  const initialData = await timeboxServerPromise(() => getPublicStockDetail(initialTicker), 3200, null);
>>>>>>> main
  return <StockPageClient initialTicker={initialTicker} initialData={initialData} />;
}
