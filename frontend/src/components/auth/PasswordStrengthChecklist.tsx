"use client";

import { cn } from "@/lib/utils";
import type { PasswordStrengthResult } from "@/lib/account";

function PasswordRule({
  active,
  label,
}: {
  active: boolean;
  label: string;
}) {
  return (
    <li className={cn("flex items-center gap-2 text-xs", active ? "text-positive" : "text-text-secondary")}>
      <span
        className={cn(
          "inline-flex h-5 w-5 items-center justify-center rounded-sm text-[10px] font-semibold",
          active ? "bg-positive/12 text-positive" : "bg-text/6 text-text-secondary",
        )}
      >
        {active ? "완료" : "대기"}
      </span>
      <span>{label}</span>
    </li>
  );
}

export default function PasswordStrengthChecklist({
  result,
}: {
  result: PasswordStrengthResult;
}) {
  const barWidths = ["w-1/5", "w-2/5", "w-3/5", "w-4/5", "w-full"];
  const tones = [
    "bg-negative",
    "bg-orange-500",
    "bg-amber-500",
    "bg-sky-500",
    "bg-positive",
  ];
  const meterIndex = Math.max(0, Math.min(result.score, 4));

  return (
    <div className="section-slab-subtle !p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-text">비밀번호 보안 강도</div>
          <div className="mt-1 text-xs text-text-secondary">대문자, 소문자, 숫자, 특수문자, 10자 이상을 모두 만족해야 가입할 수 있습니다.</div>
        </div>
        <span className="status-token">
          {result.label}
        </span>
      </div>
      <div className="mt-4 h-2 rounded-sm bg-border/40">
        <div className={cn("h-full rounded-sm transition-all", barWidths[meterIndex], tones[meterIndex])} />
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        <PasswordRule active={result.checks.minLength} label="10자 이상" />
        <PasswordRule active={result.checks.uppercase} label="영문 대문자 포함" />
        <PasswordRule active={result.checks.lowercase} label="영문 소문자 포함" />
        <PasswordRule active={result.checks.number} label="숫자 포함" />
        <PasswordRule active={result.checks.symbol} label="특수문자 포함" />
        <PasswordRule active={result.checks.match} label="비밀번호 재확인 일치" />
      </ul>
    </div>
  );
}
