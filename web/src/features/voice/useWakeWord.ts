/**
 * Écoute permanente du mot de réveil « Nebula ».
 *
 * Principe S : détecter le mot de réveil est sa seule responsabilité.
 * Il ne connaît pas les commandes ni la synthèse.
 *
 * Quand active = true :
 *   - Un reconnaisseur en-US tourne en mode continu.
 *   - Dès que « Nebula » est détecté, onWake() est appelé et l'écoute s'arrête.
 *   - En cas d'erreur ou de fin, il redémarre automatiquement (back-off 500 ms).
 *
 * Quand active = false : tout s'arrête proprement.
 */
import { useEffect, useRef } from "react";
import { containsWakeWord } from "./commandParser";

// Types inline identiques à speechRecognition.ts
interface SpeechRecognitionEvent {
  results: { [i: number]: { [j: number]: { transcript: string }; isFinal: boolean }; length: number };
}
interface WakeRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
interface WakeRecognitionCtor { new(): WakeRecognitionInstance; }

export function useWakeWord(active: boolean, onWake: () => void): void {
  const recRef      = useRef<WakeRecognitionInstance | null>(null);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onWakeRef   = useRef(onWake);
  const stoppedRef  = useRef(false);
  onWakeRef.current = onWake;

  useEffect(() => {
    const w = window as unknown as {
      SpeechRecognition?: WakeRecognitionCtor;
      webkitSpeechRecognition?: WakeRecognitionCtor;
    };
    const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;

    if (!SR || !active) {
      stoppedRef.current = true;
      recRef.current?.stop();
      recRef.current = null;
      return;
    }

    stoppedRef.current = false;

    function startListening() {
      if (stoppedRef.current) return;

      const rec = new SR!();
      rec.continuous      = true;
      rec.interimResults  = true;
      rec.lang            = "en-US";
      rec.maxAlternatives = 2;

      rec.onresult = (e) => {
        for (let i = 0; i < e.results.length; i++) {
          const r = e.results[i];
          if (!r) continue;
          // Vérifier chaque alternative
          for (let j = 0; j < 2; j++) {
            const alt = r[j];
            if (alt && containsWakeWord(alt.transcript)) {
              rec.stop();
              onWakeRef.current();
              return;
            }
          }
        }
      };

      rec.onerror = ({ error }) => {
        if (stoppedRef.current) return;
        // "no-speech" est normal en écoute continue
        if (error !== "aborted") {
          timerRef.current = setTimeout(startListening, 1_000);
        }
      };

      rec.onend = () => {
        if (!stoppedRef.current) {
          timerRef.current = setTimeout(startListening, 500);
        }
      };

      recRef.current = rec;
      rec.start();
    }

    startListening();

    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      recRef.current?.stop();
      recRef.current = null;
    };
  }, [active]);
}
