/**
 * Hook React qui gère l'état de l'animation de survol.
 *
 * Principe S (Single Responsibility) : ce hook ne gère que l'état de
 * l'animation (joue/pause, progression, vitesse). Le calcul de la caméra
 * et les effets de bord de rendu sont délégués à leurs propres modules.
 *
 * Il utilise `requestAnimationFrame` via `useEffect` pour avancer la
 * progression au fil du temps, et met à jour `hoverDistanceM` dans le
 * magasin partagé pour synchroniser le profil 2D de F3.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useShared } from "@/shared/store";
import {
  advanceFlyover,
  computeCamera,
  EXAGGERATION_STEPS,
  SPEED_STEPS,
  type CameraTarget,
  type ExaggerationFactor,
  type FlyoverSpeed,
  type RouteProfile,
} from "./flyover";

export interface FlyoverControls {
  /** État courant de la caméra (longitude, latitude, altitude, bearing, pitch). */
  camera: CameraTarget | null;
  /** Exagération verticale courante. */
  exaggeration: ExaggerationFactor;
  /** Vitesse courante du survol. */
  speed: FlyoverSpeed;
  /** L'animation est-elle en cours ? */
  playing: boolean;
  /** Distance parcourue en mètres. */
  progressM: number;
  /** Démarrer ou reprendre le survol. */
  play: () => void;
  /** Mettre en pause. */
  pause: () => void;
  /** Rembobiner au début. */
  rewind: () => void;
  /** Aller à une distance le long du tracé (curseur). */
  seek: (m: number) => void;
  /** Changer l'exagération verticale. */
  setExaggeration: (v: ExaggerationFactor) => void;
  /** Changer la vitesse. */
  setSpeed: (v: FlyoverSpeed) => void;
}

export function useFlyover(
  profile: RouteProfile[],
  totalDistanceM: number,
): FlyoverControls {
  const setHoverDistance = useShared((s) => s.setHoverDistance);

  const [playing, setPlaying] = useState(false);
  const [progressM, setProgressM] = useState(0);
  const [exaggeration, setExaggeration] = useState<ExaggerationFactor>(
    EXAGGERATION_STEPS[1],
  );
  const [speed, setSpeed] = useState<FlyoverSpeed>(SPEED_STEPS[1]);

  // Référence pour la boucle d'animation (ne déclenche pas de re-render)
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);
  const progressRef = useRef(progressM);
  progressRef.current = progressM;

  // Synchronise le repère de profil F3 quand la progression change
  useEffect(() => {
    setHoverDistance(progressM > 0 ? progressM : null);
    return () => setHoverDistance(null);
  }, [progressM, setHoverDistance]);

  // Boucle d'animation via requestAnimationFrame
  useEffect(() => {
    if (!playing || profile.length === 0 || totalDistanceM === 0) return;

    function tick(timestamp: number) {
      const deltaMs =
        lastTimeRef.current !== null ? timestamp - lastTimeRef.current : 16;
      lastTimeRef.current = timestamp;

      const next = advanceFlyover(
        progressRef.current,
        totalDistanceM,
        speed,
        deltaMs,
      );

      if (next === null) {
        // Survol terminé
        setProgressM(totalDistanceM);
        setPlaying(false);
        lastTimeRef.current = null;
        return;
      }

      setProgressM(next);
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTimeRef.current = null;
    };
  }, [playing, profile, totalDistanceM, speed]);

  // Réinitialiser quand l'itinéraire change
  useEffect(() => {
    setProgressM(0);
    setPlaying(false);
  }, [profile]);

  const play = useCallback(() => {
    // Si on est à la fin, rembobiner d'abord
    if (progressRef.current >= totalDistanceM && totalDistanceM > 0) {
      setProgressM(0);
    }
    setPlaying(true);
  }, [totalDistanceM]);

  const pause = useCallback(() => setPlaying(false), []);

  const rewind = useCallback(() => {
    setPlaying(false);
    setProgressM(0);
  }, []);

  const seek = useCallback(
    (m: number) => setProgressM(Math.max(0, Math.min(totalDistanceM, m))),
    [totalDistanceM],
  );

  // Calculer la position de caméra courante (pur, pas d'effet de bord)
  const camera: CameraTarget | null =
    profile.length > 0
      ? computeCamera(profile, progressM, exaggeration)
      : null;

  return {
    camera,
    exaggeration,
    speed,
    playing,
    progressM,
    play,
    pause,
    rewind,
    seek,
    setExaggeration,
    setSpeed,
  };
}
