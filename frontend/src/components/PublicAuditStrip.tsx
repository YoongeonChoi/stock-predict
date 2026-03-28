import { buildPublicAuditChips, type PublicAuditFields } from "@/lib/public-audit";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<"neutral" | "warning" | "info", string> = {
  neutral: "border-border/70 bg-surface/55 text-text-secondary",
  warning: "border-amber-500/20 bg-amber-500/10 text-amber-600",
  info: "border-accent/15 bg-accent/10 text-accent",
};

export default function PublicAuditStrip({
  meta,
  staleLabel,
  className,
}: {
  meta?: PublicAuditFields | null;
  staleLabel?: string | null;
  className?: string;
}) {
  const chips = buildPublicAuditChips(meta, { staleLabel });
  if (chips.length === 0) {
    return null;
  }
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      {chips.map((chip) => (
        <span
          key={`${chip.tone}-${chip.label}`}
          className={cn("inline-flex items-center rounded-full border px-3 py-1.5 text-[11px] font-medium", TONE_CLASS[chip.tone])}
        >
          {chip.label}
        </span>
      ))}
    </div>
  );
}
