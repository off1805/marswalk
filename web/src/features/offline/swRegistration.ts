/**
 * Enregistrement du service worker Workbox.
 *
 * Appelé par `feature.setup()` dans `main.tsx` avant le premier rendu.
 *
 * Principe S : enregistrer le service worker est la seule responsabilité
 * de ce module. Il ne connaît ni l'UI ni la file d'attente.
 *
 * Principe D : `Workbox` est importé dynamiquement pour ne pas alourdir
 * le bundle initial — il n'est chargé que si le navigateur supporte
 * les service workers.
 */

/** Enregistre le service worker Workbox si l'environnement le supporte. */
export async function registerServiceWorker(): Promise<void> {
  // En mode mock (développement), MSW utilise déjà un service worker.
  // On n'enregistre pas le SW de production pour éviter les conflits.
  if (import.meta.env.VITE_MOCK) return;

  // Les service workers demandent HTTPS (ou localhost).
  if (!("serviceWorker" in navigator)) return;

  try {
    const { Workbox } = await import("workbox-window");
    const wb = new Workbox("/sw.js");

    // En production, on active silencieusement la nouvelle version
    // sans demander de rechargement — comportement conservateur.
    wb.addEventListener("waiting", () => {
      wb.messageSkipWaiting();
    });

    await wb.register();
  } catch (err) {
    // Ne pas bloquer le démarrage si le SW échoue à s'enregistrer.
    console.warn("[F7] Service worker non enregistré :", err);
  }
}
