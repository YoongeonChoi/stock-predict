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
    <div className={`rounded-lg ${toneClass} p-3 ${className}`.trim()}>
      <div className="text-xs text-text-secondary">{label}</div>
      <div className={`${valueClassName} mt-1`}>{value}</div>
    </div>
  );
}
