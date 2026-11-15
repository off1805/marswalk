/**
 * Hook — reconnaissance vocale avec wake word et protection anti-écho.
 *
 * Flux d'état :
 *
 *   idle
 *    │  [1er clic]
 *    ▼
 *   wakeWord ◄─────────────────────────────────────────────────────┐
 *    │  [« Nebula » détecté]                                       │
 *    │    → micro STOP                                             │
 *    │    → synthèse répond aléatoirement  (isSpeaking = true)     │
 *    │    → micro RESTART quand isSpeaking = false                 │
 *    ▼                                                             │
 *   listening ──[timeout 8 s / no-speech]─────────────────────────┤
 *    │  [commande finale reconnue]                                 │
 *    ▼                                                             │
 *   processing ───────────────────────────────────────────────────┘
 *
 * Anti-écho : useWakeWord reçoit `paused = isSpeaking`. Tant que Nebula
 * parle, le reconnaisseur de wake word est arrêté. Il redémarre dès que
 * la synthèse termine. Même protection pour le micro de commandes.
 *
 * Principe S : gérer l'état de l'écoute est sa seule responsabilité.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { looksLikeCommand, randomWakeResponse } from "./commandParser";
import { useWakeWord } from "./useWakeWord";
import type { RecognitionState } from "./types";
import type { ISpeechRecognizer } from "./speechRecognition";
import type { SpeechQueue } from "./useSpeechQueue";

export interface VoiceRecognitionState {
  recognitionState: RecognitionState;
  transcript: string;
  active: boolean;
  toggle: () => void;
}

/** Durée max d'écoute d'une commande en ms. */
const COMMAND_TIMEOUT_MS = 15_000;

export function useVoiceRecognition(
  recognizer: ISpeechRecognizer,
  speechQueue: SpeechQueue,
  onCommand: (transcript: string) => void,
): VoiceRecognitionState {
  const [state, setState]           = useState<RecognitionState>(() =>
    recognizer.isSupported() ? "idle" : "unsupported",
  );
  const [transcript, setTranscript] = useState("");
  const listeningRef                = useRef(false);
  const timeoutRef                  = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Raccourci vers l'état de synthèse (vrai = Nebula parle)
  const { isSpeaking } = speechQueue;

  // ── Anti-écho : stopper le micro de commande si Nebula parle ───────────────
  useEffect(() => {
    if (isSpeaking && listeningRef.current) {
      // Nebula commence à parler pendant l'écoute de commande → stopper
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      recognizer.stop();
      listeningRef.current = false;
      // On ne change pas l'état : il reviendra à wakeWord via onEnd
    }
  }, [isSpeaking, recognizer]);

  // ── Écoute active de commandes ─────────────────────────────────────────────

  const startCommandListening = useCallback(() => {
    if (!recognizer.isSupported()) return;

    recognizer.start();
    listeningRef.current = true;
    setState("listening");
    setTranscript("");

    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      if (!listeningRef.current) return;
      recognizer.stop();
      listeningRef.current = false;
      setState("wakeWord");
      speechQueue.enqueue({
        text: "No command received after 15 seconds. I'm still listening for Nebula.",
        priority: "low",
      });
    }, COMMAND_TIMEOUT_MS);
  }, [recognizer, speechQueue]);

  const stopCommandListening = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    recognizer.stop();
    listeningRef.current = false;
  }, [recognizer]);

  // ── Callbacks du reconnaisseur de commandes ────────────────────────────────

  useEffect(() => {
    if (!recognizer.isSupported()) return;

    recognizer.onResult((text, isFinal) => {
      // Ignorer si Nebula parle (écho)
      if (isSpeaking) return;

      setTranscript(text);
      if (isFinal) {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        listeningRef.current = false;
        setState("processing");
        onCommand(text);
        setTranscript("");
        setState("wakeWord");
      } else if (looksLikeCommand(text)) {
        setState("processing");
      }
    });

    recognizer.onError((error) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      listeningRef.current = false;
      if (error === "no-speech" || error === "aborted") {
        setState("wakeWord");
      } else {
        setState("error");
      }
    });

    recognizer.onEnd(() => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      listeningRef.current = false;
      setState((prev) => prev === "listening" ? "wakeWord" : prev);
    });
  }, [recognizer, onCommand, isSpeaking]);

  // ── Wake word : écoute passive (pausée quand Nebula parle) ────────────────

  useWakeWord(
    state === "wakeWord",
    isSpeaking,   // ← pause le reconnaisseur pendant la synthèse
    useCallback(() => {
      // Nebula détecté → réponse aléatoire, puis ouverture du micro de commande
      // Le micro de commande s'ouvre APRÈS la fin de la synthèse grâce à isSpeaking
      const response = randomWakeResponse();
      speechQueue.enqueue({ text: response, priority: "low" });

      // On attend que la synthèse soit terminée pour ouvrir le micro
      // en observant isSpeaking via un polling léger
      let attempts = 0;
      const waitAndStart = () => {
        attempts++;
        if (attempts > 50) return; // sécurité max 5 s
        if (speechQueue.isSpeaking) {
          setTimeout(waitAndStart, 100);
        } else {
          // Synthèse terminée → petit délai supplémentaire (réverbération)
          setTimeout(startCommandListening, 200);
        }
      };
      // Laisser la synthèse démarrer (100 ms) avant de commencer à attendre
      setTimeout(waitAndStart, 100);
    }, [speechQueue, startCommandListening]),
  );

  // ── Bouton toggle ──────────────────────────────────────────────────────────

  const toggle = useCallback(() => {
    if (!recognizer.isSupported()) return;

    switch (state) {
      case "idle":
        setState("wakeWord");
        speechQueue.enqueue({
          text: "Wake word mode activated. Say Nebula to give a command.",
          priority: "low",
        });
        break;

      case "wakeWord":
        // Bypass du wake word (accès direct, utile en démo)
        startCommandListening();
        break;

      case "listening":
      case "processing":
        stopCommandListening();
        setState("idle");
        speechQueue.enqueue({ text: "Voice assistant deactivated.", priority: "low" });
        break;

      case "error":
        setState("wakeWord");
        break;

      case "unsupported":
        break;
    }
  }, [state, recognizer, speechQueue, startCommandListening, stopCommandListening]);

  // Nettoyage
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      recognizer.stop();
    };
  }, [recognizer]);

  return {
    recognitionState: state,
    transcript,
    active: state === "listening" || state === "processing",
    toggle,
  };
}
