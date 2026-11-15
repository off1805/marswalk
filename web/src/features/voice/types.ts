/**
 * Contrats internes de la feature vocale (V1).
 *
 * Principe I : chaque consommateur reçoit uniquement ce dont il a besoin.
 */

// ── Commandes reconnues ───────────────────────────────────────────────────────

export type VoiceCommand =
  | { kind: "addTarget" }
  | { kind: "selectVariant"; variant: "safest" | "fastest" | "science" }
  | { kind: "queryPoint" }
  | { kind: "startFlyover" }
  | { kind: "pauseFlyover" }
  | { kind: "resumeFlyover" }
  | { kind: "setFlyoverSpeed"; speed: 0.5 | 1 | 2 | 5 }
  | { kind: "returnToHabitat" }
  | { kind: "acknowledgeAlert" }
  | { kind: "toggleLayer"; layerId: string }
  | { kind: "unknown"; transcript: string };

// ── État de la reconnaissance ─────────────────────────────────────────────────

/**
 * idle      — micro éteint
 * wakeWord  — écoute passive du mot de réveil « Nebula »
 * listening — écoute active d'une commande (après réveil)
 * processing — commande reçue, traitement en cours
 * error     — erreur de reconnaissance
 * unsupported — Web Speech API absente
 */
export type RecognitionState =
  | "unsupported"
  | "idle"
  | "wakeWord"
  | "listening"
  | "processing"
  | "error";

// ── Synthèse ──────────────────────────────────────────────────────────────────

export interface SynthRequest {
  /** Texte en anglais à lire. */
  text: string;
  /** `high` interrompt la synthèse en cours (alertes danger). */
  priority: "low" | "high";
}
