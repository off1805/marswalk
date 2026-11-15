/**
 * Tests de la feature V1 — assistant vocal.
 *
 * On teste les modules purs (sans navigateur, sans React) :
 *   commandParser.ts  parseCommand, looksLikeCommand
 *
 * Les hooks React (useVoiceRecognition, useVoiceCommands, useAlertSpeaker)
 * sont couverts par l'intégration manuelle en mode dev:mock.
 */
import { describe, it, expect } from "vitest";
import { parseCommand, looksLikeCommand } from "./commandParser";

// ── parseCommand ──────────────────────────────────────────────────────────────

describe("parseCommand — ajouter une cible", () => {
  it("reconnaît 'ajoute une cible'", () => {
    expect(parseCommand("ajoute une cible")).toEqual({ kind: "addTarget" });
  });
  it("reconnaît 'ajouter une cible ici'", () => {
    expect(parseCommand("ajouter une cible ici")).toEqual({ kind: "addTarget" });
  });
  it("reconnaît 'ajoute cible' sans article", () => {
    expect(parseCommand("ajoute cible")).toEqual({ kind: "addTarget" });
  });
});

describe("parseCommand — sélectionner une variante", () => {
  it("reconnaît 'choisis la variante la plus sûre'", () => {
    const cmd = parseCommand("choisis la variante la plus sûre");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "safest" });
  });
  it("reconnaît 'prends la variante la plus rapide'", () => {
    const cmd = parseCommand("prends la variante la plus rapide");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "fastest" });
  });
  it("reconnaît 'sélectionne la variante science'", () => {
    const cmd = parseCommand("sélectionne la variante science");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "science" });
  });
  it("reconnaît 'variante sûre' (forme courte)", () => {
    const cmd = parseCommand("variante sûre");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "safest" });
  });
  it("reconnaît 'variante rapide' (forme courte)", () => {
    const cmd = parseCommand("variante rapide");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "fastest" });
  });
  it("reconnaît 'variante science' (forme courte)", () => {
    const cmd = parseCommand("variante science");
    expect(cmd).toEqual({ kind: "selectVariant", variant: "science" });
  });
});

describe("parseCommand — urgences", () => {
  it("reconnaît 'retour à l'habitat'", () => {
    expect(parseCommand("retour à l'habitat")).toEqual({ kind: "returnToHabitat" });
  });
  it("reconnaît 'retour à la base'", () => {
    expect(parseCommand("retour à la base")).toEqual({ kind: "returnToHabitat" });
  });
  it("reconnaît 'retour à l'abri'", () => {
    expect(parseCommand("retour à l'abri")).toEqual({ kind: "returnToHabitat" });
  });
  it("reconnaît 'acquitte l'alerte'", () => {
    expect(parseCommand("acquitte l'alerte")).toEqual({ kind: "acknowledgeAlert" });
  });
  it("reconnaît 'acquitter l'alerte'", () => {
    expect(parseCommand("acquitter l'alerte")).toEqual({ kind: "acknowledgeAlert" });
  });
});

describe("parseCommand — survol 3D", () => {
  it("reconnaît 'lance le survol'", () => {
    expect(parseCommand("lance le survol")).toEqual({ kind: "startFlyover" });
  });
  it("reconnaît 'démarre le survol'", () => {
    expect(parseCommand("démarre le survol")).toEqual({ kind: "startFlyover" });
  });
  it("reconnaît 'pause le survol'", () => {
    expect(parseCommand("pause le survol")).toEqual({ kind: "pauseFlyover" });
  });
  it("reconnaît 'arrête le survol'", () => {
    expect(parseCommand("arrête le survol")).toEqual({ kind: "pauseFlyover" });
  });
  it("reconnaît 'vitesse 2'", () => {
    expect(parseCommand("vitesse 2")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
  it("reconnaît 'accélère à 5'", () => {
    expect(parseCommand("accélère à 5")).toEqual({ kind: "setFlyoverSpeed", speed: 5 });
  });
  it("arrondit '3' à la vitesse la plus proche (2)", () => {
    expect(parseCommand("vitesse 3")).toEqual({ kind: "setFlyoverSpeed", speed: 2 });
  });
});

describe("parseCommand — interrogation", () => {
  it("reconnaît 'interroge la pente'", () => {
    expect(parseCommand("interroge la pente")).toEqual({ kind: "queryPoint" });
  });
  it("reconnaît 'quelle est la pente'", () => {
    expect(parseCommand("quelle est la pente")).toEqual({ kind: "queryPoint" });
  });
});

describe("parseCommand — inconnu", () => {
  it("retourne unknown pour un texte sans commande", () => {
    const cmd = parseCommand("bonjour comment ça va");
    expect(cmd.kind).toBe("unknown");
  });
  it("inclut le transcript dans la réponse unknown", () => {
    const cmd = parseCommand("texte quelconque");
    expect(cmd.kind).toBe("unknown");
    if (cmd.kind === "unknown") {
      expect(cmd.transcript).toBe("texte quelconque");
    }
  });
  it("retourne unknown pour une chaîne vide", () => {
    expect(parseCommand("").kind).toBe("unknown");
  });
});

// ── looksLikeCommand ──────────────────────────────────────────────────────────

describe("looksLikeCommand", () => {
  it("retourne true pour 'ajoute une'", () => {
    expect(looksLikeCommand("ajoute une")).toBe(true);
  });
  it("retourne true pour 'retour'", () => {
    expect(looksLikeCommand("retour")).toBe(true);
  });
  it("retourne true pour 'survol'", () => {
    expect(looksLikeCommand("survol")).toBe(true);
  });
  it("retourne false pour du bruit sans mot-clé", () => {
    expect(looksLikeCommand("euh")).toBe(false);
  });
  it("est insensible à la casse", () => {
    expect(looksLikeCommand("AJOUTE")).toBe(true);
  });
});
