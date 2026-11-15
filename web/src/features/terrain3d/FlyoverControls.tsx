/**
 * Contrôles UI du survol : lecture/pause, rembobinage, vitesse,
 * exagération verticale et barre de progression.
 *
 * Principe S (Single Responsibility) : ce composant ne fait qu'afficher
 * les contrôles et émettre les événements vers son parent. Il ne connaît
 * pas la caméra, le terrain ni le magasin partagé.
 *
 * Principe I (Interface Segregation) : il reçoit exactement les props
 * dont il a besoin, sans dépendre de l'interface complète `FlyoverControls`.
 */
import { Button } from "@/shared/ui/Button";
import {
  EXAGGERATION_STEPS,
  SPEED_STEPS,
  type ExaggerationFactor,
  type FlyoverSpeed,
} from "./flyover";

interface Props {
  playing: boolean;
  progressM: number;
  totalDistanceM: number;
  exaggeration: ExaggerationFactor;
  speed: FlyoverSpeed;
  onPlay: () => void;
  onPause: () => void;
  onRewind: () => void;
  onExaggerationChange: (v: ExaggerationFactor) => void;
  onSpeedChange: (v: FlyoverSpeed) => void;
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

export function FlyoverControls({
  playing,
  progressM,
  totalDistanceM,
  exaggeration,
  speed,
  onPlay,
  onPause,
  onRewind,
  onExaggerationChange,
  onSpeedChange,
}: Props) {
  const percent =
    totalDistanceM > 0 ? (progressM / totalDistanceM) * 100 : 0;

  return (
    <div
      className="flex flex-col gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-xs"
      aria-label="Contrôles du survol 3D"
    >
      {/* Lecture / pause / rembobinage */}
      <div className="flex items-center gap-2">
        <Button
          onClick={onRewind}
          aria-label="Rembobiner au début"
          className="px-2 py-1 text-xs"
        >
          ⏮
        </Button>
        {playing ? (
          <Button
            onClick={onPause}
            variant="primary"
            aria-label="Mettre en pause"
            className="px-2 py-1 text-xs"
          >
            ⏸ Pause
          </Button>
        ) : (
          <Button
            onClick={onPlay}
            variant="primary"
            aria-label="Lancer le survol"
            className="px-2 py-1 text-xs"
            disabled={totalDistanceM === 0}
          >
            ▶ Survol
          </Button>
        )}
        <span className="ml-auto text-[var(--text-muted)]">
          {formatDistance(progressM)}
          {totalDistanceM > 0 && ` / ${formatDistance(totalDistanceM)}`}
        </span>
      </div>

      {/* Barre de progression */}
      {totalDistanceM > 0 && (
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-2)]"
          role="progressbar"
          aria-valuenow={Math.round(percent)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Progression du survol"
        >
          <div
            className="h-full rounded-full bg-[var(--color-info)] transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
      )}

      {/* Vitesse */}
      <div className="flex items-center gap-1.5">
        <span className="text-[var(--text-muted)]">Vitesse</span>
        <div className="flex gap-1" role="radiogroup" aria-label="Vitesse du survol">
          {SPEED_STEPS.map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={speed === s}
              onClick={() => onSpeedChange(s)}
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold transition-all ${
                speed === s
                  ? "bg-[var(--color-info)] text-white"
                  : "bg-[var(--surface-2)] text-[var(--text-muted)]"
              }`}
            >
              ×{s}
            </button>
          ))}
        </div>
      </div>

      {/* Exagération verticale */}
      <div className="flex items-center gap-1.5">
        <span className="text-[var(--text-muted)]">Exagération</span>
        <div
          className="flex gap-1"
          role="radiogroup"
          aria-label="Exagération verticale"
        >
          {EXAGGERATION_STEPS.map((e) => (
            <button
              key={e}
              type="button"
              role="radio"
              aria-checked={exaggeration === e}
              onClick={() => onExaggerationChange(e)}
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold transition-all ${
                exaggeration === e
                  ? "bg-[var(--color-info)] text-white"
                  : "bg-[var(--surface-2)] text-[var(--text-muted)]"
              }`}
            >
              ×{e}
            </button>
          ))}
        </div>
        <span className="ml-1 text-[var(--text-muted)]" aria-live="polite">
          ×{exaggeration}
        </span>
      </div>
    </div>
  );
}
