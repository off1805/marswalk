/**
 * Hook React — reconnaissance vocale.
 *
 * Principe S : écouter le micro, transcrire et déclencher l'exécution
 * d'une commande. Pas de logique de synthèse ici.
 *
 * Principe I : expose exactement ce dont `VoiceButton` a besoin.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { looksLikeCommand } from "./commandParser";
import type { RecognitionState } from "./types";
import type { ISpeechRecognizer } from "./speechRecognition";

export interface VoiceRecognitionState {
  recognitionState: RecognitionState;
  transcript: string;
  /** Vrai pendant l'écoute ou le traitement — pour le style du bouton. */
  active: boolean;
  toggle: () => void;
}

export function useVoiceRecognition(
  recognizer: ISpeechRecognizer,
  onCommand: (transcript: string) => void,
): VoiceRecognitionState {
  const [state, setState] = useState<RecognitionState>(() =>
    recognizer.isSupported() ? "idle" : "unsupported",
  );
  const [transcript, setTranscript] = useState("");
  const listeningRef = useRef(false);

  useEffect(() => {
    if (!recognizer.isSupported()) return;

    recognizer.onResult((text, isFinal) => {
      setTranscript(text);

      if (isFinal) {
        setState("processing");
        onCommand(text);
        setTranscript("");
      } else if (looksLikeCommand(text)) {
        setState("processing");
      }
    });

    recognizer.onError((error) => {
      // "no-speech" est attendu quand l'utilisateur ne parle pas
      if (error !== "no-speech") setState("error");
      else setState("idle");
      listeningRef.current = false;
    });

    recognizer.onEnd(() => {
      listeningRef.current = false;
      setState((prev) => (prev === "processing" ? "idle" : "idle"));
    });
  }, [recognizer, onCommand]);

  const toggle = useCallback(() => {
    if (!recognizer.isSupported()) return;

    if (listeningRef.current) {
      recognizer.stop();
      listeningRef.current = false;
      setState("idle");
    } else {
      recognizer.start();
      listeningRef.current = true;
      setState("listening");
      setTranscript("");
    }
  }, [recognizer]);

  return {
    recognitionState: state,
    transcript,
    active: state === "listening" || state === "processing",
    toggle,
  };
}
