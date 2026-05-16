import StockPageClient from "@/components/pages/StockPageClient";
import { getPublicStockDetail } from "@/lib/public-server-api";
import { timeboxServerPromise } from "@/lib/server-timebox";
import type { Metadata } from "next";

export const revalidate = 0;

export async function generateMetadata({ params }: { params: { ticker: string } }): Promise<Metadata> {
  const ticker = decodeURIComponent(params.ticker);
  const data = await timeboxServerPromise(() => getPublicStockDetail(ticker), 1000, null);
  const name = data?.name || ticker;
  return {
    title: `${name} (${ticker}) 주가, 예측 분포, 재무 요약 - Stock Predict`,
    description: `${name} (${ticker})의 가격 흐름, 예측 분포, 기술 신호, 재무 요약을 확인하세요.`,
    openGraph: {
      title: `${name} (${ticker}) 주가와 예측 분포 - Stock Predict`,
      description: `${name} (${ticker})의 가격 흐름과 재무 종합 요약.`,
      type: "website",
    },
    twitter: {
      card: "summary",
      title: `${name} (${ticker}) 분석 리포트`,
      description: `${name} 종목의 예측 분포와 기회 레이더 요약입니다.`,
    },
  };
}

export default async function StockPage({
  params,
}: {
  params: { ticker: string };
}) {
  const initialTicker = decodeURIComponent(params.ticker);
  const initialData = await timeboxServerPromise(() => getPublicStockDetail(initialTicker), 3200, null);
  return <StockPageClient initialTicker={initialTicker} initialData={initialData} />;
}
