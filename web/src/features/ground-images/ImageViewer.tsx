/** Visionneuse d'une image au sol : vignette, sol, instrument, identifiant, lien complet. */
import { thumbSrc, useViewer, type GroundImage } from "./data";
import { Button } from "@/shared/ui";

export function ImageCard({ image, onClose }: { image: GroundImage; onClose?: () => void }) {
  const p = image.props;
  const src = thumbSrc(p);
  return (
    <figure
      aria-label={`Image ${p.image_id}`}
      className="flex w-72 flex-col gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 shadow-lg"
    >
      {src ? (
        <img src={src} alt={`${p.camera ?? p.instrument}, sol ${p.sol}`} className="w-full rounded" loading="lazy" />
      ) : (
        <div className="flex h-32 items-center justify-center rounded bg-[var(--surface-2)] text-sm">
          Vignette indisponible
        </div>
      )}
      <figcaption className="flex flex-col gap-1 text-sm">
        <strong>
          Sol {p.sol} · {p.camera ?? p.instrument}
        </strong>
        <span>Instrument : {p.instrument}</span>
        <span className="break-all">Identifiant : {p.image_id}</span>
        {p.azimuth_deg !== null && p.azimuth_deg !== undefined && (
          <span>Azimut du mât : {Math.round(p.azimuth_deg)}°</span>
        )}
        <span className="text-[var(--text-muted)]">
          Position du rover au sol de prise de vue{p.credit ? ` · ${p.credit}` : ""}
        </span>
        <span className="flex gap-2">
          {p.url && (
            <a href={p.url} target="_blank" rel="noreferrer" className="underline">
              Image complète ↗
            </a>
          )}
          {onClose && (
            <Button className="ml-auto" onClick={onClose} aria-label="Fermer la visionneuse">
              ✕
            </Button>
          )}
        </span>
      </figcaption>
    </figure>
  );
}

export function ImageViewer() {
  const selected = useViewer((s) => s.selected);
  const open = useViewer((s) => s.open);
  if (!selected) return null;
  return (
    <div className="absolute bottom-4 left-4">
      <ImageCard image={selected} onClose={() => open(null)} />
    </div>
  );
}
