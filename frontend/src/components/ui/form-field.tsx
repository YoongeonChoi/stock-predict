import type { InputHTMLAttributes, LabelHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface FormFieldProps {
  children: ReactNode;
  className?: string;
  error?: string;
  helperText?: string;
  id: string;
  label: string;
}

export function FormField({ children, className, error, helperText, id, label }: FormFieldProps) {
  const describedBy = error ? `${id}-error` : helperText ? `${id}-helper` : undefined;

  return (
    <div className={cn("min-w-0", className)}>
      <label className="ui-field-label" htmlFor={id}>
        {label}
      </label>
      <div data-describedby={describedBy}>{children}</div>
      {error ? (
        <p id={`${id}-error`} className="ui-helper-text text-negative">
          {error}
        </p>
      ) : helperText ? (
        <p id={`${id}-helper`} className="ui-helper-text">
          {helperText}
        </p>
      ) : null}
    </div>
  );
}

type FieldLabelProps = LabelHTMLAttributes<HTMLLabelElement>;

export function FieldLabel({ className, ...props }: FieldLabelProps) {
  return <label className={cn("ui-field-label", className)} {...props} />;
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("ui-input", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("ui-textarea", className)} {...props} />;
}
