/**
 * Assistant vocal (V1).
 *
 * Architecture (principes SOLID) :
 *
 *   types.ts                 I    Interfaces internes
 *   commandParser.ts         S+O  Parseur pur (texte → commande, extensible)
 *   speechRecognition.ts     S+D  Abstraction Web Speech API (injectable)
 *   speechSynthesis.ts       S+O  Abstraction synthèse, deux niveaux (injectable)
 *   serviceRegistry.ts       D    Composition root des singletons
 *   useSpeechQueue.ts        S    File de synthèse sans chevauchement
 *   useVoiceRecognition.ts   S+I  Hook micro → transcription
 *   useVoiceCommands.ts      S+D  Hook transcription → action magasin/API
 *   useAlertSpeaker.ts       S+D  Hook lecture des alertes (via cache TanStack Query)
 *   VoiceButton.tsx          S+I  Bouton micro avec état visible et textuel
 *   VoicePanel.tsx           S+D  Assembleur des hooks et composants
 *   voice.test.ts            —    Tests unitaires du parseur
 *
 * Enregistrée dans registry.ts via la PR contracts/add-voice-to-registry.
 * Slot : map-overlay, order 30 (en dessous du badge offline F7).
 */
import type { Feature } from "@/app/feature";
import { VoicePanel } from "./VoicePanel";

/** Relaie les événements DOM de V1 vers F6 (survol). */
function setupVoiceEventBridge(): void {
  window.addEventListener("v1:flyover:pause", () => {
    window.dispatchEvent(new CustomEvent("f6:flyover:pause"));
  });
  window.addEventListener("v1:flyover:speed", (e: Event) => {
    window.dispatchEvent(
      new CustomEvent("f6:flyover:speed", {
        detail: (e as CustomEvent<number>).detail,
      }),
    );
  });
}

export const feature: Feature = {
  id: "voice",
  panels: [
    {
      slot: "map-overlay",
      order: 30,
      component: VoicePanel,
      modes: ["map"],
    },
  ],
  routes: [],
  setup: setupVoiceEventBridge,
};

// Exports pour les tests
export { parseCommand, looksLikeCommand } from "./commandParser";
export { MockSpeechRecognizer } from "./speechRecognition";
export { __setRecognizerForTest, __setSynthesizerForTest } from "./serviceRegistry";
