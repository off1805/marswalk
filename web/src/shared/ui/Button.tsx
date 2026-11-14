import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";

const styles: Record<Variant, string> = {
  primary: "bg-[var(--color-info)] text-white",
  secondary: "bg-[var(--surface-2)] text-[var(--text)] border border-[var(--border)]",
  danger: "bg-[var(--color-danger)] text-white",
};

/** Bouton de base. */
export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`rounded-md px-3 py-2 font-semibold disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
