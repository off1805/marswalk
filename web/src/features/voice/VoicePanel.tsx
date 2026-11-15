/**
 * Panneau assembleur de la feature vocale — slot `map-overlay`.
 *
 * Principe S : orchestrer les hooks et composants est sa seule responsabilité.
 * Principe D : dépend des abstractions exposées par ses hooks.
 *
 * Ce composant :
 *   1. Instancie les singletons via `serviceRegistry`.
 *   2. Monte la file de synthèse (`useSpeechQueue`).
 *   3. Active la lecture automatique des alertes (`useAlertSpeaker`).
 *   4. Exécute les commandes (`useVoiceCommands`).
 *   5. Gère la reconnaissance (`useVoiceRecognition`).
 *   6. Affiche `VoiceButton`.
 */
import { useCallback } from "react";
import { getRecognizer, getSynthesizer } from "./serviceRegistry";
import { useSpeechQueue } from "./useSpeechQueue";
import { useAlertSpeaker } from "./useAlertSpeaker";
import { useVoiceCommands } from "./useVoiceCommands";
import { useVoiceRecognition } from "./useVoiceRecognition";
import { parseCommand } from "./commandParser";
import { VoiceButton } from "./VoiceButton";

export function VoicePanel() {
  const recognizer = getRecognizer();
  const synthesizer = getSynthesizer();

  // File de synthèse — une seule voix à la fois, priorité respectée
  const speechQueue = useSpeechQueue(synthesizer);

  // Lecture automatique des alertes danger
  useAlertSpeaker(speechQueue);

  // Exécution des commandes
  const { execute } = useVoiceCommands(speechQueue);

  // Callback : transcription finale → parse → exécute
  const handleTranscript = useCallback(
    (transcript: string) => {
      const cmd = parseCommand(transcript);
      void execute(cmd);
    },
    [execute],
  );

  // Reconnaissance vocale
  const { recognitionState, transcript, toggle } = useVoiceRecognition(
    recognizer,
    handleTranscript,
  );

  return (
    <div
      className="absolute bottom-16 right-4 z-20"
      aria-label="Assistant vocal"
    >
      <VoiceButton
        state={recognitionState}
        transcript={transcript}
        onToggle={toggle}
      />
    </div>
  );
}
