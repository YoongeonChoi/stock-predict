import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost";
type ButtonSize = "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "border border-accent bg-accent text-white shadow-[0_14px_32px_-22px_rgb(var(--accent-rgb))] hover:bg-[var(--accent-strong)]",
  secondary:
    "border border-border/80 bg-white text-text hover:border-accent/40 hover:text-accent",
  ghost:
    "border border-transparent bg-transparent text-text-secondary hover:bg-surface hover:text-text",
};

const sizeClasses: Record<ButtonSize, string> = {
  md: "min-h-12 px-5 py-3 text-[0.95rem]",
  lg: "min-h-[3.35rem] px-6 py-3.5 text-base",
};

interface BaseButtonProps {
  children: ReactNode;
  className?: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
}

export type ButtonProps = BaseButtonProps & ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({
  children,
  className,
  size = "md",
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex max-w-full items-center justify-center gap-2 rounded-[14px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}

export type ButtonLinkProps = BaseButtonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
    href: string;
  };

export function ButtonLink({
  children,
  className,
  href,
  size = "md",
  variant = "primary",
  ...props
}: ButtonLinkProps) {
  return (
    <Link
      className={cn(
        "inline-flex max-w-full items-center justify-center gap-2 rounded-[14px] font-semibold transition-colors",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      href={href}
      {...props}
    >
      {children}
    </Link>
  );
}
