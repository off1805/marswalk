/**
 * Configuration du décodage des tuiles terrain-RGB en altitude (mètres).
 *
 * Principe O (Open/Closed) : ajouter un nouveau format d'encodage revient à
 * créer une nouvelle `ElevationDecoder` sans toucher au code de rendu.
 *
 * L'encodage terrain-RGB de Marswalk suit la convention Mapbox :
 *   altitude_m = -10 000 + (R × 256² + G × 256 + B) × 0,1
 *
 * Les coordonnées sont en degrés planétocentriques Mars 2000 (règle R2).
 * Le pseudo-Mercator WebMercatorQuad s'applique aux longitudes/latitudes
 * martiennes — identique à la carte 2D (règle R3).
 */

/** Paramètres de décodage d'un pixel RGB en altitude (mètres). */
export interface ElevationDecoder {
  rScaler: number;
  gScaler: number;
  bScaler: number;
  offset: number;
}

/** Décodeur pour le format terrain-RGB de Marswalk (convention Mapbox). */
export const MARSWALK_ELEVATION_DECODER: ElevationDecoder = {
  rScaler: 6553.6,
  gScaler: 25.6,
  bScaler: 0.1,
  offset: -10_000,
};

/** Paramètres de la TerrainLayer, injectables et testables séparément. */
export interface TerrainConfig {
  /** Gabarit d'URL des tuiles terrain-RGB, avec {x}, {y}, {z}. */
  elevationUrlTemplate: string;
  /** Gabarit d'URL des tuiles d'imagerie de surface (texture). */
  textureUrlTemplate: string;
  /** Tolérance d'erreur Martini en mètres — plus petit = maillage plus fin. */
  meshMaxError: number;
  /** Décodeur d'altitude. */
  elevationDecoder: ElevationDecoder;
  /** Bbox du site [ouest, sud, est, nord] en degrés. */
  bbox: [number, number, number, number];
}

/**
 * Fabrique la configuration terrain à partir des métadonnées du manifeste.
 * Principe D (Dependency Inversion) : la vue 3D reçoit une `TerrainConfig`
 * abstraite plutôt qu'une dépendance directe sur `SiteManifest`.
 */
export function buildTerrainConfig(
  siteId: string,
  bbox: [number, number, number, number],
  textureLayerId: string,
  textureFormat: "webp" | "png",
): TerrainConfig {
  return {
    elevationUrlTemplate: `/tiles/${siteId}/terrain_rgb/{z}/{x}/{y}.png`,
    textureUrlTemplate: `/tiles/${siteId}/${textureLayerId}/{z}/{x}/{y}.${textureFormat}`,
    meshMaxError: 1.0,
    elevationDecoder: MARSWALK_ELEVATION_DECODER,
    bbox,
  };
}
