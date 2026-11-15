/**
 * File de synthèse vocale — évite que deux synthèses se chevauchent.
 *
 * Principe S : gérer la file et la priorité est sa seule responsabilité.
 * Les requêtes `high` vident la file et parlent immédiatement.
 */
import { useCallback, useRef } from "react";
import type { SynthRequest } from "./types";
import type { ISpeechSynthesizer } from "./speechSynthesis";

export interface SpeechQueue {
  enqueue(req: SynthRequest): void;
  cancel(): void;
}

export function useSpeechQueue(synthesizer: ISpeechSynthesizer): SpeechQueue {
  const queue = useRef<SynthRequest[]>([]);
  const speaking = useRef(false);

  const processNext = useCallback(async () => {
    if (speaking.current || queue.current.length === 0) return;
    const req = queue.current.shift()!;
    speaking.current = true;
    try {
      await synthesizer.speak(req);
    } catch {
      // Silence en cas d'erreur de synthèse
    } finally {
      speaking.current = false;
      void processNext();
    }
  }, [synthesizer]);

  const enqueue = useCallback(
    (req: SynthRequest) => {
      if (req.priority === "high") {
        // Vide la file et interrompt la synthèse en cours
        queue.current = [req];
        synthesizer.cancel();
        speaking.current = false;
      } else {
        queue.current.push(req);
      }
      void processNext();
    },
    [synthesizer, processNext],
  );

  const cancel = useCallback(() => {
    queue.current = [];
    synthesizer.cancel();
    speaking.current = false;
  }, [synthesizer]);

  return { enqueue, cancel };
}
