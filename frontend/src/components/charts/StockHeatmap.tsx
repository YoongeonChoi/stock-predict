"use client";

import { useRouter } from "next/navigation";
import { Treemap, ResponsiveContainer } from "recharts";

import WorkspaceStateCard, { WorkspaceLoadingCard } from "@/components/WorkspaceStateCard";
import type { HeatmapData } from "@/lib/api";

function changeToColor(change: number, neutralPalette = false): string {
  if (neutralPalette) return "#cbd5e1";
  if (change >= 3) return "#15803d";
  if (change >= 2) return "#16a34a";
  if (change >= 1) return "#22c55e";
  if (change >= 0.5) return "#4ade80";
  if (change >= 0) return "#86efac";
  if (change >= -0.5) return "#fca5a5";
  if (change >= -1) return "#f87171";
  if (change >= -2) return "#ef4444";
  if (change >= -3) return "#dc2626";
  return "#b91c1c";
}

interface CustomContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  change?: number;
  ticker?: string;
  depth?: number;
  index?: number;
  neutralPalette?: boolean;
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name, change = 0, ticker, depth, neutralPalette = false } = props;

  if (depth !== 1 || width < 4 || height < 4) return null;

  const bg = changeToColor(change, neutralPalette);
  const showTicker = width > 40 && height > 24;
  const showChange = !neutralPalette && width > 50 && height > 36;
  const fontSize = Math.max(8, Math.min(12, width / 7));

  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={bg} stroke="var(--bg)" strokeWidth={1.5} rx={2} />
      {showTicker && (
        <text
          x={x + width / 2} y={y + height / 2 - (showChange ? 5 : 0)}
          textAnchor="middle" dominantBaseline="central"
          fill="white" fontSize={fontSize} fontWeight="bold"
          style={{ textShadow: "0 1px 2px rgba(0,0,0,0.5)", pointerEvents: "none" }}
        >
          {name}
        </text>
      )}
      {showChange && (
        <text
          x={x + width / 2} y={y + height / 2 + fontSize}
          textAnchor="middle" dominantBaseline="central"
          fill="rgba(255,255,255,0.85)" fontSize={Math.max(7, fontSize - 2)}
          style={{ pointerEvents: "none" }}
        >
          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </text>
      )}
    </g>
  );
}

interface Props {
  data: HeatmapData | null;
  loading?: boolean;
}

export default function StockHeatmap({ data, loading }: Props) {
  const router = useRouter();

  if (loading) {
    return (
      <WorkspaceLoadingCard
        title="시장 히트맵을 정리하고 있습니다"
        message="시가총액 가중 분포와 종목별 등락률을 먼저 묶은 뒤 보드에 배치합니다."
        className="min-h-[260px]"
      />
    );
  }

  if (!data || !data.children?.length) {
    return (
      <WorkspaceStateCard
        eyebrow="히트맵 대기"
        title="표시할 시장 분포가 아직 없습니다"
        message="대표 종목의 시가총액과 등락률이 정리되면 히트맵이 이 영역에 바로 채워집니다."
        className="min-h-[220px]"
      />
    );
  }

  const flat = data.children.flatMap((sector) =>
    sector.children.map((stock) => ({
      ...stock,
      sector: sector.name,
    }))
  );
  const neutralFallback =
    Boolean(data.partial || data.fallback_reason)
    && flat.length > 0
    && flat.every((stock) => Math.abs(stock.change ?? 0) < 0.0001);

  const handleClick = (node: any) => {
    if (node?.ticker) {
      router.push(`/stock/${encodeURIComponent(node.ticker)}`);
    }
  };

  return (
    <div className="space-y-3">
      {neutralFallback ? (
        <div className="rounded-2xl border border-border/70 bg-surface/50 px-4 py-3 text-sm text-text-secondary">
          실시간 등락률 분포가 아직 도착하지 않아 시가총액 배치만 먼저 보여주고 있습니다.
        </div>
      ) : null}
      <div className="h-[420px] w-full cursor-pointer">
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={flat}
            dataKey="size"
            aspectRatio={4 / 3}
            content={<CustomContent neutralPalette={neutralFallback} />}
            onClick={handleClick}
          />
        </ResponsiveContainer>
      </div>
    </div>
  );
}
