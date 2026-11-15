/**
 * Tests de l'algorithme Mars24 (C1) — TypeScript.
 *
 * Les cas de référence de la NASA GISS sont vérifiés à mieux que 2 secondes LMST.
 * Les vecteurs de test partagés avec Python sont dans packages/core/tests/marstime_vectors.json.
 *
 * Référence : https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  deltaJ2000Tt,
  ls,
  marsMeanAnomaly,
  marsSolDate,
  marsTime,
  mstHours,
} from "./marstime";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseHms(s: string): number {
  const [h, m, sec] = s.split(":").map(Number) as [number, number, number];
  return h + m / 60 + sec / 3600;
}

function diffHmsS(a: string, b: string): number {
  const diff = Math.abs(parseHms(a) - parseHms(b));
  return Math.min(diff, 24 - diff) * 3600;
}

// ---------------------------------------------------------------------------
// Cas 1 — quasi-minuit commun Terre/Mars (2000-01-06T00:00:00Z)
// ---------------------------------------------------------------------------

describe("GISS-1 : 2000-01-06T00:00:00Z", () => {
  const utc = new Date("2000-01-06T00:00:00Z");
  const lon = 0.0;

  it("ΔtJ2000 ≈ 4.50074 jours", () => {
    expect(deltaJ2000Tt(utc)).toBeCloseTo(4.50074, 3);
  });

  it("M ≈ 21.746°", () => {
    expect(marsMeanAnomaly(deltaJ2000Tt(utc))).toBeCloseTo(21.746, 1);
  });

  it("Ls ≈ 277.19°", () => {
    expect(ls(deltaJ2000Tt(utc))).toBeCloseTo(277.188, 1);
  });

  it("MST ≈ 23:59:39", () => {
    const mst = mstHours(utc);
    // reconstruct HH:MM:SS
    const total = Math.round(((mst % 24) + 24) % 24 * 3600) % 86400;
    const hh = String(Math.floor(total / 3600)).padStart(2, "0");
    const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
    const ss = String(total % 60).padStart(2, "0");
    expect(diffHmsS(`${hh}:${mm}:${ss}`, "23:59:39")).toBeLessThan(2);
  });

  it("LMST ≈ 23:59:39 (lon = 0°)", () => {
    const r = marsTime(utc, lon, utc);
    expect(diffHmsS(r.lmst, "23:59:39")).toBeLessThan(2);
  });

  it("LTST ≈ 23:38:54", () => {
    const r = marsTime(utc, lon, utc);
    expect(diffHmsS(r.ltst, "23:38:54")).toBeLessThan(2);
  });

  it("ls_deg ≈ 277.19", () => {
    const r = marsTime(utc, lon, utc);
    expect(Math.abs(r.ls_deg - 277.188)).toBeLessThan(0.05);
  });
});

// ---------------------------------------------------------------------------
// Cas 2 — Spirit MER-A landing (2004-01-03T13:46:31Z)
// ---------------------------------------------------------------------------

describe("GISS-2 : Spirit landing", () => {
  const utc = new Date("2004-01-03T13:46:31Z");
  const lonEast = -184.702; // 184.702°W → −184.702°E

  it("Ls ≈ 327.324°", () => {
    expect(ls(deltaJ2000Tt(utc))).toBeCloseTo(327.324, 1);
  });

  it("LMST ≈ 00:51:07", () => {
    const r = marsTime(utc, lonEast, utc);
    expect(diffHmsS(r.lmst, "00:51:07")).toBeLessThan(2);
  });

  it("LTST ≈ 00:00:00", () => {
    const r = marsTime(utc, lonEast, utc);
    expect(diffHmsS(r.ltst, "00:00:00")).toBeLessThan(3);
  });
});

// ---------------------------------------------------------------------------
// Tests comportementaux
// ---------------------------------------------------------------------------

describe("comportement général", () => {
  it("ls_deg est dans [0, 360)", () => {
    for (const year of [2000, 2004, 2020, 2026]) {
      const utc = new Date(`${year}-06-15T00:00:00Z`);
      const r = marsTime(utc, 0, utc);
      expect(r.ls_deg).toBeGreaterThanOrEqual(0);
      expect(r.ls_deg).toBeLessThan(360);
    }
  });

  it("lmst_hours est dans [0, 24)", () => {
    for (const lon of [-180, -90, 0, 77.58, 90, 180]) {
      const utc = new Date("2026-11-14T08:00:00Z");
      const r = marsTime(utc, lon, utc);
      expect(r.lmst_hours).toBeGreaterThanOrEqual(0);
      expect(r.lmst_hours).toBeLessThan(24);
    }
  });

  it("un décalage de 90°E vaut +6 h de LMST", () => {
    const utc = new Date("2026-11-14T12:00:00Z");
    const r0 = marsTime(utc, 0, utc);
    const r90 = marsTime(utc, 90, utc);
    const diff = ((r90.lmst_hours - r0.lmst_hours) % 24 + 24) % 24;
    expect(Math.abs(diff - 6)).toBeLessThan(0.001);
  });

  it("MSD augmente avec le temps", () => {
    const t1 = new Date("2026-01-01T00:00:00Z");
    const t2 = new Date("2026-06-01T00:00:00Z");
    const t3 = new Date("2026-11-01T00:00:00Z");
    expect(marsSolDate(t1)).toBeLessThan(marsSolDate(t2));
    expect(marsSolDate(t2)).toBeLessThan(marsSolDate(t3));
  });

  it("sol de mission = 1 au premier instant", () => {
    const epoch = new Date("2026-11-01T00:00:00Z");
    const utc = new Date("2026-11-01T06:00:00Z");
    const r = marsTime(utc, 77.58, epoch);
    expect(r.sol).toBe(1);
  });

  it("sol de mission = 2 après un sol entier", () => {
    const epoch = new Date("2026-11-01T00:00:00Z");
    // 1 sol = 88 775.244 s → arrondir à 88 776 s
    const utc = new Date(epoch.getTime() + 88_776_000);
    const r = marsTime(utc, 77.58, epoch);
    expect(r.sol).toBe(2);
  });

  it("ltst et ls_deg sont présents (pas null/undefined)", () => {
    const utc = new Date("2026-11-14T12:00:00Z");
    const r = marsTime(utc, 77.58, utc);
    expect(r.ltst).toBeDefined();
    expect(r.ls_deg).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Parité Python–TypeScript via vecteurs JSON partagés
// ---------------------------------------------------------------------------

describe("vecteurs partagés Python-TypeScript", () => {
  const vectorsPath = resolve(
    __dirname,
    "../../../packages/core/tests/c1/marstime_vectors.json",
  );
  const { vectors } = JSON.parse(readFileSync(vectorsPath, "utf-8")) as {
    vectors: Array<{
      name: string;
      utc: string;
      lon_east: number;
      expected: Record<string, unknown>;
      tolerance_lmst_s: number;
    }>;
  };

  // LMST exact
  for (const v of vectors) {
    if (!v.expected.lmst) continue;
    it(`${v.name} — LMST`, () => {
      const utc = new Date(v.utc);
      const r = marsTime(utc, v.lon_east, utc);
      const diff = diffHmsS(r.lmst, v.expected.lmst as string);
      expect(diff).toBeLessThanOrEqual(v.tolerance_lmst_s);
    });
  }

  // Ls exact
  for (const v of vectors) {
    if (!("ls_deg" in v.expected)) continue;
    it(`${v.name} — Ls`, () => {
      const utc = new Date(v.utc);
      const r = marsTime(utc, v.lon_east, utc);
      expect(Math.abs(r.ls_deg - (v.expected.ls_deg as number))).toBeLessThan(0.1);
    });
  }

  // lmst_hours_range
  for (const v of vectors) {
    if (!v.expected.lmst_hours_range) continue;
    it(`${v.name} — LMST range`, () => {
      const utc = new Date(v.utc);
      const r = marsTime(utc, v.lon_east, utc);
      const [lo, hi] = v.expected.lmst_hours_range as [number, number];
      expect(r.lmst_hours).toBeGreaterThanOrEqual(lo);
      expect(r.lmst_hours).toBeLessThan(hi);
    });
  }

  // lmst_offset_from_mst_h
  for (const v of vectors) {
    if (!("lmst_offset_from_mst_h" in v.expected)) continue;
    it(`${v.name} — LMST offset`, () => {
      const utc = new Date(v.utc);
      const r = marsTime(utc, v.lon_east, utc);
      const mst = mstHours(utc);
      const offset = v.expected.lmst_offset_from_mst_h as number;
      const expected = ((mst + offset) % 24 + 24) % 24;
      let diffS = Math.abs(r.lmst_hours - expected) * 3600;
      diffS = Math.min(diffS, 86400 - diffS);
      expect(diffS).toBeLessThanOrEqual(v.tolerance_lmst_s);
    });
  }

  // sol_min
  for (const v of vectors) {
    if (!("sol_min" in v.expected)) continue;
    it(`${v.name} — sol minimum`, () => {
      const utc = new Date(v.utc);
      const epoch = new Date("2026-11-01T00:00:00Z");
      const r = marsTime(utc, v.lon_east, epoch);
      expect(r.sol).toBeGreaterThanOrEqual(v.expected.sol_min as number);
    });
  }
});
