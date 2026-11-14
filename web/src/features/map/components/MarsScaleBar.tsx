import { metersPerPixel } from "@/shared/geodesy";
import { useSiteManifest } from "@/shared/hooks";

/**
 * Barre d'échelle martienne réutilisable (C1 / F1, règle R3).
 *
 * Calcule l'échelle réelle au niveau du sol martien (rayon 3 396 190 m).
 * N'utilise JAMAIS l'échelle native de MapLibre (qui suppose la Terre et WGS 84).
 */
export function MarsScaleBar({ zoom = 14 }: { zoom?: number }) {
  const { data: manifest } = useSiteManifest();

  // Latitude de référence (centre du site ou équateur par défaut)
  const refLat = manifest
    ? (manifest.bbox[1] + manifest.bbox[3]) / 2.0
    : 18.38;

  const mPerPx = metersPerPixel(zoom, refLat);

  // Largeur cible de la barre d'échelle : ~100px
  const targetDistanceM = mPerPx * 100;

  // Arrondi à des pas lisibles (10, 20, 50, 100, 200, 500, 1000, 2000, 5000...)
  const exponent = Math.floor(Math.log10(targetDistanceM));
  const base = targetDistanceM / Math.pow(10, exponent);

  let niceBase: number;
  if (base >= 5) niceBase = 5;
  else if (base >= 2) niceBase = 2;
  else niceBase = 1;

  const actualDistanceM = niceBase * Math.pow(10, exponent);
  const barWidthPx = Math.max(30, Math.min(200, actualDistanceM / mPerPx));

  const displayDistance = actualDistanceM >= 1000
    ? `${(actualDistanceM / 1000).toFixed(actualDistanceM % 1000 === 0 ? 0 : 1)} km`
    : `${Math.round(actualDistanceM)} m`;

  return (
    <div
      data-testid="mars-scale-bar"
      className="absolute bottom-3 left-3 pointer-events-auto rounded bg-black/75 px-2 py-1 text-white shadow backdrop-blur-sm select-none"
      aria-label={`Échelle martienne : ${displayDistance}`}
    >
      <div className="flex items-center justify-between text-[10px] font-mono leading-none">
        <span>0</span>
        <span className="font-bold">{displayDistance}</span>
      </div>
      <div
        className="mt-0.5 h-1 border-b-2 border-l-2 border-r-2 border-white"
        style={{ width: `${barWidthPx}px` }}
      />
      <div className="mt-0.5 text-[9px] text-gray-300 font-mono tracking-tight text-center">
        Mars 2000
      </div>
    </div>
  );
}
