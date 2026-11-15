/**
 * Parseur de commandes vocales — anglais (en-US).
 *
 * Principe S : convertir un texte transcrit en VoiceCommand est la seule
 * responsabilité de ce module. Aucun effet de bord.
 *
 * Principe O : ajouter une commande = ajouter une entrée dans PATTERNS.
 *
 * Chaque action dispose de nombreuses variantes pour couvrir les formulations
 * naturelles, les abréviations et les légères erreurs de reconnaissance.
 */
import type { VoiceCommand } from "./types";

// ── Mot de réveil ─────────────────────────────────────────────────────────────

export const WAKE_WORD = "Nebula";
const WAKE_WORD_RE = /\bne[bv]ula\b/i;

/** Détecte le mot de réveil dans une transcription. */
export function containsWakeWord(text: string): boolean {
  return WAKE_WORD_RE.test(text);
}

/**
 * Réponses aléatoires de Nebula après le réveil.
 * Courtes, naturelles, variées — pour une communication fluide.
 */
export const WAKE_RESPONSES = [
  "How can I help you?",
  "Ready to serve.",
  "I'm listening.",
  "Yes, go ahead.",
  "At your command.",
  "Online and ready.",
  "What do you need?",
  "Standing by.",
  "Nebula here, what's up?",
  "Mission control, go ahead.",
  "Awaiting your orders.",
  "All systems go.",
] as const;

