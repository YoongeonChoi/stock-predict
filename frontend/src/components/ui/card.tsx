import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Card({ children, className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "min-w-0 rounded-[22px] border border-border/70 bg-white p-5 shadow-[0_24px_80px_-54px_rgba(15,23,42,0.42)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
