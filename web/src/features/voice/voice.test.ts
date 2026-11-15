/**
 * Tests de la feature V1 — assistant vocal Nebula.
 *
 * Couvre les modules purs (sans navigateur) :
 *   commandParser.ts  parseCommand, looksLikeCommand, containsWakeWord, randomWakeResponse
 */
import { describe, it, expect } from "vitest";
import {
  parseCommand,
  looksLikeCommand,
  containsWakeWord,
  randomWakeResponse,
  WAKE_RESPONSES,
  WAKE_WORD,
} from "./commandParser";

// ── Wake word ─────────────────────────────────────────────────────────────────

describe("containsWakeWord", () => {
  it("détecte le mot exact", () => {
    expect(containsWakeWord("Nebula")).toBe(true);
  });
  it("est insensible à la casse", () => {
    expect(containsWakeWord("NEBULA")).toBe(true);
    expect(containsWakeWord("nebula")).toBe(true);
  });
  it("tolère la variante 'nevula'", () => {
    expect(containsWakeWord("nevula")).toBe(true);
  });
  it("retourne false pour un texte sans wake word", () => {
    expect(containsWakeWord("hello there")).toBe(false);
  });
  it(`WAKE_WORD vaut "${WAKE_WORD}"`, () => {
    expect(WAKE_WORD).toBe("Nebula");
  });
});

describe("randomWakeResponse", () => {
  it("retourne une chaîne non vide", () => {
    expect(randomWakeResponse().length).toBeGreaterThan(0);
  });
  it("retourne une réponse de la liste WAKE_RESPONSES", () => {
    // Appeler 20 fois pour couvrir le hasard
    for (let i = 0; i < 20; i++) {
      expect(WAKE_RESPONSES).toContain(randomWakeResponse());
    }
  });
  it("WAKE_RESPONSES contient au moins 5 réponses", () => {
    expect(WAKE_RESPONSES.length).toBeGreaterThanOrEqual(5);
  });
});

// ── addTarget ─────────────────────────────────────────────────────────────────

describe("parseCommand — addTarget", () => {
  const cases = [
    "add a target",
    "add target",
    "place a waypoint",
    "drop a pin",
    "mark a point",
    "create a new target",
    "set a waypoint",
    "insert a marker",
    "new target",
    "new waypoint",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "addTarget" });
    });
  }
});

// ── selectVariant safest ──────────────────────────────────────────────────────

describe("parseCommand — selectVariant safest", () => {
  const cases = [
    "select the safest route",
    "choose the safe route",
    "take the most secure path",
    "use the safety variant",
    "go with the cautious route",
    "apply the conservative path",
    "pick the safest option",
    "safest route",
    "safety route",
    "most secure",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "selectVariant", variant: "safest" });
    });
  }
});

// ── selectVariant fastest ─────────────────────────────────────────────────────

describe("parseCommand — selectVariant fastest", () => {
  const cases = [
    "select the fastest route",
    "choose the quickest path",
    "take the most direct route",
    "go with the shortest path",
    "pick the rapid option",
    "fastest route",
    "quickest",
    "most direct",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "selectVariant", variant: "fastest" });
    });
  }
});

// ── selectVariant science ─────────────────────────────────────────────────────

describe("parseCommand — selectVariant science", () => {
  const cases = [
    "select the science route",
    "choose the scientific path",
    "take the research route",
    "go with the exploration variant",
    "science route",
    "scientific variant",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "selectVariant", variant: "science" });
    });
  }
});

// ── returnToHabitat ───────────────────────────────────────────────────────────

describe("parseCommand — returnToHabitat", () => {
  const cases = [
    "return to habitat",
    "return to base",
    "head back to home",
    "go back to shelter",
    "abort mission",
    "emergency return",
    "go home",
    "RTB",
    "abort",
    "mayday",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "returnToHabitat" });
    });
  }
});

// ── acknowledgeAlert ──────────────────────────────────────────────────────────

