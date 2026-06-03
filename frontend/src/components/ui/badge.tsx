import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
}

export function Badge({ children, className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex min-h-8 items-center rounded-full border border-accent/15 bg-accent/10 px-3 text-sm font-semibold text-accent",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
