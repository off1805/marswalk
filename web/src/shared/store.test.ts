import { beforeEach, describe, expect, it } from "vitest";
import { useShared } from "./store";

describe("magasin partagé", () => {
  beforeEach(() => useShared.setState({ layers: {}, hoverDistanceM: null }));

  it("règle la visibilité et l'opacité d'une couche", () => {
    useShared.getState().setLayer("slope", { visible: true });
    useShared.getState().setLayer("slope", { opacity: 0.4 });
    expect(useShared.getState().layers.slope).toEqual({ visible: true, opacity: 0.4 });
  });

  it("partage la distance survolée", () => {
    useShared.getState().setHoverDistance(120);
    expect(useShared.getState().hoverDistanceM).toBe(120);
  });
});
