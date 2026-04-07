import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
  variant?: "default" | "compact";
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
  className,
  variant = "default",
}: PageHeaderProps) {
  const compact = variant === "compact";

  return (
    <section
      className={cn(
        "page-header-panel",
        compact && "page-header-panel-compact",
        className,
      )}
    >
      <div className={cn("page-header-layout", compact && "page-header-layout-compact")}>
        <div className="min-w-0">
          {eyebrow ? <div className={cn("page-eyebrow", compact && "page-eyebrow-compact")}>{eyebrow}</div> : null}
          <h1 className={cn("page-title", compact && "page-title-compact")}>{title}</h1>
          <div className={cn("page-description", compact && "page-description-compact")}>{description}</div>
          {meta ? (
            <div className={cn("page-header-meta-row", compact && "page-header-meta-row-compact")}>{meta}</div>
          ) : null}
        </div>
        {actions ? (
          <div
            className={cn(
              "page-header-actions",
              compact && "page-header-actions-compact",
            )}
          >
            {actions}
          </div>
        ) : null}
      </div>
    </section>
  );
}
