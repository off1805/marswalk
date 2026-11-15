/**
 * Bouton micro — interface principale de l'assistant vocal.
 *
 * États visuels (couleur + icône + texte — ENF-06) :
 *   idle       🌙 gris       — cliquer pour activer
 *   wakeWord   👂 bleu pulsé — attend « Nebula »
 *   listening  🎙 vert animé — écoute une commande
 *   processing ⟳ rotation   — traitement
 *   error      ⚠ orange     — erreur micro
 *   unsupported 🚫 désactivé
 */
import type { RecognitionState } from "./types";
import { WAKE_WORD } from "./commandParser";

interface Props {
  state: RecognitionState;
  transcript: string;
  onToggle: () => void;
}

const LABEL: Record<RecognitionState, string> = {
  unsupported : "Voice not supported in this browser",
  idle        : `Activate Nebula voice assistant`,
  wakeWord    : `Waiting for wake word "${WAKE_WORD}"… click to skip`,
  listening   : "Listening for command… click to cancel",
  processing  : "Processing command…",
  error       : "Microphone error — click to retry",
};

const ICON: Record<RecognitionState, string> = {
  unsupported : "🚫",
  idle        : "🌙",
  wakeWord    : "👂",
  listening   : "🎙",
  processing  : "⟳",
  error       : "⚠",
};

const HINT: Partial<Record<RecognitionState, string>> = {
  idle     : `Say "${WAKE_WORD}"`,
  wakeWord : `Say "${WAKE_WORD}"`,
  listening: "Speak now…",
  processing: "Processing…",
  error    : "▲ Mic error",
};

export function VoiceButton({ state, transcript, onToggle }: Props) {
  const disabled     = state === "unsupported";
  const isWakeWord   = state === "wakeWord";
  const isListening  = state === "listening";
  const isProcessing = state === "processing";
  const isError      = state === "error";
  const isActive     = isWakeWord || isListening || isProcessing;

  const colorClass =
    isListening  ? "border-[var(--color-ok)] bg-[var(--color-ok)] text-white"
    : isWakeWord ? "border-[var(--color-info)] bg-[var(--surface)] text-[var(--color-info)]"
    : isError    ? "border-[var(--color-caution)] bg-[var(--surface)] text-[var(--color-caution)]"
    : isProcessing? "border-[var(--color-info)] bg-[var(--surface)] text-[var(--color-info)]"
    : "border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] hover:border-[var(--color-info)] hover:text-[var(--color-info)]";

  return (
    <div className="flex flex-col items-end gap-1 select-none">
      <button
        type="button"
        onClick={onToggle}
        disabled={disabled}
        aria-label={LABEL[state]}
        aria-pressed={isActive}
        title={LABEL[state]}
        className={[
          "relative flex h-11 w-11 items-center justify-center rounded-full",
          "border-2 text-xl transition-all duration-200",
          "disabled:opacity-40 disabled:cursor-not-allowed",
          "focus:outline-none focus:ring-2 focus:ring-[var(--focus)]",
          colorClass,
        ].join(" ")}
      >
        {/* Pulsation lente — wake word */}
        {isWakeWord && (
          <span
            className="absolute inset-0 rounded-full border-2 border-[var(--color-info)] animate-ping opacity-25"
            style={{ animationDuration: "2.5s" }}
            aria-hidden="true"
          />
        )}
        {/* Pulsation vive — écoute commande */}
        {isListening && (
          <span
            className="absolute inset-0 rounded-full border-2 border-[var(--color-ok)] animate-ping opacity-50"
            aria-hidden="true"
          />
        )}

        <span
          aria-hidden="true"
          className={isProcessing ? "animate-spin inline-block" : ""}
        >
          {ICON[state]}
        </span>
      </button>

      {/* Transcription en direct */}
      {transcript && (
        <p
          className="max-w-[200px] rounded bg-[var(--surface)] px-2 py-0.5 text-right text-[10px] italic text-[var(--text-muted)] shadow"
          aria-live="polite"
        >
          « {transcript} »
        </p>
      )}

      {/* Indication textuelle d'état */}
      {!transcript && HINT[state] && (
        <p
          className={[
            "text-right text-[10px]",
            isListening  ? "text-[var(--color-ok)]"
            : isWakeWord ? "text-[var(--color-info)]"
            : isError    ? "text-[var(--color-caution)]"
            : "text-[var(--text-muted)]",
          ].join(" ")}
          role={isError ? "alert" : "status"}
          aria-live="polite"
        >
          {HINT[state]}
        </p>
      )}
    </div>
  );
}
