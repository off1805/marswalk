// Préparation des tests du front (jsdom). MapLibre et deck.gl ne sont pas rendus en test.
export {};

// MapLibre builds its worker URL from a Blob when its module loads; jsdom has no
// createObjectURL. Pure helpers that import maplibre-gl (3D camera) need it to load.
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = () => "blob:jsdom";
}
