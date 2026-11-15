/**
 * Choix du site affiché. Le site de départ est, dans l'ordre : `?site=` dans l'adresse, le
 * dernier site choisi sur ce navigateur, `VITE_DEFAULT_SITE`, puis Jezero s'il est installé,
 * sinon le premier site réel de `GET /api/sites`, sinon le site fictif.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, type Schemas } from "@/shared/api/client";
import { queryKeys } from "@/shared/queryKeys";
import { useShared } from "@/shared/store";

const STORAGE_KEY = "marswalk.site";
const PREFERRED_SITE = "jezero";

export function useSites() {
  return useQuery({
    queryKey: queryKeys.sites(),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites");
      if (error || !data) throw new Error("Liste des sites indisponible");
      return data as Schemas["SiteSummary"][];
    },
    staleTime: Infinity,
  });
}

function readStored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function remember(siteId: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, siteId);
  } catch {
    /* stockage indisponible : le choix vaut pour la session */
  }
}

/** Choisit le site de départ parmi les sites servis par l'API. */
export function pickSite(available: string[], wanted: (string | null | undefined)[]): string | null {
  for (const id of wanted) if (id && available.includes(id)) return id;
  if (available.includes(PREFERRED_SITE)) return PREFERRED_SITE;
  return available.find((id) => id !== "fictif") ?? available[0] ?? null;
}

/** Applique le site de départ une fois la liste des sites connue. */
export function SiteSync() {
  const sites = useSites();
  const setSiteId = useShared((s) => s.setSiteId);
  useEffect(() => {
    if (!sites.data) return;
    const fromUrl = new URLSearchParams(window.location.search).get("site");
    const env = import.meta.env.VITE_DEFAULT_SITE as string | undefined;
    const chosen = pickSite(
      sites.data.map((s) => s.site_id),
      [fromUrl, readStored(), env],
    );
    if (chosen) setSiteId(chosen);
  }, [sites.data, setSiteId]);
  return null;
}

/** Liste déroulante de la barre du haut (masquée s'il n'y a qu'un site). */
export function SitePicker() {
  const sites = useSites();
  const siteId = useShared((s) => s.siteId);
  const setSiteId = useShared((s) => s.setSiteId);
  if (!sites.data || sites.data.length < 2) return null;
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="sr-only">Site</span>
      <select
        aria-label="Site"
        value={siteId}
        onChange={(e) => {
          const id = e.target.value;
          remember(id);
          const url = new URL(window.location.href);
          url.searchParams.set("site", id);
          window.history.replaceState(null, "", url);
          setSiteId(id);
        }}
        className="rounded border border-[var(--border)] bg-[var(--surface)] px-1"
      >
        {sites.data.map((s) => (
          <option key={s.site_id} value={s.site_id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
