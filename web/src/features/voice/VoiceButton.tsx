/**
 * Bouton micro — interface principale de l'assistant vocal.
 *
 * Principe S : afficher l'état du micro et permettre de l'activer/désactiver
 * est sa seule responsabilité.
 *
 * Principe I : reçoit exactement ce dont il a besoin depuis `VoicePanel`.
 *
 * La couleur n'est jamais le seul indice (ENF-06) : forme + animation + texte.
 */
import type { RecognitionState } from "./types";

interface Props {
  state: RecognitionState;
  transcript: string;
  onToggle: () => void;
}

const STATE_LABEL: Record<RecognitionState, string> = {
  unsupported: "Voix non supportée",
  idle: "Activer le micro",
  listening: "Écoute en cours… (cliquez pour arrêter)",
  processing: "Traitement…",
  error: "Erreur micro — cliquez pour réessayer",
};

const STATE_ICON: Record<RecognitionState, string> = {
  unsupported: "🎙̶",
  idle: "🎙",
  listening: "🎙",
  processing: "⟳",
  error: "⚠",
};

export function VoiceButton({ state, transcript, onToggle }: Props) {
  const disabled = state === "unsupported";
  const active = state === "listening" || state === "processing";
  const isError = state === "error";

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={onToggle}
        disabled={disabled}
        aria-label={STATE_LABEL[state]}
        aria-pressed={active}
        className={`
          relative flex h-10 w-10 items-center justify-center rounded-full
          border-2 text-lg font-bold transition-all
          disabled:opacity-40 disabled:cursor-not-allowed
          focus:outline-none focus:ring-2 focus:ring-[var(--focus)]
          ${active
            ? "border-[var(--color-info)] bg-[var(--color-info)] text-white shadow-lg"
            : isError
            ? "border-[var(--color-caution)] bg-[var(--surface)] text-[var(--color-caution)]"
            : "border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:border-[var(--color-info)]"
          }
        `}
      >
        {/* Anneau d'animation quand actif */}
        {state === "listening" && (
          <span
            className="absolute inset-0 rounded-full border-2 border-[var(--color-info)] animate-ping opacity-50"
            aria-hidden="true"
          />
        )}
        <span aria-hidden="true">{STATE_ICON[state]}</span>
      </button>

      {/* Transcription en direct */}
      {transcript && (
        <p
          className="max-w-[200px] text-center text-[10px] text-[var(--text-muted)] italic"
          aria-live="polite"
          aria-label="Transcription en cours"
        >
          « {transcript} »
        </p>
      )}

      {/* État textuel accessible */}
      {!transcript && active && (
        <p
          className="text-[10px] text-[var(--color-info)]"
          aria-live="polite"
          role="status"
        >
          {state === "listening" ? "Je vous écoute…" : "Traitement…"}
        </p>
      )}

      {isError && (
        <p className="text-[10px] text-[var(--color-caution)]" role="alert">
          ▲ Erreur micro
        </p>
      )}
    </div>
  );
}
