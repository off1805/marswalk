/**
 * Écoute permanente du mot de réveil « Nebula ».
 *
 * Principe S : détecter le mot de réveil est sa seule responsabilité.
 *
 * Paramètre `paused` : quand vrai (Nebula est en train de parler), l'écoute
 * s'arrête proprement pour éviter que le micro capte la synthèse vocale.
 * Dès que `paused` repasse à false, l'écoute redémarre automatiquement.
 */
import { useEffect, useRef } from "react";
import { containsWakeWord } from "./commandParser";

interface WakeRecognitionEvent {
  results: { [i: number]: { [j: number]: { transcript: string }; isFinal: boolean }; length: number };
}
interface WakeRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((e: WakeRecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
interface WakeRecognitionCtor { new(): WakeRecognitionInstance; }

export function useWakeWord(
  active: boolean,
  paused: boolean,
  onWake: () => void,
): void {
  const recRef     = useRef<WakeRecognitionInstance | null>(null);
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);
  const pausedRef  = useRef(paused);
  const onWakeRef  = useRef(onWake);

  // Mettre à jour les refs sans redémarrer l'effet
  onWakeRef.current = onWake;
  pausedRef.current = paused;

  // Réagir à paused : arrêter ou relancer l'écoute
  useEffect(() => {
    if (!active) return;

    if (paused) {
      // Nebula parle — arrêter le micro immédiatement
      if (timerRef.current) clearTimeout(timerRef.current);
      recRef.current?.stop();
      recRef.current = null;
    }
    // Quand paused repasse à false, l'effet principal (ci-dessous) redémarre
    // automatiquement car `paused` est dans ses dépendances.
  }, [paused, active]);

  // Effet principal : démarrer / arrêter l'écoute passive
  useEffect(() => {
    const w = window as unknown as {
      SpeechRecognition?: WakeRecognitionCtor;
      webkitSpeechRecognition?: WakeRecognitionCtor;
    };
    const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;

    if (!SR || !active || paused) {
      stoppedRef.current = true;
      recRef.current?.stop();
      recRef.current = null;
      return;
    }

    stoppedRef.current = false;

    function startListening() {
      if (stoppedRef.current || pausedRef.current) return;

      const rec = new SR!();
      rec.continuous      = true;
      rec.interimResults  = true;
      rec.lang            = "en-US";
      rec.maxAlternatives = 2;

      rec.onresult = (e) => {
        // Ne pas traiter si Nebula est en train de parler
        if (pausedRef.current) return;

        for (let i = 0; i < e.results.length; i++) {
          const r = e.results[i];
          if (!r) continue;
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
        if (stoppedRef.current || pausedRef.current) return;
        if (error !== "aborted") {
          timerRef.current = setTimeout(startListening, 1_000);
        }
      };

      rec.onend = () => {
        if (!stoppedRef.current && !pausedRef.current) {
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
  }, [active, paused]);
}
