/**
 * Composant de rendu bas niveau : un canvas deck.gl avec TerrainLayer.
 *
 * Principe S (Single Responsibility) : ce composant ne fait que rendre
 * le terrain 3D. Il ne connaît pas l'animation, les contrôles ni le
 * magasin partagé.
 *
 * Principe D (Dependency Inversion) : il reçoit `TerrainConfig` et
 * `CameraTarget` comme props — deux abstractions, pas les types deck.gl.
 *
 * Implémentation : deck.gl 9 n'a pas de binding React `DeckGL`. On utilise
 * l'API impérative `Deck` depuis `@deck.gl/core`, montée via `useEffect`.
 */
import { useEffect, useRef } from "react";
import { Deck, type MapViewState } from "@deck.gl/core";
import { TerrainLayer } from "@deck.gl/geo-layers";
import type { CameraTarget } from "./flyover";
import type { TerrainConfig } from "./terrain.config";
import type { Route } from "@/shared/api/client";
import { buildRouteLayer } from "./routeLayer";

interface Props {
  config: TerrainConfig;
  camera: CameraTarget | null;
  exaggeration: number;
  activeRoute: Route | null;
  /** Appelé quand l'utilisateur fait glisser manuellement la caméra. */
  onViewStateChange?: (longitude: number, latitude: number) => void;
}

/** Zoom WebMercator approximatif pour une vue à une altitude donnée. */
function altitudeToZoom(altitudeM: number): number {
  return Math.max(10, Math.min(18, 16 - Math.log2(Math.max(1, altitudeM) / 100)));
}

function buildViewState(
  config: TerrainConfig,
  camera: CameraTarget | null,
): MapViewState {
  if (camera) {
    return {
      longitude: camera.longitude,
      latitude: camera.latitude,
      zoom: altitudeToZoom(camera.altitude),
      bearing: camera.bearing,
      pitch: camera.pitch,
    };
  }
  return {
    longitude: (config.bbox[0] + config.bbox[2]) / 2,
    latitude: (config.bbox[1] + config.bbox[3]) / 2,
    zoom: 13,
    bearing: 0,
    pitch: 50,
  };
}

export function TerrainCanvas({
  config,
  camera,
  exaggeration,
  activeRoute,
  onViewStateChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<Deck | null>(null);

  // Montage de l'instance Deck (une seule fois)
  useEffect(() => {
    if (!containerRef.current) return;

    const deck = new Deck({
      canvas: (() => {
        const canvas = document.createElement("canvas");
        // Position absolue pour remplir le conteneur sans contribuer au flux
        // et provoquer un scroll involontaire.
        canvas.style.position = "absolute";
        canvas.style.inset = "0";
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        containerRef.current!.appendChild(canvas);
        return canvas;
      })(),
      initialViewState: buildViewState(config, null),
      controller: true,
      onViewStateChange: ({ viewState }) => {
        onViewStateChange?.(
          (viewState as { longitude: number; latitude: number }).longitude,
          (viewState as { longitude: number; latitude: number }).latitude,
        );
      },
      layers: [],
    });

    deckRef.current = deck;

    return () => {
      deck.finalize();
      deckRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mise à jour des couches et de la vue à chaque changement de props
  useEffect(() => {
    const deck = deckRef.current;
    if (!deck) return;

    // Décodeur avec exagération verticale appliquée aux scalers (l'offset reste fixe)
    const exaggeratedDecoder = {
      rScaler: config.elevationDecoder.rScaler * exaggeration,
      gScaler: config.elevationDecoder.gScaler * exaggeration,
      bScaler: config.elevationDecoder.bScaler * exaggeration,
      offset: config.elevationDecoder.offset,
    };

    const terrainLayer = new TerrainLayer({
      id: "f6-terrain",
      elevationData: config.elevationUrlTemplate,
      texture: config.textureUrlTemplate,
      elevationDecoder: exaggeratedDecoder,
      meshMaxError: config.meshMaxError,
    });

    const routeLayer = activeRoute ? buildRouteLayer(activeRoute) : null;
    const layers = routeLayer ? [terrainLayer, routeLayer] : [terrainLayer];

    deck.setProps({ layers });

    if (camera) {
      deck.setProps({ viewState: buildViewState(config, camera) });
    }
  }, [config, camera, exaggeration, activeRoute]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0"
      role="img"
      aria-label="Rendu 3D du terrain martien"
      data-testid="terrain-canvas"
    />
  );
}
