/** Panneau d'export : GeoJSON et fiche imprimable du plan, carnet de la sortie (X1). */
import { Link } from "react-router";
import { downloadJson, KIND_LABELS, logbookToGeojson } from "./format";
import { planGeojsonUrl, useLogbook } from "./queries";
import { Button, Panel } from "@/shared/ui";
import { useShared } from "@/shared/store";

const linkClass =
  "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 font-semibold text-[var(--text)]";

export function ExportPanel() {
  const planId = useShared((s) => s.activePlanId);
  const evaId = useShared((s) => s.evaId);
  const book = useLogbook(evaId, 5000);
  const last = book.data?.entries.slice(-4).reverse() ?? [];
  return (
    <Panel title="Export & Logbook">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">Plan</h3>
          {planId ? (
            <div className="flex flex-wrap gap-2">
              <a className={linkClass} href={planGeojsonUrl(planId)} download={`marswalk-${planId}.geojson`}>
                ⤓ Plan GeoJSON
              </a>
              <Link className={linkClass} to={`/export/plan/${encodeURIComponent(planId)}`}>
                🖶 Printable sheet (PDF)
              </Link>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Select a plan to export it.</p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">EVA logbook</h3>
          {!evaId && (
            <p className="text-sm text-[var(--text-muted)]">The logbook opens when an EVA is started.</p>
          )}
          {evaId && book.isError && <p className="text-sm">Logbook unavailable.</p>}
          {evaId && book.data && (
            <>
              <ul aria-label="Recent logbook entries" className="flex flex-col gap-1 text-sm">
                {last.map((e, i) => (
                  <li key={`${e.utc}-${i}`}>
                    <span className="text-[var(--text-muted)]">
                      Sol {e.sol} · {e.lmst}
                    </span>{" "}
                    <strong>{KIND_LABELS[e.kind]}</strong> {e.text}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap gap-2">
                <Link className={linkClass} to={`/export/logbook/${encodeURIComponent(evaId)}`}>
                  🖶 Full logbook
                </Link>
                <Button onClick={() => downloadJson(`marswalk-${evaId}-logbook.geojson`, logbookToGeojson(book.data))}>
                  ⤓ Logbook GeoJSON
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}
