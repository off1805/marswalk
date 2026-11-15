/**
 * Contrats internes de la feature hors ligne (F7).
 *
 * Principe I (Interface Segregation) : chaque consommateur reçoit
 * uniquement l'interface dont il a besoin.
 *
 * Principe O (Open/Closed) : ajouter un type d'opération en file
 * revient à étendre `QueuedOperation` — le moteur de file ne change pas.
 */

// ── État du service worker ────────────────────────────────────────────────────

/** État observable du service worker Workbox. */
export type SwStatus =
  | "unsupported"  // navigator.serviceWorker absent
  | "pending"      // enregistrement en cours
  | "active"       // service worker actif et contrôlant la page
  | "waiting"      // nouvelle version en attente d'activation
  | "error";       // enregistrement échoué

// ── Connexion ─────────────────────────────────────────────────────────────────

/** État de la connectivité réseau. */
export type NetworkStatus = "online" | "offline";

// ── Préchargement ─────────────────────────────────────────────────────────────

/** Progression du préchargement du paquet de site. */
export interface PrefetchProgress {
  /** Nombre de ressources téléchargées. */
  done: number;
  /** Nombre total de ressources à télécharger. */
  total: number;
  /** Vrai pendant le téléchargement. */
  running: boolean;
  /** Erreur éventuelle. */
  error: string | null;
}

/** Ressource à précharger. */
export interface PrefetchResource {
  /** URL de la ressource. */
  url: string;
  /** Taille indicative en octets (0 si inconnue). */
  bytes: number;
}

// ── File d'attente des opérations hors ligne ──────────────────────────────────

/** Opération mise en file pendant une coupure réseau. */
export interface QueuedOperation {
  /** Identifiant unique de l'opération. */
  id: string;
  /** Type de l'opération. */
  kind: "createTarget" | "updateTarget" | "deleteTarget" | "addObservation";
  /** Horodatage de mise en file (ms depuis epoch). */
  enqueuedAt: number;
  /** Corps de la requête sérialisé. */
  payload: unknown;
  /** Nombre de tentatives déjà effectuées. */
  attempts: number;
}

/** Résultat d'une tentative de rejeu d'opération. */
export type ReplayResult =
  | { kind: "success"; operationId: string }
  | { kind: "failure"; operationId: string; reason: string };
