/**
 * Contrats internes de la feature vocale (V1).
 *
 * Principe I (Interface Segregation) : chaque consommateur reçoit
 * uniquement le type dont il a besoin.
 */

// ── Commandes reconnues ───────────────────────────────────────────────────────

/** Commande parsée depuis la transcription. */
export type VoiceCommand =
  | { kind: "addTarget" }
  | { kind: "selectVariant"; variant: "safest" | "fastest" | "science" }
  | { kind: "queryPoint" }
  | { kind: "startFlyover" }
  | { kind: "returnToHabitat" }
  | { kind: "acknowledgeAlert" }
  | { kind: "pauseFlyover" }
  | { kind: "setFlyoverSpeed"; speed: 0.5 | 1 | 2 | 5 }
  | { kind: "toggleLayer"; layerId: string }
  | { kind: "unknown"; transcript: string };

// ── État de la reconnaissance ─────────────────────────────────────────────────

/** État observable du micro. */
export type RecognitionState =
  | "unsupported"  // Web Speech API absente
  | "idle"         // micro éteint
  | "listening"    // écoute en cours
  | "processing"   // résultat final reçu, traitement de la commande
  | "error";       // erreur de reconnaissance

// ── File de synthèse ──────────────────────────────────────────────────────────

/** Requête de synthèse vocale. */
export interface SynthRequest {
  text: string;
  /** `high` interrompt la synthèse en cours (alertes danger). */
  priority: "low" | "high";
}
