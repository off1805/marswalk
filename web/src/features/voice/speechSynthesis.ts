/**
 * Synthèse vocale en anglais (en-US).
 *
 * Préférence de voix (ordre décroissant de qualité) :
 *   Google US English   Chrome/Edge — qualité excellente
 *   Samantha            macOS — claire, naturelle
 *   Alex                macOS — alternative
 *   Microsoft Zira      Windows 10/11
 *   Microsoft Aria      Windows 11
 *   première voix en-US disponible en repli
 *
 * Principe D : le code dépend de ISpeechSynthesizer, jamais de
 * window.speechSynthesis directement.
 *
 * Principe O : ajouter un synthétiseur cloud = nouvelle classe,
 * zéro modification du code appelant.
 */
import type { SynthRequest } from "./types";

export interface ISpeechSynthesizer {
  speak(req: SynthRequest): Promise<void>;
  cancel(): void;
  isAvailable(): boolean;
}

// ── Sélection de voix ─────────────────────────────────────────────────────────

const PREFERRED_VOICES = [
  "Google US English",
  "Samantha",
  "Alex",
  "Microsoft Aria Online (Natural) - English (United States)",
  "Microsoft Zira Desktop - English (United States)",
  "Microsoft David Desktop - English (United States)",
];

function pickEnglishVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  for (const name of PREFERRED_VOICES) {
    const v = voices.find((v) => v.name.includes(name));
    if (v) return v;
  }
  return (
    voices.find((v) => v.lang === "en-US") ??
    voices.find((v) => v.lang.startsWith("en")) ??
    null
  );
}

// ── BrowserSynthesizer ────────────────────────────────────────────────────────

export class BrowserSynthesizer implements ISpeechSynthesizer {
  isAvailable(): boolean {
    return "speechSynthesis" in window;
  }

  cancel(): void {
    window.speechSynthesis.cancel();
  }

  speak({ text, priority }: SynthRequest): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.isAvailable()) { resolve(); return; }
      if (priority === "high") window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang  = "en-US";
      utterance.rate  = 1.0;
      utterance.pitch = 1.0;

      // Les voix chargent de façon asynchrone — on tente d'en obtenir une.
      const voice = pickEnglishVoice();
      if (voice) utterance.voice = voice;

      // Workaround Chrome : la synthèse se coupe après ~15 s. On la relance.
      const keepAlive = setInterval(() => {
        if (window.speechSynthesis.paused) window.speechSynthesis.resume();
      }, 5_000);

      utterance.onend = () => { clearInterval(keepAlive); resolve(); };
      utterance.onerror = (e) => {
        clearInterval(keepAlive);
        if (e.error === "interrupted" || e.error === "canceled") resolve();
        else reject(new Error(e.error));
      };

      window.speechSynthesis.speak(utterance);
    });
  }
}

// ── PiperSynthesizer (conteneur Docker) ──────────────────────────────────────

export class PiperSynthesizer implements ISpeechSynthesizer {
  private readonly fallback = new BrowserSynthesizer();

  isAvailable(): boolean { return true; }
  cancel(): void { this.fallback.cancel(); }

  async speak(req: SynthRequest): Promise<void> {
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: req.text, voice: "en_US-ljspeech-medium" }),
      });
      if (!res.ok) throw new Error(`TTS API: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      await new Promise<void>((resolve, reject) => {
        const audio = new Audio(url);
        audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
        audio.onerror = () => { URL.revokeObjectURL(url); reject(new Error("audio")); };
        void audio.play();
      });
    } catch {
      await this.fallback.speak(req);
    }
  }
}

// ── Fabrique ──────────────────────────────────────────────────────────────────

export function createSynthesizer(
  networkStatus: "online" | "offline",
): ISpeechSynthesizer {
  if (networkStatus === "online") return new PiperSynthesizer();
  return new BrowserSynthesizer();
}
