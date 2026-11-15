import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";

const styles: Record<Variant, string> = {
  primary: "bg-[var(--accent)] text-[var(--accent-ink)] hover:brightness-110",
  secondary:
    "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)] hover:bg-[var(--surface-3)] hover:border-[var(--border-strong)]",
  danger: "bg-[var(--color-danger)] text-black hover:brightness-110",
};

/** Base button. */
export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-[background-color,border-color,filter] duration-150 disabled:cursor-not-allowed disabled:opacity-45 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