describe("parseCommand — acknowledgeAlert", () => {
  const cases = [
    "acknowledge the alert",
    "confirm the warning",
    "dismiss the notification",
    "clear the alarm",
    "got it",
    "copy that",
    "understood",
    "roger",
    "affirmative",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "acknowledgeAlert" });
    });
  }
});

// ── startFlyover ──────────────────────────────────────────────────────────────

describe("parseCommand — startFlyover", () => {
  const cases = [
    "start the flyover",
    "launch the 3D view",
    "open 3d",
    "begin flyover",
    "show 3D",
    "activate 3d mode",
    "fly over",
    "aerial view",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "startFlyover" });
    });
  }
});

// ── pauseFlyover / resumeFlyover ──────────────────────────────────────────────

describe("parseCommand — pauseFlyover", () => {
  const cases = ["pause the flyover", "stop the animation", "halt the camera", "freeze the flight"];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "pauseFlyover" });
    });
  }
});

describe("parseCommand — resumeFlyover", () => {
  const cases = ["resume the flyover", "continue the animation", "restart the flight", "unpause flyover"];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "resumeFlyover" });
    });
  }
});

// ── setFlyoverSpeed ───────────────────────────────────────────────────────────

describe("parseCommand — setFlyoverSpeed", () => {
  it("reconnaît 'speed to 2'", () => {
    expect(parseCommand("speed to 2")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
  it("reconnaît 'set speed 5'", () => {
    expect(parseCommand("set speed 5")).toEqual({ kind: "setFlyoverSpeed", speed: 5 });
  });
  it("reconnaît '×2'", () => {
    expect(parseCommand("×2")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
  it("reconnaît 'speed slow'", () => {
    expect(parseCommand("speed slow")).toEqual({ kind: "setFlyoverSpeed", speed: 0.5 });
  });
  it("reconnaît 'speed very fast'", () => {
    expect(parseCommand("speed very fast")).toEqual({ kind: "setFlyoverSpeed", speed: 5 });
  });
  it("reconnaît 'go fast'", () => {
    expect(parseCommand("go fast")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
  it("arrondit 3 à la vitesse la plus proche (2)", () => {
    expect(parseCommand("speed to 3")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
});

// ── queryPoint ────────────────────────────────────────────────────────────────

describe("parseCommand — queryPoint", () => {
  const cases = [
    "query this point",
    "analyze this location",
    "scan this area",
    "what is the slope here",
    "what is the elevation",
    "check this spot",
    "tell me the data",
  ];
  for (const phrase of cases) {
    it(`reconnaît "${phrase}"`, () => {
      expect(parseCommand(phrase)).toEqual({ kind: "queryPoint" });
    });
  }
});

// ── unknown ───────────────────────────────────────────────────────────────────

describe("parseCommand — unknown", () => {
  it("retourne unknown pour du bruit", () => {
    expect(parseCommand("hello how are you").kind).toBe("unknown");
  });
  it("inclut le transcript", () => {
    const cmd = parseCommand("random noise");
    expect(cmd.kind).toBe("unknown");
    if (cmd.kind === "unknown") expect(cmd.transcript).toBe("random noise");
  });
  it("retourne unknown pour une chaîne vide", () => {
    expect(parseCommand("").kind).toBe("unknown");
  });
});

// ── looksLikeCommand ──────────────────────────────────────────────────────────

describe("looksLikeCommand", () => {
  it("retourne true pour 'add'", () => expect(looksLikeCommand("add")).toBe(true));
  it("retourne true pour 'abort'", () => expect(looksLikeCommand("abort")).toBe(true));
  it("retourne true pour 'flyover'", () => expect(looksLikeCommand("flyover")).toBe(true));
  it("retourne true pour 'got it'", () => expect(looksLikeCommand("got it")).toBe(true));
  it("retourne false pour du bruit", () => expect(looksLikeCommand("um")).toBe(false));
  it("est insensible à la casse", () => expect(looksLikeCommand("ADD")).toBe(true));
});
