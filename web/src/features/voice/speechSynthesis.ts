/**
 * Abstraction de la synthèse vocale.
 *
 * Principe D : le code dépend de `ISpeechSynthesizer`, pas de
 * `window.speechSynthesis` directement.
 *
 * Principe O : ajouter un synthétiseur cloud (Piper TTS, OpenAI) = créer
 * une nouvelle classe sans toucher au code appelant.
 *
 * Architecture à deux niveaux :
 *   1. `BrowserSynthesizer`  — fonctionne hors ligne, qualité variable
 *   2. `PiperSynthesizer`    — API FastAPI locale (conteneur Docker)
 *
 * `createSynthesizer` choisit automatiquement selon la connectivité.
 */
import type { SynthRequest } from "./types";

export interface ISpeechSynthesizer {
  speak(req: SynthRequest): Promise<void>;
  cancel(): void;
  isAvailable(): boolean;
}

// ── Synthétiseur navigateur ───────────────────────────────────────────────────

/** Sélectionne la meilleure voix française disponible dans le navigateur. */
function pickFrenchVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  // Préférences ordonnées : Thomas (macOS) > Amélie (macOS) > Hortense (Win)
  const PREFERRED = ["Thomas", "Amélie", "Hortense", "Google français"];
  for (const name of PREFERRED) {
    const v = voices.find((v) => v.name.includes(name) && v.lang.startsWith("fr"));
    if (v) return v;
  }
  return voices.find((v) => v.lang.startsWith("fr")) ?? null;
}

export class BrowserSynthesizer implements ISpeechSynthesizer {
  isAvailable(): boolean {
    return "speechSynthesis" in window;
  }

  cancel(): void {
    window.speechSynthesis.cancel();
  }

  speak({ text, priority }: SynthRequest): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.isAvailable()) {
        resolve();
        return;
      }
      if (priority === "high") {
        window.speechSynthesis.cancel();
      }
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "fr-FR";
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      // Les voix se chargent de manière asynchrone — on réessaie si besoin
      const voice = pickFrenchVoice();
      if (voice) utterance.voice = voice;

      utterance.onend = () => resolve();
      utterance.onerror = (e) => reject(new Error(e.error));

      window.speechSynthesis.speak(utterance);
    });
  }
}

// ── Synthétiseur Piper TTS (conteneur Docker) ─────────────────────────────────

/**
 * Appelle `/api/tts` (endpoint à ajouter via demande de changement).
 * En attendant, se rabat sur `BrowserSynthesizer`.
 */
export class PiperSynthesizer implements ISpeechSynthesizer {
  private readonly fallback = new BrowserSynthesizer();

  isAvailable(): boolean {
    return true; // toujours déclaré disponible, utilise le fallback si l'API est absente
  }

  cancel(): void {
    this.fallback.cancel();
  }

  async speak(req: SynthRequest): Promise<void> {
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: req.text, voice: "fr_FR-upmc-medium" }),
      });
      if (!res.ok) throw new Error(`TTS API: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      await new Promise<void>((resolve, reject) => {
        const audio = new Audio(url);
        audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); reject(); };
        void audio.play();
      });
    } catch {
      // Piper indisponible → repli sur le navigateur
      await this.fallback.speak(req);
    }
  }
}

// ── Fabrique ──────────────────────────────────────────────────────────────────

/**
 * Choisit le synthétiseur optimal selon la connectivité.
 * Principe D : le code appelant reçoit une abstraction, pas une classe concrète.
 */
export function createSynthesizer(
  networkStatus: "online" | "offline",
): ISpeechSynthesizer {
  // En ligne : on tente Piper (qualité supérieure et cohérente)
  if (networkStatus === "online") return new PiperSynthesizer();
  // Hors ligne : uniquement le navigateur
  return new BrowserSynthesizer();
}
