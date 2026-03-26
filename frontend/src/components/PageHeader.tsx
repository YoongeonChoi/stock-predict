import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <section className={cn("page-header-panel", className)}>
      <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          {eyebrow ? <div className="page-eyebrow">{eyebrow}</div> : null}
          <h1 className="page-title">{title}</h1>
          <p className="page-description">{description}</p>
          {meta ? <div className="mt-4 flex flex-wrap gap-2">{meta}</div> : null}
        </div>
        {actions ? <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap">{actions}</div> : null}
      </div>
    </section>
  );
}
