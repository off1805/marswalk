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
 *   voice.test.ts            —    Tests unitaires (parser, commandParser)
 *
 * Contrainte : `registry.ts` est gelé (T00) et ne liste pas V1.
 * Contournement : `setup()` monte `VoicePanel` via un portail React dans un
 * div dédié injecté dans le DOM, sans slot officiel.
 * La demande de changement est dans `tasks/change-requests/V1-registry-voice.md`.
 */
import { type Feature } from "@/app/feature";
import { VoicePanel } from "./VoicePanel";

/** Monte VoicePanel dans le DOM via un portail React au démarrage. */
async function setupVoice(): Promise<void> {
  // On attend que React ait rendu le DOM racine
  await new Promise<void>((resolve) => {
    if (document.getElementById("root")) resolve();
    else {
      const obs = new MutationObserver(() => {
        if (document.getElementById("root")) { obs.disconnect(); resolve(); }
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
  });

  // Créer un div hôte et l'ajouter dans le body
  const host = document.createElement("div");
  host.id = "v1-voice-host";
  document.body.appendChild(host);

  // Monter VoicePanel via un portail (import dynamique pour ne pas alourdir le bundle initial)
// Mounted via setup() portal — createPortal not needed at module level
  const { createElement } = await import("react");
  const { createRoot } = await import("react-dom/client");
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { queryClient } = await import("@/app/App");
  const { BrowserRouter } = await import("react-router");

  const root = createRoot(host);
  root.render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(BrowserRouter, null, createElement(VoicePanel)),
    ),
  );

  // Écouter les événements DOM pour la pause/vitesse du survol F6
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
  panels: [],  // Pas de slot officiel — contournement via setup()
  routes: [],
  setup: setupVoice,
};

// Exports pour les tests
export { parseCommand, looksLikeCommand } from "./commandParser";
export { MockSpeechRecognizer } from "./speechRecognition";
export { __setRecognizerForTest, __setSynthesizerForTest } from "./serviceRegistry";
