import type { ReactNode } from "react";

/**
 * Base panel. Panels live inside a console pane (the shell draws the glass), so the
 * panel itself is a quiet section: a tracked-caps title and its content, separated
 * from its neighbours by a hairline.
 */
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      aria-label={title}
      className="border-b border-[var(--border)] px-4 pb-4 pt-3 last:border-b-0"
    >
      <h2 className="label-caps mb-3">{title}</h2>
      {children}
    </section>
  );
}
