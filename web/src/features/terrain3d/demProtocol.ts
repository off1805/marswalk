/**
 * Elevation tiles for the 3D terrain, cleaned in the browser before MapLibre meshes them.
 *
 * The site's terrain-RGB tiles (Mapbox encoding) carry absolute Mars elevations, around
 * -2,600 m, and their pixels outside the site are transparent, which decodes to
 * -10,000 m. Meshed as is, the site sits on a "cube" with walls dropping thousands of
 * metres at its edges, and vertical exaggeration multiplies the absolute depth rather
 * than the relief.
 *
 * The `mwdem://` protocol fetches each tile, re-expresses every pixel relative to the
 * site's reference elevation, and gives no-data pixels (and missing tiles) that
 * reference. The ground then continues flat beyond the site, exaggeration scales only
 * the relief, and the camera works near zero altitude.
 *
 * Tiles entirely outside the site are answered locally with a flat tile, without a
 * request: the ground and its shading then continue seamlessly in every direction.
 *
 * URL form: `mwdem://<referenceElevationM>@<w>,<s>,<e>,<n>@<tile path with {z}/{x}/{y}>`.
 */
import maplibregl from "maplibre-gl";

export const DEM_SCHEME = "mwdem";
const SIZE = 256;

/** Mapbox terrain-RGB: elevation = -10 000 + (R·256² + G·256 + B) · 0.1. */
export function decodeMapbox(r: number, g: number, b: number): number {
  return -10_000 + (r * 65_536 + g * 256 + b) * 0.1;
}

/** Inverse of `decodeMapbox`, clamped to the encodable range. */
export function encodeMapbox(elevationM: number): [number, number, number] {
  const v = Math.max(0, Math.min(16_777_215, Math.round((elevationM + 10_000) * 10)));
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

/**
 * Rewrites RGBA terrain pixels in place: elevation relative to `referenceM`, no-data
 * (transparent) pixels set to the reference.
 */
export function relativize(px: Uint8ClampedArray, referenceM: number): void {
  for (let i = 0; i < px.length; i += 4) {
    const rel = px[i + 3]! < 128 ? 0 : decodeMapbox(px[i]!, px[i + 1]!, px[i + 2]!) - referenceM;
    const [r, g, b] = encodeMapbox(rel);
    px[i] = r;
    px[i + 1] = g;
    px[i + 2] = b;
    px[i + 3] = 255;
  }
}

export function demTileUrl(
  referenceM: number,
  bbox: [number, number, number, number],
  pathTemplate: string,
): string {
  return `${DEM_SCHEME}://${referenceM.toFixed(1)}@${bbox.join(",")}@${pathTemplate}`;
}

/** Lon/lat bounds [w, s, e, n] of a WebMercator tile. */
export function tileBounds(z: number, x: number, y: number): [number, number, number, number] {
  const n = 2 ** z;
  const lon = (i: number) => (i / n) * 360 - 180;
  const lat = (j: number) => (Math.atan(Math.sinh(Math.PI * (1 - (2 * j) / n))) * 180) / Math.PI;
  return [lon(x), lat(y + 1), lon(x + 1), lat(y)];
}

function intersects(a: [number, number, number, number], b: number[]): boolean {
  return a[0] < b[2]! && a[2] > b[0]! && a[1] < b[3]! && a[3] > b[1]!;
}

let flatTile: Promise<ArrayBuffer> | null = null;

async function encodePng(canvas: OffscreenCanvas): Promise<ArrayBuffer> {
  const blob = await canvas.convertToBlob({ type: "image/png" });
  return blob.arrayBuffer();
}

/** A tile at the reference elevation, for tiles the server does not have. */
function flat(): Promise<ArrayBuffer> {
  flatTile ??= (async () => {
    const canvas = new OffscreenCanvas(SIZE, SIZE);
    const ctx = canvas.getContext("2d")!;
    const [r, g, b] = encodeMapbox(0);
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(0, 0, SIZE, SIZE);
    return encodePng(canvas);
  })();
  return flatTile;
}

async function loadTile(url: string, signal: AbortSignal): Promise<ArrayBuffer> {
  const [refText, bboxText, ...rest] = url.slice(DEM_SCHEME.length + 3).split("@");
  const referenceM = Number(refText);
  const site = bboxText!.split(",").map(Number);
  const path = rest.join("@");
  const zxy = /\/(\d+)\/(\d+)\/(\d+)\.\w+$/.exec(path);
  if (zxy && !intersects(tileBounds(+zxy[1]!, +zxy[2]!, +zxy[3]!), site)) return flat();
  const res = await fetch(path, { signal });
  if (!res.ok) return flat();
  const bitmap = await createImageBitmap(await res.blob(), {
    premultiplyAlpha: "none",
    colorSpaceConversion: "none",
  });
  const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  relativize(image.data, referenceM);
  ctx.putImageData(image, 0, 0);
  return encodePng(canvas);
}

let registered = false;

/** Registers the protocol once per page. */
export function registerDemProtocol(): void {
  if (registered) return;
  registered = true;
  maplibregl.addProtocol(DEM_SCHEME, async (params, abort) => ({
    data: await loadTile(params.url, abort.signal),
  }));
}

function tileXY(lon: number, lat: number, z: number): [number, number] {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.asinh(Math.tan((lat * Math.PI) / 180)) / Math.PI) / 2) * n);
  return [x, y];
}

/**
 * Median elevation of the site, measured on its coarsest terrain tiles. Used as the
 * reference: the plain around the site sits at this height, so the site's edges meet
 * it with the smallest possible step.
 */
export async function measureReferenceElevation(
  pathTemplate: string,
  bbox: [number, number, number, number],
  zoom: number,
): Promise<number | null> {
  const [w, s, e, n] = bbox;
  const [x0, y0] = tileXY(w, n, zoom);
  const [x1, y1] = tileXY(e, s, zoom);
  const values: number[] = [];
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      const url = pathTemplate.replace("{z}", String(zoom)).replace("{x}", String(x)).replace("{y}", String(y));
      const res = await fetch(url);
      if (!res.ok) continue;
      const bitmap = await createImageBitmap(await res.blob(), { premultiplyAlpha: "none", colorSpaceConversion: "none" });
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(bitmap, 0, 0);
      bitmap.close();
      const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 0; i < px.length; i += 16) {
        if (px[i + 3]! >= 128) values.push(decodeMapbox(px[i]!, px[i + 1]!, px[i + 2]!));
      }
    }
  }
  if (values.length === 0) return null;
  values.sort((a, b) => a - b);
  return values[Math.floor(values.length / 2)]!;
}
