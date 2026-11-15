/**
 * Flyover bar of the 3D view: play / pause, rewind, a seek slider along the route,
 * distance, and speed.
 */
import { SPEED_STEPS, type FlyoverSpeed } from "./flyover";

interface Props {
  playing: boolean;
  progressM: number;
  totalDistanceM: number;
  speed: FlyoverSpeed;
  onPlay: () => void;
  onPause: () => void;
  onRewind: () => void;
  onSeek: (m: number) => void;
  onSpeedChange: (v: FlyoverSpeed) => void;
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}

export function Segmented<T extends number | string>({
  label,
  options,
  value,
  onChange,
  format,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  format: (v: T) => string;
}) {
  return (
    <div className="flex gap-0.5 rounded-full border border-[var(--border)] p-0.5" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={String(o)}
          type="button"
          role="radio"
          aria-checked={value === o}
          onClick={() => onChange(o)}
          className={`h-6 min-w-8 rounded-full px-2 font-mono text-[11px] tabular-nums transition-colors ${
            value === o
              ? "bg-[var(--accent)] text-[var(--accent-ink)]"
              : "text-[var(--text-muted)] hover:text-[var(--text)]"
          }`}
        >
          {format(o)}
        </button>
      ))}
    </div>
  );
}

export function FlyoverControls({
  playing,
  progressM,
  totalDistanceM,
  speed,
  onPlay,
  onPause,
  onRewind,
  onSeek,
  onSpeedChange,
}: Props) {
  const disabled = totalDistanceM === 0;
  return (
    <div className="pane flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2.5" aria-label="3D flyover controls">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onRewind}
          disabled={disabled}
          aria-label="Rewind to start"
          className="grid size-9 place-items-center rounded-full text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--text)] disabled:opacity-40"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 5v14M18 6l-9 6 9 6V6Z" />
          </svg>
        </button>
        <button
          type="button"
          onClick={playing ? onPause : onPlay}
          disabled={disabled}
          aria-label={playing ? "Pause" : "Start flyover"}
          className="inline-flex h-9 items-center gap-2 rounded-full bg-[var(--accent)] pl-3 pr-4 text-sm font-medium text-[var(--accent-ink)] hover:brightness-110 disabled:opacity-40"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            {playing ? <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" /> : <path d="M7 4.5v15l12.5-7.5L7 4.5Z" />}
          </svg>
          {playing ? "Pause" : "Fly the route"}
        </button>
      </div>
      <label className="flex min-w-[12rem] flex-1 items-center gap-3">
        <span className="sr-only">Position along the route</span>
        <input
          type="range"
          min={0}
          max={Math.max(1, Math.round(totalDistanceM))}
          step={1}
          value={Math.round(progressM)}
          disabled={disabled}
          onChange={(e) => onSeek(Number(e.target.value))}
          aria-label="Flyover progress"
          className="h-1 flex-1 cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed"
        />
        <span className="whitespace-nowrap font-mono text-xs tabular-nums text-[var(--text-muted)]">
          {formatDistance(progressM)}
          {totalDistanceM > 0 && ` / ${formatDistance(totalDistanceM)}`}
        </span>
      </label>
      <div className="flex items-center gap-2">
        <span className="label-caps">Speed</span>
        <Segmented label="Flyover speed" options={SPEED_STEPS} value={speed} onChange={onSpeedChange} format={(s) => `×${s}`} />
      </div>
    </div>
  );
}
