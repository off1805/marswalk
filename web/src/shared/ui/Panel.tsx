import type { ReactNode } from "react";

/** Panneau latéral de base, avec un titre. */
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
    >
      <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-[var(--text-muted)]">
        {title}
      </h2>
      {children}
    </section>
  );
}
