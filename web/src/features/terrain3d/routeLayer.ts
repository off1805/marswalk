/**
 * Construction de la couche deck.gl représentant l'itinéraire sur le terrain 3D.
 *
 * Principe S (Single Responsibility) : construire la PathLayer de l'itinéraire
 * est la seule responsabilité de ce module. Il est séparé de TerrainCanvas
 * pour pouvoir être testé et modifié indépendamment.
 */
import { PathLayer } from "@deck.gl/layers";
import type { Route } from "@/shared/api/client";
import { colors, hexToRgb } from "@/shared/theme";

function rgba(hex: string, a = 255): [number, number, number, number] {
  const [r, g, b] = hexToRgb(hex);
  return [r, g, b, a];
}

const VARIANT_COLOR: Record<string, [number, number, number, number]> = {
  safest: rgba(colors.route.safest, 230),
  fastest: rgba(colors.route.fastest, 230),
  science: rgba(colors.route.science, 230),
};

/**
 * Construit la PathLayer de l'itinéraire actif, avec une légère altitude
 * au-dessus du terrain pour éviter le z-fighting.
 */
export function buildRouteLayer(route: Route): PathLayer {
  const coords = route.geometry.coordinates as [number, number][];
  // Élever légèrement le tracé au-dessus du terrain
  const elevated = coords.map(([lon, lat]) => [lon, lat, 10] as [number, number, number]);
  const color = VARIANT_COLOR[route.variant] ?? rgba(colors.info, 230);

  return new PathLayer({
    id: `f6-route-${route.id}`,
    data: [{ path: elevated }],
    getPath: (d: { path: [number, number, number][] }) => d.path,
    getColor: color,
    getWidth: 6,
    widthUnits: "pixels",
    widthMinPixels: 3,
    pickable: false,
  });
}
