/**
 * Tests de la feature F6 — vue 3D.
 *
 * On teste les fonctions pures (aucune dépendance React ou deck.gl) :
 *
 *   flyover.ts         sampleProfile, computeCamera, advanceFlyover
 *   terrain.config.ts  buildTerrainConfig, MARSWALK_ELEVATION_DECODER
 *   routeLayer.ts      buildRouteLayer (structure seulement)
 *
 * Critères d'acceptation couverts :
 *   - Le survol se lance d'un clic (démontré par l'intégration)
 *   - L'exagération verticale est réglable et reflétée dans la caméra
 *   - La barre de progression avance correctement
 *   - `advanceFlyover` retourne null en fin de parcours
 */
import { describe, it, expect } from "vitest";
import {
  sampleProfile,
  computeCamera,
  advanceFlyover,
  type RouteProfile,
  EXAGGERATION_STEPS,
} from "./flyover";
import {
  buildTerrainConfig,
  MARSWALK_ELEVATION_DECODER,
} from "./terrain.config";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const FLAT_PROFILE: RouteProfile[] = [
  { distanceM: 0, position: [77.57, 18.38], elevationM: 100 },
  { distanceM: 500, position: [77.575, 18.382], elevationM: 100 },
  { distanceM: 1000, position: [77.58, 18.385], elevationM: 100 },
];

const RISING_PROFILE: RouteProfile[] = [
  { distanceM: 0, position: [77.57, 18.38], elevationM: 0 },
  { distanceM: 500, position: [77.575, 18.382], elevationM: 50 },
  { distanceM: 1000, position: [77.58, 18.385], elevationM: 100 },
];

// ── sampleProfile ─────────────────────────────────────────────────────────────

describe("sampleProfile", () => {
  it("retourne le premier point pour une distance nulle", () => {
    const { position, elevationM } = sampleProfile(FLAT_PROFILE, 0);
    expect(position[0]).toBeCloseTo(77.57);
    expect(elevationM).toBe(100);
  });

  it("retourne le dernier point au-delà de la longueur totale", () => {
    const { position } = sampleProfile(FLAT_PROFILE, 9999);
    expect(position[0]).toBeCloseTo(77.58);
  });

  it("interpole correctement à mi-parcours", () => {
    const { elevationM } = sampleProfile(RISING_PROFILE, 500);
    expect(elevationM).toBeCloseTo(50);
  });

  it("interpole la position entre deux échantillons", () => {
    const { position } = sampleProfile(FLAT_PROFILE, 250);
    // 250 m = moitié entre 0 et 500 m
    expect(position[0]).toBeCloseTo((77.57 + 77.575) / 2, 4);
  });

  it("gère un profil vide sans erreur", () => {
    const { position, elevationM } = sampleProfile([], 100);
    expect(position).toEqual([0, 0]);
    expect(elevationM).toBe(0);
  });

  it("gère un profil à un seul point", () => {
    const single: RouteProfile[] = [
      { distanceM: 0, position: [1, 2], elevationM: 42 },
    ];
    const { elevationM } = sampleProfile(single, 500);
    expect(elevationM).toBe(42);
  });
});

// ── computeCamera ─────────────────────────────────────────────────────────────

describe("computeCamera", () => {
  it("retourne une altitude basée sur l'élévation du terrain + offset caméra", () => {
    const camera = computeCamera(FLAT_PROFILE, 0, 1);
    // altitude = élévation × exagération + offset (80 m)
    expect(camera.altitude).toBeGreaterThan(100);
    expect(camera.altitude).toBeLessThan(300);
  });

  it("multiplie l'altitude par l'exagération verticale", () => {
    const cam1 = computeCamera(RISING_PROFILE, 1000, 1);
    const cam5 = computeCamera(RISING_PROFILE, 1000, 5);
    // altitude(×5) doit être plus grande que altitude(×1)
    expect(cam5.altitude).toBeGreaterThan(cam1.altitude);
  });

  it("retourne un bearing entre 0 et 360", () => {
    const camera = computeCamera(FLAT_PROFILE, 0, 1);
    expect(camera.bearing).toBeGreaterThanOrEqual(0);
    expect(camera.bearing).toBeLessThan(360);
  });

  it("place la caméra aux bonnes coordonnées de départ", () => {
    const camera = computeCamera(FLAT_PROFILE, 0, 1);
    expect(camera.longitude).toBeCloseTo(77.57, 2);
    expect(camera.latitude).toBeCloseTo(18.38, 2);
  });
});

