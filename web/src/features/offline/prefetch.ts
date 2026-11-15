/**
 * Préchargement du paquet de site dans le cache du service worker.
 *
 * Principe S (Single Responsibility) : construire la liste des URLs à
 * précharger et les mettre en cache est la seule responsabilité de ce module.
 *
 * Principe D (Dependency Inversion) : `prefetchSite` reçoit une fonction
 * `fetchFn` injectable — ce qui permet de tester sans réseau réel.
 */
import type { SiteManifest } from "@/shared/api/client";
import type { PrefetchProgress, PrefetchResource } from "./types";

/** Niveaux de zoom à précharger pour chaque couche. */
const PREFETCH_ZOOM_LEVELS = [12, 13, 14, 15];
/** Nombre maximal de téléchargements en parallèle. */
const CONCURRENCY = 4;

/**
 * Construit la liste des ressources à mettre en cache pour un site.
 *
 * Inclut :
 * - Le manifeste JSON du site
 * - Les couches vectorielles (rover_traverse, ground_images, cibles)
 * - Les tuiles raster aux niveaux de zoom utiles pour toutes les couches
 *   visibles par défaut (préréglage « safety »)
 * - Les tuiles terrain-RGB pour la vue 3D
 */
export function buildPrefetchList(
  manifest: SiteManifest,
  siteId: string,
): PrefetchResource[] {
  const resources: PrefetchResource[] = [];

  // Manifeste
  resources.push({ url: `/api/sites/${siteId}`, bytes: 10_000 });

  // Couches vectorielles
  for (const layer of manifest.layers) {
    if (layer.kind === "vector" || layer.kind === "ground") {
      resources.push({
        url: `/api/sites/${siteId}/vector/${layer.id}`,
        bytes: 50_000,
      });
    }
  }

  // Tuiles raster pour les couches du préréglage sécurité
  const SAFETY_LAYERS = [
    "hillshade",
    "slope",
    "scarps",
    "obstacles",
    "hirise_vis",
    "ctx_vis",
  ];
  for (const layer of manifest.layers) {
    if (!layer.tiles || !SAFETY_LAYERS.includes(layer.id)) continue;
    for (const z of PREFETCH_ZOOM_LEVELS) {
      if (z < layer.tiles.minzoom || z > layer.tiles.maxzoom) continue;
      // Nombre de tuiles au zoom z sur la bbox du site
      const tiles = tilesInBbox(manifest.bbox as [number, number, number, number], z);
      for (const [x, y] of tiles) {
        resources.push({
          url: `/tiles/${siteId}/${layer.id}/${z}/${x}/${y}.${layer.tiles.format}`,
          bytes: 20_000,
        });
      }
    }
  }

  // Tuiles terrain-RGB
  if (manifest.terrain) {
    for (const z of PREFETCH_ZOOM_LEVELS) {
      if (z < manifest.terrain.minzoom || z > manifest.terrain.maxzoom) continue;
      const tiles = tilesInBbox(manifest.bbox as [number, number, number, number], z);
      for (const [x, y] of tiles) {
        resources.push({
          url: `/tiles/${siteId}/terrain_rgb/${z}/${x}/${y}.png`,
          bytes: 15_000,
        });
      }
    }
  }

  return resources;
}

/**
 * Calcule les indices de tuiles WebMercatorQuad couvrant une bbox.
 * Coordonnées martiennes traitées comme des degrés — règle R3.
 */
function tilesInBbox(
  bbox: [number, number, number, number],
  z: number,
): [number, number][] {
  const [west, south, east, north] = bbox;
  const n = 2 ** z;

  function lonToX(lon: number): number {
    return Math.floor(((lon + 180) / 360) * n);
  }
  function latToY(lat: number): number {
    const latRad = (lat * Math.PI) / 180;
    return Math.floor(
      ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) /
        2) *
        n,
    );
  }

  const x0 = lonToX(west);
  const x1 = lonToX(east);
  const y0 = latToY(north); // nord = y plus petit
  const y1 = latToY(south);

  const tiles: [number, number][] = [];
  for (let x = x0; x <= Math.min(x1, n - 1); x++) {
    for (let y = y0; y <= Math.min(y1, n - 1); y++) {
      tiles.push([x, y]);
    }
  }
  return tiles;
}

/**
 * Précharge toutes les ressources d'un site dans le cache du navigateur.
 *
 * @param resources  Liste des ressources à précharger.
 * @param onProgress Appelé après chaque ressource téléchargée.
 * @param signal     Pour annuler le préchargement.
 * @param fetchFn    Fonction fetch injectable (testabilité).
 */
export async function prefetchResources(
  resources: PrefetchResource[],
  onProgress: (progress: PrefetchProgress) => void,
  signal: AbortSignal,
  fetchFn: typeof fetch = fetch,
): Promise<void> {
  const total = resources.length;
  let done = 0;

  onProgress({ done: 0, total, running: true, error: null });

  // Ouvre le cache dédié au préchargement
  const cache = await caches.open("marswalk-prefetch-v1");

  // Traitement par lots (CONCURRENCY requêtes simultanées)
  for (let i = 0; i < resources.length; i += CONCURRENCY) {
    if (signal.aborted) break;

    const batch = resources.slice(i, i + CONCURRENCY);
    await Promise.all(
      batch.map(async ({ url }) => {
        if (signal.aborted) return;
        try {
          const cached = await cache.match(url);
          if (!cached) {
            const response = await fetchFn(url, { signal });
            if (response.ok) await cache.put(url, response);
          }
        } catch {
          // Ressource inaccessible : on continue sans bloquer
        } finally {
          done++;
          onProgress({ done, total, running: done < total, error: null });
        }
      }),
    );
  }

  onProgress({ done, total, running: false, error: null });
}
