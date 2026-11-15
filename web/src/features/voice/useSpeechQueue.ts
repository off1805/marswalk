/**
 * File de synthèse vocale.
 *
 * Principe S : gérer la file, la priorité et l'état de parole est sa seule
 * responsabilité.
 *
 * Expose `isSpeaking` pour que l'écoute du micro puisse se mettre en pause
 * pendant que Nebula parle — évite l'écho (le micro qui capte la synthèse).
 */
import { useCallback, useRef, useState } from "react";
import type { SynthRequest } from "./types";
import type { ISpeechSynthesizer } from "./speechSynthesis";

export interface SpeechQueue {
  enqueue(req: SynthRequest): void;
  cancel(): void;
  /** Vrai pendant toute la durée d'une synthèse vocale. */
  isSpeaking: boolean;
}

export function useSpeechQueue(synthesizer: ISpeechSynthesizer): SpeechQueue {
  const queue      = useRef<SynthRequest[]>([]);
  const speakingRef = useRef(false);
  // État React pour déclencher les re-renders dans les consommateurs
  const [isSpeaking, setIsSpeaking] = useState(false);

  const setSpeaking = useCallback((val: boolean) => {
    speakingRef.current = val;
    setIsSpeaking(val);
  }, []);

  const processNext = useCallback(async () => {
    if (speakingRef.current || queue.current.length === 0) return;
    const req = queue.current.shift()!;
    setSpeaking(true);
    try {
      await synthesizer.speak(req);
    } catch {
      // Erreur de synthèse silencieuse
    } finally {
      setSpeaking(false);
      void processNext();
    }
  }, [synthesizer, setSpeaking]);

  const enqueue = useCallback(
    (req: SynthRequest) => {
      if (req.priority === "high") {
        queue.current = [req];
        synthesizer.cancel();
        setSpeaking(false);
      } else {
        queue.current.push(req);
      }
      void processNext();
    },
    [synthesizer, processNext, setSpeaking],
  );

  const cancel = useCallback(() => {
    queue.current = [];
    synthesizer.cancel();
    setSpeaking(false);
  }, [synthesizer, setSpeaking]);

  return { enqueue, cancel, isSpeaking };
}
