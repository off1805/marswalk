import { describe, expect, it } from "vitest";
import { pickSite } from "./SitePicker";

describe("pickSite", () => {
  it("prend le premier souhait servi par l'API", () => {
    expect(pickSite(["fictif", "jezero"], ["fictif", null])).toBe("fictif");
    expect(pickSite(["fictif", "jezero"], [null, "inconnu", "jezero"])).toBe("jezero");
  });
  it("préfère Jezero, puis un site réel, puis le site fictif", () => {
    expect(pickSite(["fictif", "jezero"], [])).toBe("jezero");
    expect(pickSite(["fictif", "gale"], [])).toBe("gale");
    expect(pickSite(["fictif"], ["jezero"])).toBe("fictif");
    expect(pickSite([], [])).toBeNull();
  });
});