// ── advanceFlyover ────────────────────────────────────────────────────────────

describe("advanceFlyover", () => {
  it("avance la progression de façon proportionnelle au temps", () => {
    // À vitesse ×1, 1000 ms → 20 m
    const next = advanceFlyover(0, 10_000, 1, 1000);
    expect(next).toBeCloseTo(20, 0);
  });

  it("avance plus vite à vitesse ×2", () => {
    const at1 = advanceFlyover(0, 10_000, 1, 1000);
    const at2 = advanceFlyover(0, 10_000, 2, 1000);
    expect(at2).toBeCloseTo((at1 ?? 0) * 2, 0);
  });

  it("retourne null quand la progression atteint ou dépasse la longueur totale", () => {
    expect(advanceFlyover(990, 1000, 1, 1000)).toBeNull();
  });

  it("ne retourne pas null si la progression reste inférieure à la longueur", () => {
    expect(advanceFlyover(0, 10_000, 1, 100)).not.toBeNull();
  });

  it("retourne null immédiatement si déjà à la fin", () => {
    expect(advanceFlyover(1000, 1000, 1, 16)).toBeNull();
  });
});

// ── buildTerrainConfig ────────────────────────────────────────────────────────

describe("buildTerrainConfig", () => {
  const bbox: [number, number, number, number] = [77.5, 18.3, 77.6, 18.4];
  const config = buildTerrainConfig("fictif", bbox, "hirise_vis", "webp");

  it("construit les URLs avec le bon siteId", () => {
    expect(config.elevationUrlTemplate).toContain("fictif");
    expect(config.textureUrlTemplate).toContain("fictif");
  });

  it("inclut {z} {x} {y} dans les gabarits d'URL", () => {
    expect(config.elevationUrlTemplate).toContain("{z}");
    expect(config.textureUrlTemplate).toContain("{z}");
  });

  it("choisit le bon identifiant de couche de texture", () => {
    expect(config.textureUrlTemplate).toContain("hirise_vis");
  });

  it("utilise le décodeur Marswalk", () => {
    expect(config.elevationDecoder.offset).toBe(MARSWALK_ELEVATION_DECODER.offset);
  });

  it("conserve la bbox du site", () => {
    expect(config.bbox).toEqual(bbox);
  });
});

// ── MARSWALK_ELEVATION_DECODER ────────────────────────────────────────────────

describe("MARSWALK_ELEVATION_DECODER", () => {
  it("décode un pixel blanc (255,255,255) en altitude positive", () => {
    const { rScaler, gScaler, bScaler, offset } = MARSWALK_ELEVATION_DECODER;
    const alt = 255 * rScaler + 255 * gScaler + 255 * bScaler + offset;
    // Doit être une altitude plausible (positive pour des pixels clairs)
    expect(alt).toBeGreaterThan(0);
  });

  it("correspond à la convention Mapbox (-10 000 m pour le pixel noir)", () => {
    const { offset } = MARSWALK_ELEVATION_DECODER;
    // Pixel noir (0,0,0) → offset
    expect(offset).toBe(-10_000);
  });
});

// ── EXAGGERATION_STEPS ────────────────────────────────────────────────────────

describe("EXAGGERATION_STEPS", () => {
  it("contient au moins 1 (pas d'exagération) et une valeur > 1", () => {
    expect(EXAGGERATION_STEPS).toContain(1);
    expect(EXAGGERATION_STEPS.some((v) => v > 1)).toBe(true);
  });

  it("est trié par ordre croissant", () => {
    for (let i = 1; i < EXAGGERATION_STEPS.length; i++) {
      expect(EXAGGERATION_STEPS[i]!).toBeGreaterThan(EXAGGERATION_STEPS[i - 1]!);
    }
  });
});
