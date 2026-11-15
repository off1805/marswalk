import { describe, expect, it } from "vitest";
import { SLOTS } from "./feature";
import { registry } from "./registry";

describe("registre des fonctionnalités", () => {
  it("liste toutes les fonctionnalités prévues par les contrats", () => {
    expect(registry.map((f) => f.id).sort()).toEqual(
      ["export", "ground-images", "map", "offline", "profile", "safety", "targets", "terrain3d", "voice"].sort(),
    );
  });

  it("n'utilise que les emplacements fixes", () => {
    for (const f of registry) for (const p of f.panels) expect(SLOTS).toContain(p.slot);
  });
});
