/**
 * Logique d'animation du survol de l'itinéraire (caméra qui suit le tracé).
 *
 * Principe S (Single Responsibility) : ce module ne fait qu'une chose —
 * calculer l'état de la caméra à chaque instant du survol. Il ne sait rien
 * du rendu ni de React.
 *
 * Principe D (Dependency Inversion) : il opère sur des types géométriques
 * simples (`LonLat`, `RouteProfile`) sans dépendre de deck.gl ou de l'API.
 */

import type { LonLat } from "@/shared/api/client";

/** Un échantillon de position le long de l'itinéraire. */
export interface RouteProfile {
  /** Distance cumulée depuis le départ, en mètres. */
  distanceM: number;
  /** Position géographique [lon, lat] en degrés. */
  position: LonLat;
  /** Altitude en mètres (peut être nulle si le MNT est absent). */
  elevationM: number | null;
}

/** Facteurs d'exagération verticale disponibles. */
export const EXAGGERATION_STEPS = [1, 2, 3, 5, 10] as const;
export type ExaggerationFactor = (typeof EXAGGERATION_STEPS)[number];

/** Vitesses de survol (facteur temps). */
export const SPEED_STEPS = [0.5, 1, 2, 5, 10, 20] as const;
export type FlyoverSpeed = (typeof SPEED_STEPS)[number];

/** État de l'animation de survol. */
export interface FlyoverState {
  /** L'animation est-elle en cours ? */
  playing: boolean;
  /** Distance parcourue le long du tracé, en mètres. */
  progressM: number;
  /** Vitesse courante. */
  speed: FlyoverSpeed;
}

/** Position et orientation de la caméra calculées à partir de l'état. */
export interface CameraTarget {
  longitude: number;
  latitude: number;
  /** Altitude de la caméra, en mètres au-dessus du terrain. */
  altitude: number;
  /** Cap de la caméra en degrés depuis le nord. */
  bearing: number;
  /** Inclinaison de la caméra (0 = nadir, 90 = horizon). */
  pitch: number;
}

const CAMERA_HEIGHT_M = 80;
const CAMERA_PITCH = 60;
const LOOKAHEAD_M = 40;

/**
 * Interpole linéairement entre deux valeurs.
 * Fonction pure — aucun effet de bord.
 */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Trouve l'échantillon de profil correspondant à une distance donnée,
 * et interpole la position entre les deux échantillons encadrants.
 *
 * Complexité O(log n) si le profil est trié par distance (ce qui est garanti
 * par le serveur). Ici on fait une recherche linéaire simple car les profils
 * ont au plus quelques milliers de points.
 */
export function sampleProfile(
  profile: RouteProfile[],
  distanceM: number,
): { position: LonLat; elevationM: number } {
  if (profile.length === 0) {
    return { position: [0, 0], elevationM: 0 };
  }
  if (distanceM <= profile[0]!.distanceM) {
    return {
      position: profile[0]!.position,
      elevationM: profile[0]!.elevationM ?? 0,
    };
  }
  const last = profile[profile.length - 1]!;
  if (distanceM >= last.distanceM) {
    return { position: last.position, elevationM: last.elevationM ?? 0 };
  }

  // Trouver les deux échantillons encadrants
  for (let i = 0; i < profile.length - 1; i++) {
    const a = profile[i]!;
    const b = profile[i + 1]!;
    if (distanceM >= a.distanceM && distanceM <= b.distanceM) {
      const range = b.distanceM - a.distanceM;
      const t = range > 0 ? (distanceM - a.distanceM) / range : 0;
      return {
        position: [
          lerp(a.position[0], b.position[0], t),
          lerp(a.position[1], b.position[1], t),
        ],
        elevationM: lerp(a.elevationM ?? 0, b.elevationM ?? 0, t),
      };
    }
  }

  return { position: last.position, elevationM: last.elevationM ?? 0 };
}

/**
 * Calcule l'état de caméra pour un instant du survol.
 *
 * La caméra est positionnée `CAMERA_HEIGHT_M` mètres au-dessus du terrain,
 * inclinée vers l'avant (`CAMERA_PITCH` degrés) et orientée vers le point
 * situé `LOOKAHEAD_M` mètres plus loin sur le tracé.
 */
export function computeCamera(
  profile: RouteProfile[],
  progressM: number,
  exaggeration: ExaggerationFactor,
): CameraTarget {
  const { position, elevationM } = sampleProfile(profile, progressM);
  const ahead = sampleProfile(profile, progressM + LOOKAHEAD_M);

  const dLon = ahead.position[0] - position[0];
  const dLat = ahead.position[1] - position[1];
  const bearing =
    dLon === 0 && dLat === 0
      ? 0
      : (Math.atan2(dLon, dLat) * 180) / Math.PI;

  return {
    longitude: position[0],
    latitude: position[1],
    altitude: (elevationM * exaggeration) + CAMERA_HEIGHT_M,
    bearing: (bearing + 360) % 360,
    pitch: CAMERA_PITCH,
  };
}

/**
 * Avance la progression de l'animation d'un pas de temps.
 *
 * Retourne la nouvelle progression en mètres, bornée à la longueur totale.
 * Renvoie `null` si le survol est terminé.
 */
export function advanceFlyover(
  progressM: number,
  totalM: number,
  speed: FlyoverSpeed,
  deltaMs: number,
): number | null {
  // On avance à ~20 m/s à vitesse ×1 (compromis entre fluide et lisible)
  const BASE_SPEED_MPS = 20;
  const newProgress = progressM + BASE_SPEED_MPS * speed * (deltaMs / 1000);
  return newProgress >= totalM ? null : newProgress;
}
