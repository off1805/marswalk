/**
 * Hook — reconnaissance vocale avec wake word.
 *
 * Flux d'état :
 *
 *   idle
 *    │  [1er clic bouton]
 *    ▼
 *   wakeWord ◄──────────────────────────────────────────────────┐
 *    │  [« Nebula » détecté]  → synthèse répond aléatoirement   │
 *    ▼                                                           │
 *   listening ──[timeout 8 s / erreur no-speech]───────────────►┤
 *    │  [commande finale reconnue]                               │
 *    ▼                                                           │
 *   processing ──────────────────────────────────────────────── ┘
 *
 * [2e clic en état wakeWord] → listening (bypass du wake word, pour la démo)
 * [clic en état listening/processing] → idle (annuler complètement)
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
const COMMAND_TIMEOUT_MS = 8_000;

export function useVoiceRecognition(
  recognizer: ISpeechRecognizer,
  speechQueue: SpeechQueue,
  onCommand: (transcript: string) => void,
): VoiceRecognitionState {
  const [state, setState]       = useState<RecognitionState>(() =>
    recognizer.isSupported() ? "idle" : "unsupported",
  );
  const [transcript, setTranscript] = useState("");
  const listeningRef   = useRef(false);
  const timeoutRef     = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Écoute active de commandes ──────────────────────────────────────────────

  const startCommandListening = useCallback(() => {
    if (!recognizer.isSupported()) return;

    recognizer.start();
    listeningRef.current = true;
    setState("listening");
    setTranscript("");

    // Timeout : si aucune commande en 8 s, retour en wake word
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      if (!listeningRef.current) return;
      recognizer.stop();
      listeningRef.current = false;
      setState("wakeWord");
      speechQueue.enqueue({ text: "No command received. I'm still listening for Nebula.", priority: "low" });
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
      setTranscript(text);
      if (isFinal) {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        listeningRef.current = false;
        setState("processing");
        onCommand(text);
        setTranscript("");
        // Retour automatique en écoute passive
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
  }, [recognizer, onCommand]);

  // ── Wake word : écoute passive ─────────────────────────────────────────────

  useWakeWord(
    state === "wakeWord",
    useCallback(() => {
      // Nebula détecté → réponse vocale aléatoire puis écoute de commande
      const response = randomWakeResponse();
      speechQueue.enqueue({ text: response, priority: "low" });
      // Petit délai pour laisser la synthèse commencer avant d'ouvrir le micro
      setTimeout(startCommandListening, 600);
    }, [speechQueue, startCommandListening]),
  );

  // ── Bouton toggle ──────────────────────────────────────────────────────────

  const toggle = useCallback(() => {
    if (!recognizer.isSupported()) return;

    switch (state) {
      case "idle":
        // Première activation → mode wake word
        setState("wakeWord");
        speechQueue.enqueue({ text: "Wake word mode activated. Say Nebula to give a command.", priority: "low" });
        break;

      case "wakeWord":
        // 2e clic → bypass du wake word (accès direct, utile en démo)
        startCommandListening();
        break;

      case "listening":
      case "processing":
        // Annuler
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
