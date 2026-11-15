/**
 * Panneau assembleur de la feature vocale — slot map-overlay.
 *
 * Flux :
 *   1. useSpeechQueue    → file de synthèse anglaise (une voix à la fois)
 *   2. useAlertSpeaker   → lit les alertes danger automatiquement en anglais
 *   3. useVoiceCommands  → traduit les commandes en actions magasin/API
 *   4. useVoiceRecognition → gère l'état micro + wake word Nebula
 *   5. VoiceButton       → affiche l'état et permet le toggle
 *
 * Principe S : orchestrer, ne pas calculer.
 * Principe D : dépend des abstractions exposées par les hooks.
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

  const speechQueue = useSpeechQueue(synthesizer);

  // Lecture automatique des alertes en anglais
  useAlertSpeaker(speechQueue);

  const { execute } = useVoiceCommands(speechQueue);

  const handleTranscript = useCallback(
    (transcript: string) => {
      void execute(parseCommand(transcript));
    },
    [execute],
  );

  const { recognitionState, transcript, toggle } = useVoiceRecognition(
    recognizer,
    speechQueue,
    handleTranscript,
  );

  return (
    <div
      className="absolute bottom-16 right-4 z-20"
      aria-label="Nebula voice assistant"
    >
      <VoiceButton
        state={recognitionState}
        transcript={transcript}
        onToggle={toggle}
      />
    </div>
  );
}