export function randomWakeResponse(): string {
  const idx = Math.floor(Math.random() * WAKE_RESPONSES.length);
  return WAKE_RESPONSES[idx]!;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Préfixe commun aux commandes de sélection/choix. */
const SELECT_PREFIX =
  /(?:select|choose|take|use|apply|go\s+with|switch\s+to|activate|set|pick|i\s+want)\s+(?:the\s+)?/i.source;

/** Suffixe optionnel désignant l'itinéraire. */
const ROUTE_SUFFIX =
  /(?:\s+(?:route|path|variant|option|way))?/.source;

// ── Patterns ──────────────────────────────────────────────────────────────────

interface Pattern {
  re: RegExp;
  toCommand: (m: RegExpMatchArray) => VoiceCommand;
}

const PATTERNS: Pattern[] = [

  // ═══════════════════════════════════════════════════════════════════════════
  // ADD TARGET
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /(?:add|place|drop|mark|create|set|put|insert)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:target|waypoint|marker|pin|point(?:\s+of\s+interest)?|poi|stop)/i,
    toCommand: () => ({ kind: "addTarget" }),
  },
  {
    re: /new\s+(?:target|waypoint|marker|pin|point)/i,
    toCommand: () => ({ kind: "addTarget" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // VARIANT — SAFEST
  // ═══════════════════════════════════════════════════════════════════════════
  {
    // "select/choose the safest/safe/secure/cautious/conservative route/path/variant"
    re: new RegExp(
      SELECT_PREFIX +
      "(?:safest?|most\\s+secure|safety|cautious|conservative|careful|secure)" +
      ROUTE_SUFFIX,
      "i",
    ),
    toCommand: () => ({ kind: "selectVariant", variant: "safest" }),
  },
  {
    // "choose the safe route" — "safe" seul suivi obligatoirement d'un mot de chemin
    re: /(?:select|choose|take|use|apply|go\s+with|switch\s+to|activate|set|pick)\s+(?:the\s+)?safe\s+(?:route|path|variant|option|way)/i,
    toCommand: () => ({ kind: "selectVariant", variant: "safest" }),
  },
  {
    // route/path safest / route safest
    re: /(?:route|path|variant|option|way)\s+(?:number\s+)?(?:one|1\s+)?(?:safest?|safe|secure|cautious)/i,
    toCommand: () => ({ kind: "selectVariant", variant: "safest" }),
  },
  {
    // short: "safest", "safest route", "safety route", "most secure"
    re: /\b(?:safest|most\s+secure|safety\s+(?:route|path))\b/i,
    toCommand: () => ({ kind: "selectVariant", variant: "safest" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // VARIANT — FASTEST
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: new RegExp(
      SELECT_PREFIX +
      "(?:fastest?|quickest?|most\\s+direct|shortest|direct|rapid)" +
      ROUTE_SUFFIX,
      "i",
    ),
    toCommand: () => ({ kind: "selectVariant", variant: "fastest" }),
  },
  {
    re: /(?:route|path|variant|option|way)\s+(?:number\s+)?(?:two|2\s+)?(?:fastest?|quick|direct|short(?:est)?)/i,
    toCommand: () => ({ kind: "selectVariant", variant: "fastest" }),
  },
  {
    re: /\b(?:fastest|quickest|most\s+direct|shortest\s+(?:route|path))\b/i,
    toCommand: () => ({ kind: "selectVariant", variant: "fastest" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // VARIANT — SCIENCE
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: new RegExp(
      SELECT_PREFIX +
      "(?:science|scientific|research|exploration|sample)" +
      ROUTE_SUFFIX,
      "i",
    ),
    toCommand: () => ({ kind: "selectVariant", variant: "science" }),
  },
  {
    re: /(?:route|path|variant|option|way)\s+(?:number\s+)?(?:three|3\s+)?(?:science|scientific|research|exploration)/i,
    toCommand: () => ({ kind: "selectVariant", variant: "science" }),
  },
  {
    re: /\b(?:science|scientific)\s+(?:route|path|variant)\b/i,
    toCommand: () => ({ kind: "selectVariant", variant: "science" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // QUERY POINT
  // ═══════════════════════════════════════════════════════════════════════════
  {
    // query / analyze / scan / check / inspect this point/location/spot
    re: /\b(?:query|analyze|scan|check|inspect|sample|probe|read|tell\s+me)\b(?:\s+(?:this|the)\s+)?(?:point|location|spot|position|area|data|info)?/i,
    toCommand: () => ({ kind: "queryPoint" }),
  },
  {
    // "what is/what's the slope/altitude/elevation/value/terrain here"
    re: /\bwhat(?:'s|\s+is)\b.*?\b(?:slope|altitude|elevation|terrain|value|data|reading)\b/i,
    toCommand: () => ({ kind: "queryPoint" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // PAUSE FLYOVER  (doit précéder startFlyover — fly*over matche les deux)
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /\b(?:pause|stop|halt|freeze|hold)\b\s+(?:(?:the|this)\s+)?(?:flyover|fly\s*over|animation|camera|flight)\b/i,
    toCommand: () => ({ kind: "pauseFlyover" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESUME FLYOVER  (doit précéder startFlyover)
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /\b(?:resume|continue|restart|unpause|play)\b\s+(?:(?:the|this)\s+)?(?:flyover|fly\s*over|animation|camera|flight)\b/i,
    toCommand: () => ({ kind: "resumeFlyover" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // START FLYOVER
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /(?:start|launch|begin|open|show|go\s+to|activate|enter|switch\s+to|view|display|enable)\s+(?:the\s+)?(?:3[dD](?:\s+view)?|flyover|fly\s*over|terrain\s+view|three[\s-]d(?:\s+view)?|aerial(?:\s+view)?)/i,
    toCommand: () => ({ kind: "startFlyover" }),
  },
  {
    re: /\b(?:fly\s*over|aerial\s+(?:view|mode)|3[dD]\s+mode)\b/i,
    toCommand: () => ({ kind: "startFlyover" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // FLYOVER SPEED
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /(?:speed\s+(?:up\s+)?(?:to|at)?|set\s+(?:the\s+)?speed(?:\s+to)?|fly\s+at|times?|[x×])\s*([0-9]+(?:[.,][0-9]+)?)/i,
    toCommand: (m) => {
      const raw = parseFloat(m[1]!.replace(",", "."));
      const allowed = [0.5, 1, 2, 5] as const;
      const speed = allowed.reduce((p, c) =>
        Math.abs(c - raw) < Math.abs(p - raw) ? c : p,
      ) as 0.5 | 1 | 2 | 5;
      return { kind: "setFlyoverSpeed", speed };
    },
  },
  {
    re: /(?:speed|fly|go)\s+(slow(?:ly)?|normal(?:ly)?|fast(?:er)?|very\s+fast|half\s+speed|double\s+speed)/i,
    toCommand: (m) => {
      const v = m[1]!.toLowerCase();
      const speed =
        v.includes("very") || v.includes("double") ? 5
        : v.includes("fast") ? 2
        : v.includes("slow") || v.includes("half") ? 0.5
        : 1;
      return { kind: "setFlyoverSpeed", speed: speed as 0.5 | 1 | 2 | 5 };
    },
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RETURN TO HABITAT — EMERGENCY
  // ═══════════════════════════════════════════════════════════════════════════
  {
    // "return to habitat/base/home/shelter" etc.
    re: /(?:return(?:\s+to)?|head\s+back(?:\s+to)?|go\s+back(?:\s+to)?|navigate(?:\s+back)?\s+to)\s+(?:the\s+)?(?:habitat|base|home|shelter|camp|station|hub)/i,
    toCommand: () => ({ kind: "returnToHabitat" }),
  },
  {
    // "abort mission" / "emergency return" / "emergency abort"
    re: /\b(?:abort(?:\s+mission)?|emergency\s+(?:return|abort|evacuation)|mayday|rtb)\b/i,
    toCommand: () => ({ kind: "returnToHabitat" }),
  },
  {
    // ultra-short standalone forms
    re: /^(?:abort|go\s+home|head\s+back|r\.?t\.?b\.?|emergency)\s*[.!]?\s*$/i,
    toCommand: () => ({ kind: "returnToHabitat" }),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // ACKNOWLEDGE ALERT
  // ═══════════════════════════════════════════════════════════════════════════
  {
    re: /\b(?:acknowledge|confirm|dismiss|clear|close|silence|mute)\b(?:\s+(?:the|this|all)\s+)?(?:alert|warning|notification|alarm)s?/i,
    toCommand: () => ({ kind: "acknowledgeAlert" }),
  },
  {
    // "got it", "copy that", "understood", "roger", "affirmative"
    re: /^(?:got\s+it|copy(?:\s+that)?|understood|roger(?:\s+that)?|affirmative|10-?4)\s*[.!]?\s*$/i,
    toCommand: () => ({ kind: "acknowledgeAlert" }),
  },
];

// ── Fonctions publiques ───────────────────────────────────────────────────────

export function parseCommand(transcript: string): VoiceCommand {
  const text = transcript.trim();
  for (const { re, toCommand } of PATTERNS) {
    const m = text.match(re);
    if (m) return toCommand(m);
  }
  return { kind: "unknown", transcript: text };
}

export function looksLikeCommand(partial: string): boolean {
  const keywords = [
    "add", "place", "drop", "mark", "create",
    "select", "choose", "take", "safest", "fastest", "science",
    "query", "analyze", "scan", "what is", "what's",
    "flyover", "3d", "fly over", "aerial",
    "pause", "resume", "stop", "speed",
    "return", "abort", "go home", "head back", "mayday", "rtb",
    "acknowledge", "dismiss", "confirm", "got it", "copy",
  ];
  const lower = partial.toLowerCase();
  return keywords.some((k) => lower.includes(k));
}
