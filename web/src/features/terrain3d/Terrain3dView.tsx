/**
 * Vue 3D complète (F6) — exposée via la route `/3d`.
 *
 * Ce composant est le seul point d'assemblage. Il compose :
 *   - `useTerrain3dData`  → données (manifeste + itinéraire)
 *   - `useFlyover`        → état de l'animation de caméra
 *   - `TerrainCanvas`     → rendu deck.gl
 *   - `FlyoverControls`   → contrôles UI
 *
 * Principe S : ce composant orchestre, il ne calcule rien.
 * Principe D : il dépend des abstractions exposées par ses hooks et composants,
 *              pas de leur implémentation.
 */
import { useCallback, useState } from "react";
import { useTerrain3dData } from "./useTerrain3dData";
import { useFlyover } from "./useFlyover";
import { TerrainCanvas } from "./TerrainCanvas";
import { FlyoverControls } from "./FlyoverControls";

export function Terrain3dView() {
  const { terrainConfig, activeProfile, activeRoute, totalDistanceM, isLoading } =
    useTerrain3dData();

  const flyover = useFlyover(activeProfile, totalDistanceM);

  // Quand l'utilisateur fait glisser manuellement, on suspend l'animation.
  const handleManualDrag = useCallback(
    () => {
      if (flyover.playing) flyover.pause();
    },
    [flyover],
  );

  // État local du message d'info (pas besoin d'aller dans le magasin partagé)
  const [showHelp, setShowHelp] = useState(false);

  if (isLoading) {
    return (
      <div className="relative min-h-0 flex-1 flex items-center justify-center bg-[var(--bg)]">
        <p className="animate-pulse text-sm text-[var(--text-muted)]">
          Loading 3D terrain…
        </p>
      </div>
    );
  }

  if (!terrainConfig) {
    return (
      <div className="relative min-h-0 flex-1 flex items-center justify-center bg-[var(--bg)]">
        <p className="text-sm text-[var(--text-muted)]">
          Site manifest unavailable.
        </p>
      </div>
    );
  }

  return (
    <div
      className="relative min-h-0 flex-1 overflow-hidden"
      style={{ height: "100%" }}
      aria-label="3D terrain view"
    >
      {/* Rendu deck.gl */}
      <TerrainCanvas
        config={terrainConfig}
        camera={flyover.camera}
        exaggeration={flyover.exaggeration}
        activeRoute={activeRoute}
        onViewStateChange={handleManualDrag}
      />

      {/* Contrôles superposés en bas à gauche */}
      <div className="absolute bottom-4 left-4 w-72 space-y-2">
        {!activeRoute && (
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--text-muted)]">
            No active route. Plan and select a variant in the map view to start the flyover.
          </div>
        )}
        <FlyoverControls
          playing={flyover.playing}
          progressM={flyover.progressM}
          totalDistanceM={totalDistanceM}
          exaggeration={flyover.exaggeration}
          speed={flyover.speed}
          onPlay={flyover.play}
          onPause={flyover.pause}
          onRewind={flyover.rewind}
          onExaggerationChange={flyover.setExaggeration}
          onSpeedChange={flyover.setSpeed}
        />
      </div>

      {/* Badge d'aide */}
      <button
        type="button"
        className="absolute right-4 top-4 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
        onClick={() => setShowHelp((h) => !h)}
        aria-label="3D navigation help"
      >
        ?
      </button>
      {showHelp && (
        <div
          className="absolute right-4 top-12 w-56 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-xs"
          role="tooltip"
        >
          <p className="font-semibold mb-1">3D Navigation</p>
          <ul className="space-y-0.5 text-[var(--text-muted)]">
            <li>Click-drag — rotate view</li>
            <li>Ctrl + drag — tilt</li>
            <li>Scroll wheel — zoom</li>
            <li>Right-click + drag — pan</li>
          </ul>
        </div>
      )}
    </div>
  );
}
