/**
 * Tests de la géodésie martienne (C1) — TypeScript.
 *
 * Vérifie la parité avec ``marswalk_core.geodesy`` (Python).
 * Toutes les formules utilisent le rayon de la sphère Mars 2000 (3 396 190 m).
 */

import { describe, expect, it } from "vitest";
import {
  MARS_2000_RADIUS_M,
  type LonLat,
  bearingDeg,
  computeScaleBar,
  distanceM,
  metersPerPixel,
} from "./geodesy";

// ---------------------------------------------------------------------------
// distanceM
// ---------------------------------------------------------------------------

describe("distanceM", () => {
  it("1° de longitude à l'équateur ≈ 2π R / 360", () => {
    const expected = (2 * Math.PI * MARS_2000_RADIUS_M) / 360;
    const d = distanceM([0, 0], [1, 0]);
    expect(Math.abs(d - expected)).toBeLessThan(1); // < 1 m
    expect(d).toBeGreaterThan(59_200);
    expect(d).toBeLessThan(59_300);
  });

  it("1° de latitude à l'équateur ≈ même valeur", () => {
    const expected = (2 * Math.PI * MARS_2000_RADIUS_M) / 360;
    expect(Math.abs(distanceM([0, 0], [0, 1]) - expected)).toBeLessThan(1);
  });

  it("symétrie A→B = B→A", () => {
    const a: LonLat = [77.5, 18.3];
    const b: LonLat = [77.6, 18.4];
    expect(distanceM(a, b)).toBeCloseTo(distanceM(b, a), 9);
  });

  it("distance nulle sur un point identique", () => {
    expect(distanceM([77.58, 18.38], [77.58, 18.38])).toBe(0);
  });

  it("points antipodaux = π × R", () => {
    const expected = Math.PI * MARS_2000_RADIUS_M;
    expect(Math.abs(distanceM([0, 0], [180, 0]) - expected)).toBeLessThan(10);
  });

  it("utilise le rayon martien, pas le rayon terrestre (~6 371 km)", () => {
    const d = distanceM([0, 0], [1, 0]);
    expect(d).toBeLessThan(70_000); // clairement pas terrestre (111 km)
    expect(d).toBeGreaterThan(55_000); // clairement martien (~59 km)
  });

  it("100 m au nord de Jezero ≈ 100 m", () => {
    const offset = (100 / MARS_2000_RADIUS_M) * (180 / Math.PI);
    const hab: LonLat = [77.5782222, 18.3816712];
    const north: LonLat = [hab[0], hab[1] + offset];
    expect(Math.abs(distanceM(hab, north) - 100)).toBeLessThan(1);
  });
});

// ---------------------------------------------------------------------------
// bearingDeg
// ---------------------------------------------------------------------------

describe("bearingDeg", () => {
  it("cap vers l'est = 90°", () => {
    expect(bearingDeg([0, 0], [1, 0])).toBeCloseTo(90, 0);
  });

  it("cap vers le nord = 0°", () => {
    expect(bearingDeg([0, 0], [0, 1])).toBeCloseTo(0, 0);
  });

  it("cap vers le sud = 180°", () => {
    expect(bearingDeg([0, 1], [0, 0])).toBeCloseTo(180, 0);
  });

  it("cap vers l'ouest = 270°", () => {
    expect(bearingDeg([1, 0], [0, 0])).toBeCloseTo(270, 0);
  });

  it("cap nord-est ≈ 45°", () => {
    const b = bearingDeg([0, 0], [1, 1]);
    expect(b).toBeGreaterThan(40);
    expect(b).toBeLessThan(50);
  });

  it("toujours dans [0, 360)", () => {
    const pairs: [LonLat, LonLat][] = [
      [[0, 0], [1, 1]],
      [[100, 50], [-100, -50]],
      [[0, 80], [180, -80]],
    ];
    for (const [a, b] of pairs) {
      const br = bearingDeg(a, b);
      expect(br).toBeGreaterThanOrEqual(0);
      expect(br).toBeLessThan(360);
    }
  });
});

// ---------------------------------------------------------------------------
// metersPerPixel
// ---------------------------------------------------------------------------

describe("metersPerPixel", () => {
  it("diminue quand le zoom augmente", () => {
    expect(metersPerPixel(12, 0)).toBeGreaterThan(metersPerPixel(14, 0));
    expect(metersPerPixel(14, 0)).toBeGreaterThan(metersPerPixel(16, 0));
  });

  it("diminue avec la latitude", () => {
    expect(metersPerPixel(14, 45)).toBeLessThan(metersPerPixel(14, 0));
  });

  it("zoom 0 : ≈ 2π R / 256", () => {
    const expected = (2 * Math.PI * MARS_2000_RADIUS_M) / 256;
    expect(metersPerPixel(0, 0)).toBeCloseTo(expected, 0);
  });

  it("utilise le rayon martien (zoom 14 à l'équateur : 4–7 m/px)", () => {
    const mpp = metersPerPixel(14, 0);
    expect(mpp).toBeGreaterThan(4);
    expect(mpp).toBeLessThan(7);
  });
});

// ---------------------------------------------------------------------------
// computeScaleBar
// ---------------------------------------------------------------------------

describe("computeScaleBar", () => {
  it("widthPx ≤ maxWidthPx pour tous les zooms", () => {
    for (const zoom of [10, 12, 14, 16]) {
      expect(computeScaleBar(zoom, 18.38, 200).widthPx).toBeLessThanOrEqual(200);
    }
  });

  it("widthPx > 0", () => {
    expect(computeScaleBar(14, 18.38, 200).widthPx).toBeGreaterThan(0);
  });

  it("distanceM est un palier rond", () => {
    const STEPS = [10, 20, 50, 100, 200, 500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000];
    expect(STEPS).toContain(computeScaleBar(14, 18.38).distanceM);
  });

  it("label contient 'm' ou 'km'", () => {
    expect(computeScaleBar(14, 18.38).label).toMatch(/\d+\s*(m|km)/);
  });

  it("widthPx = round(distanceM / metersPerPixel)", () => {
    const zoom = 14;
    const lat = 18.38;
    const r = computeScaleBar(zoom, lat);
    expect(r.widthPx).toBe(Math.round(r.distanceM / metersPerPixel(zoom, lat)));
  });

  it("maxWidthPx plus petit → largeur plus petite ou égale", () => {
    expect(computeScaleBar(14, 18.38, 100).widthPx).toBeLessThanOrEqual(
      computeScaleBar(14, 18.38, 200).widthPx,
    );
  });

  it("zoom élevé → distance plus petite", () => {
    expect(computeScaleBar(16, 18.38).distanceM).toBeLessThanOrEqual(
      computeScaleBar(10, 18.38).distanceM,
    );
  });
});

// ---------------------------------------------------------------------------
// Parité Python–TypeScript
// ---------------------------------------------------------------------------

describe("parité Python-TypeScript", () => {
  it("1° à l'équateur ≈ 59274 m (2π × 3396190 / 360)", () => {
    const expected = (2 * Math.PI * 3_396_190) / 360;
    expect(distanceM([0, 0], [1, 0])).toBeCloseTo(expected, 0);
  });

  it("distance Jezero habitat → rover ≈ 170 m (manifeste fictif)", () => {
    const hab: LonLat = [77.5782222, 18.3816712];
    const rov: LonLat = [77.5810667, 18.380659];
    const d = distanceM(hab, rov);
    expect(d).toBeGreaterThan(100);
    expect(d).toBeLessThan(300);
  });
});
