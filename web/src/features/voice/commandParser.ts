/**
 * Parseur de commandes vocales.
 *
 * Principe S (Single Responsibility) : convertir un texte transcrit en
 * `VoiceCommand` est la seule responsabilité de ce module. Aucun effet de
 * bord, entièrement testable sans navigateur.
 *
 * Principe O (Open/Closed) : ajouter une commande = ajouter une entrée dans
 * `PATTERNS`. Le moteur d'exécution (`useVoiceCommands`) ne change pas.
 */
import type { VoiceCommand } from "./types";

interface Pattern {
  re: RegExp;
  toCommand: (m: RegExpMatchArray) => VoiceCommand;
}

const PATTERNS: Pattern[] = [
  // ── Cibles ───────────────────────────────────────────────────────────────
  {
    re: /ajoute?r?\s+(?:une?\s+)?cible/i,
    toCommand: () => ({ kind: "addTarget" }),
  },

  // ── Variantes ─────────────────────────────────────────────────────────────
  {
    re: /(?:choisis?|sélectionne?|prends?|utilise?)\s+(?:la\s+)?variante?\s+(?:la\s+)?(plus\s+s[uû]re?|plus\s+rapide|science)/i,
    toCommand: (m) => {
      const v = m[1]!.toLowerCase().replace(/\s+/g, " ");
      const variant =
        v.includes("s") && v.includes("re") ? "safest"
        : v.includes("rapide") ? "fastest"
        : "science";
      return { kind: "selectVariant", variant };
    },
  },
  {
    re: /(?:la\s+)?variante?\s+(s[uû]re?|rapide|science)/i,
    toCommand: (m) => {
      const v = m[1]!.toLowerCase();
      // Tester "science" d'abord car "sûre" commence aussi par "s"
      const variant =
        v === "science" ? "science"
        : v.startsWith("s") ? "safest"
        : "fastest";
      return { kind: "selectVariant", variant };
    },
  },

  // ── Interrogation ─────────────────────────────────────────────────────────
  {
    re: /(?:interroge?|qu(?:elle\s+est\s+la|'est.{0,5}la)\s+(?:valeur|pente|altitude))/i,
    toCommand: () => ({ kind: "queryPoint" }),
  },

  // ── Survol 3D ─────────────────────────────────────────────────────────────
  {
    re: /(?:lance|démarre?|commence)\s+(?:le\s+)?survol/i,
    toCommand: () => ({ kind: "startFlyover" }),
  },
  {
    re: /(?:pause|stop|arrête?)\s+(?:le\s+)?survol/i,
    toCommand: () => ({ kind: "pauseFlyover" }),
  },
  {
    re: /(?:vitesse|accélère?|ralentis?)\s+(?:à\s+|fois\s+)?([0-9]+(?:[.,][0-9]+)?)/i,
    toCommand: (m) => {
      const raw = parseFloat(m[1]!.replace(",", "."));
      const allowed = [0.5, 1, 2, 5] as const;
      const speed = (allowed.reduce((prev, curr) =>
        Math.abs(curr - raw) < Math.abs(prev - raw) ? curr : prev,
      ) as 0.5 | 1 | 2 | 5);
      return { kind: "setFlyoverSpeed", speed };
    },
  },

  // ── Urgences ──────────────────────────────────────────────────────────────
  {
    re: /retour\s+(?:à\s+)?(?:l[ae]?\s*['']?\s*)?(?:habitat|base|maison|abri)/i,
    toCommand: () => ({ kind: "returnToHabitat" }),
  },
  {
    re: /acquitte?(?:ment|r)?\s+(?:l['']?alerte|toutes?)/i,
    toCommand: () => ({ kind: "acknowledgeAlert" }),
  },
];

/**
 * Traduit une transcription en commande structurée.
 *
 * @param transcript  Texte brut renvoyé par la Web Speech API.
 * @returns           La commande reconnue, ou `{ kind: "unknown" }`.
 */
export function parseCommand(transcript: string): VoiceCommand {
  const text = transcript.trim();
  for (const { re, toCommand } of PATTERNS) {
    const m = text.match(re);
    if (m) return toCommand(m);
  }
  return { kind: "unknown", transcript: text };
}

/**
 * Retourne vrai si la transcription partielle ressemble à une commande connue.
 * Utilisé pour afficher l'état "traitement en cours" sans attendre le résultat final.
 */
export function looksLikeCommand(partial: string): boolean {
  const keywords = [
    "ajoute", "choisis", "sélectionne", "variante", "retour",
    "acquitte", "survol", "pause", "vitesse", "interroge",
  ];
  const lower = partial.toLowerCase();
  return keywords.some((k) => lower.includes(k));
}
