/**
 * Greffons Vite du mode hors ligne (F7), branchés par web/vite.config.ts.
 *
 * Configure `vite-plugin-pwa` avec Workbox pour :
 *   - Générer `dist/sw.js` au build (InjectManifest ou GenerateSW).
 *   - Pré-cacher les ressources statiques de l'application (shell).
 *   - Laisser les routes API (`/api/**`, `/tiles/**`) en network-first.
 *   - Rendre l'application installable (manifest PWA).
 *
 * En mode `mock` (développement sans API), le plugin n'est pas ajouté
 * pour ne pas interférer avec le service worker de MSW.
 *
 * Principe S : ce fichier ne configure que le plugin Vite. L'enregistrement
 * du service worker côté client est dans `swRegistration.ts`.
 */
import type { PluginOption } from "vite";

export function offlineVitePlugins(): PluginOption[] {
  // En mode mock, MSW utilise déjà un service worker — on n'en ajoute pas un second.
  if (process.env["VITE_MOCK"] === "1") return [];

  // Import dynamique pour éviter d'alourdir le bundle en mode mock
  // (vite-plugin-pwa est une devDependency, pas disponible en production Node)
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { VitePWA } = require("vite-plugin-pwa") as {
      VitePWA: (options: Record<string, unknown>) => PluginOption;
    };

    return [
      VitePWA({
        registerType: "prompt", // On contrôle l'activation via swRegistration.ts
        injectRegister: null,   // Pas d'auto-enregistrement : F7 le fait dans setup()
        strategies: "generateSW",
        workbox: {
          // Pré-cacher le shell de l'application
          globPatterns: ["**/*.{js,css,html,woff2}"],
          // Exclure les fichiers de développement MSW
          globIgnores: ["mockServiceWorker.js"],
          // Routes réseau d'abord (toujours fraîches si disponibles)
          runtimeCaching: [
            {
              urlPattern: /^\/api\/.*/,
              handler: "NetworkFirst",
              options: {
                cacheName: "marswalk-api-v1",
                expiration: { maxEntries: 200, maxAgeSeconds: 86_400 },
              },
            },
            {
              urlPattern: /^\/tiles\/.*/,
              handler: "CacheFirst",
              options: {
                cacheName: "marswalk-tiles-v1",
                expiration: {
                  maxEntries: 5000,
                  maxAgeSeconds: 7 * 86_400,
                },
              },
            },
          ],
        },
        manifest: {
          name: "Marswalk",
          short_name: "Marswalk",
          description:
            "Planification de sorties à pied sur Mars — cratère Jezero",
          theme_color: "#0b0d10",
          background_color: "#0b0d10",
          display: "standalone",
          icons: [
            {
              src: "/icon-192.png",
              sizes: "192x192",
              type: "image/png",
            },
            {
              src: "/icon-512.png",
              sizes: "512x512",
              type: "image/png",
            },
          ],
        },
      }),
    ];
  } catch {
    // vite-plugin-pwa non disponible (CI léger, test) : ne pas bloquer
    return [];
  }
}
