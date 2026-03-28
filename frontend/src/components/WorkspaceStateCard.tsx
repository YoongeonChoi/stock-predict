import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "warning" | "danger";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "border-border/70 bg-surface/45",
  warning: "border-amber-500/20 bg-amber-500/6",
  danger: "border-negative/20 bg-negative/6",
};

interface WorkspaceStateCardProps {
  eyebrow?: string;
  title: string;
  message: string;
  tone?: Tone;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  actionClassName?: string;
  aside?: ReactNode;
}

export default function WorkspaceStateCard({
  eyebrow = "상태 안내",
  title,
  message,
  tone = "neutral",
  actionLabel = "다시 시도",
  onAction,
  className,
  actionClassName,
  aside,
}: WorkspaceStateCardProps) {
  return (
    <div className={cn("rounded-[22px] border px-4 py-4", TONE_CLASS[tone], className)}>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">{eyebrow}</div>
          <div className="mt-2 text-sm font-semibold text-text">{title}</div>
          <div className="mt-1 text-sm leading-6 text-text-secondary">{message}</div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {aside}
          {onAction ? (
            <button
              onClick={onAction}
              className={cn(
                "inline-flex rounded-full border border-accent/25 px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:border-accent/45 hover:bg-accent/10",
                actionClassName,
              )}
            >
              {actionLabel}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

interface WorkspaceLoadingCardProps {
  eyebrow?: string;
  title: string;
  message: string;
  lines?: number;
  className?: string;
}

export function WorkspaceLoadingCard({
  eyebrow = "불러오는 중",
  title,
  message,
  lines = 3,
  className,
}: WorkspaceLoadingCardProps) {
  return (
    <div className={cn("rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4", className)}>
      <div className="flex h-full flex-col justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">{eyebrow}</div>
          <div className="mt-2 text-sm font-semibold text-text">{title}</div>
          <div className="mt-1 text-sm leading-6 text-text-secondary">{message}</div>
        </div>
        <div className="space-y-2">
          {Array.from({ length: lines }, (_, index) => (
            <div
              key={`${title}-${index}`}
              className="h-3 animate-pulse rounded-full bg-border/35"
              style={{ width: `${92 - index * 14}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
