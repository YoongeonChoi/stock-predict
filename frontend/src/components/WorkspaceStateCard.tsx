import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "warning" | "danger";
type Kind = "inline" | "partial" | "blocking" | "empty";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "state-card-tone-neutral",
  warning: "state-card-tone-warning",
  danger: "state-card-tone-danger",
};

const KIND_CLASS: Record<Kind, string> = {
  inline: "state-card-inline",
  partial: "state-card-partial",
  blocking: "state-card-blocking",
  empty: "state-card-empty",
};

interface WorkspaceStateCardProps {
  eyebrow?: string;
  title: string;
  message: string;
  tone?: Tone;
  kind?: Kind;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
  actionClassName?: string;
  aside?: ReactNode;
  details?: ReactNode;
}

export default function WorkspaceStateCard({
  eyebrow = "상태 안내",
  title,
  message,
  tone = "neutral",
  kind = "inline",
  actionLabel = "다시 시도",
  onAction,
  className,
  actionClassName,
  aside,
  details,
}: WorkspaceStateCardProps) {
  return (
    <div className={cn("state-card", TONE_CLASS[tone], KIND_CLASS[kind], className)}>
      <div className="state-card-shell">
        <div className="min-w-0">
          <div className="state-card-eyebrow">{eyebrow}</div>
          <div className="state-card-title">{title}</div>
          <div className="state-card-message">{message}</div>
          {details ? <div className="state-card-details">{details}</div> : null}
        </div>
        <div className="state-card-actions">
          {aside}
          {onAction ? (
            <button onClick={onAction} className={cn("state-card-action", actionClassName)}>
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
    <div className={cn("state-card state-card-loading state-card-inline state-card-tone-neutral", className)}>
      <div className="flex h-full flex-col justify-between gap-4">
        <div className="min-w-0">
          <div className="state-card-eyebrow">{eyebrow}</div>
          <div className="state-card-title">{title}</div>
          <div className="state-card-message">{message}</div>
        </div>
        <div className="space-y-2">
          {Array.from({ length: lines }, (_, index) => (
            <div
              key={`${title}-${index}`}
              className="h-3 animate-pulse rounded-full bg-border/25"
              style={{ width: `${92 - index * 14}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
