"use client";

interface Props {
  label: string;
  value: string;
  toneClass?: string;
  valueClassName?: string;
  className?: string;
}

export default function MetricValueCard({
  label,
  value,
  toneClass = "bg-border/30",
  valueClassName = "font-semibold",
  className = "",
}: Props) {
  return (
    <div className={`min-w-0 rounded-lg ${toneClass} p-3 ${className}`.trim()}>
      <div className="text-xs leading-5 text-text-secondary break-words">{label}</div>
      <div className={`${valueClassName} mt-1 leading-tight break-words`}>{value}</div>
    </div>
  );
}
