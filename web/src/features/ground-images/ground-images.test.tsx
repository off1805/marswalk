import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import groundImages from "@contracts/examples/ground_images.json";
import manifest from "@contracts/examples/site_manifest.json";
import targets from "@contracts/examples/targets.json";
import { feature } from ".";
import { nearestImages, thumbSrc, toImages, useViewer, type GroundImage } from "./data";
import { ImageViewer } from "./ImageViewer";
import { groundImageLayers } from "./layers";
import { NearbyImages } from "./NearbyImages";
import type { MapContext } from "@/app/feature";
import { api, type FeatureCollection, type LonLat, type SiteManifest } from "@/shared/api/client";
import { useShared } from "@/shared/store";

const fc = groundImages as unknown as FeatureCollection;
const images = toImages(fc);

describe("données", () => {
  it("lit l'index : chaque image a sol, instrument et identifiant", () => {
    expect(images.length).toBe(fc.features!.length);
    for (const i of images) {
      expect(typeof i.props.sol).toBe("number");
      expect(i.props.instrument).toBeTruthy();
      expect(i.props.image_id).toBeTruthy();
    }
  });

  it("préfère une vignette absolue, sinon le lien distant du JPL", () => {
    const base = { image_id: "X", sol: 1, instrument: "MCZ_LEFT" };
    expect(thumbSrc({ ...base, thumb: "thumbs/X.jpg", thumb_url: "https://jpl/x.jpg" })).toBe("https://jpl/x.jpg");
    expect(thumbSrc({ ...base, thumb: "https://jpl/y.jpg" })).toBe("https://jpl/y.jpg");
    expect(thumbSrc({ ...base, thumb: null })).toBeNull();
  });

  it("classe les images de la plus proche à la plus lointaine", () => {
    const p = images[2]!.position;
    const near = nearestImages(images, p, 3);
    expect(near[0]!.image.id).toBe(images[2]!.id);
    expect(near[0]!.distance).toBe(0);
    expect(near.map((n) => n.distance)).toEqual([...near.map((n) => n.distance)].sort((a, b) => a - b));
  });
});

describe("carte", () => {
  const ctx = (layers: Record<string, { visible: boolean; opacity: number }> = {}): MapContext => ({
    siteId: "fictif",
    manifest: manifest as unknown as SiteManifest,
    zoom: 15,
    state: { ...useShared.getState(), layers },
  });

  it("ajoute le trajet du rover et les points de prise de vue, masquables", () => {
    expect(groundImageLayers(ctx()).map((l) => l.id)).toEqual(["g1-rover-traverse", "g1-ground-images"]);
    const hidden = ctx({ ground_images: { visible: false, opacity: 1 } });
    expect(groundImageLayers(hidden).map((l) => l.id)).toEqual(["g1-rover-traverse"]);
  });

  it("un clic sur un point ouvre la visionneuse", () => {
    const layer = groundImageLayers(ctx()).find((l) => l.id === "g1-ground-images")!;
    const onClick = layer.props.onClick as (info: { object: GroundImage }) => boolean;
    onClick({ object: images[0]! });
    expect(useViewer.getState().selected?.id).toBe(images[0]!.id);
    useViewer.getState().open(null);
  });
});

describe("panneaux", () => {
  beforeEach(() => {
    vi.spyOn(api, "GET").mockImplementation((async (path: string) => {
      const data: Record<string, unknown> = {
        "/api/sites/{site_id}/ground-images": groundImages,
        "/api/sites/{site_id}/targets": targets,
      };
      return { data: data[path], error: undefined, response: new Response() };
    }) as never);
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    useViewer.getState().open(null);
    useShared.getState().selectTarget(null);
  });

  const wrap = (node: React.ReactNode) =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        {node}
      </QueryClientProvider>,
    );

  it("la visionneuse montre sol, instrument et identifiant", () => {
    useViewer.getState().open(images[1]!);
    wrap(<ImageViewer />);
    const p = images[1]!.props;
    expect(screen.getByText(new RegExp(`Sol ${p.sol}`))).toBeTruthy();
    expect(screen.getByText(`Instrument : ${p.instrument}`)).toBeTruthy();
    expect(screen.getByText(`Identifiant : ${p.image_id}`)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Fermer la visionneuse" }));
    expect(useViewer.getState().selected).toBeNull();
  });

  it("la fiche d'une cible propose les images les plus proches", async () => {
    const target = (targets as unknown as { id: string; name: string; position: LonLat }[])[0]!;
    useShared.getState().selectTarget(target.id);
    wrap(<NearbyImages />);
    const list = await screen.findByRole("list", { name: `Images proches de ${target.name}` });
    const items = list.querySelectorAll("li");
    expect(items.length).toBe(4);
    const expected = nearestImages(images, target.position, 4)[0]!.image;
    fireEvent.click(screen.getByRole("button", { name: `Ouvrir ${expected.props.image_id}` }));
    expect(useViewer.getState().selected?.id).toBe(expected.id);
  });
});

describe("fonctionnalité", () => {
  it("place la visionneuse sur la carte et le panneau à droite", () => {
    expect(feature.panels.map((p) => p.slot).sort()).toEqual(["map-overlay", "right"]);
    expect(feature.mapLayers).toBeDefined();
  });
});
