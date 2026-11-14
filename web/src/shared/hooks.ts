/** Requêtes partagées par la coquille et les fonctionnalités. */
import { useQuery } from "@tanstack/react-query";
import { api, type SiteManifest } from "./api/client";
import { queryKeys } from "./queryKeys";
import { useShared } from "./store";

export function useSiteManifest() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.site(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sites/{site_id}", {
        params: { path: { site_id: siteId } },
      });
      if (error || !data) throw new Error(`Site ${siteId} indisponible`);
      return data as SiteManifest;
    },
    staleTime: Infinity,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/health");
      if (error || !data) throw new Error("API indisponible");
      return data;
    },
    refetchInterval: 30_000,
  });
}

export function useMarsClock() {
  const siteId = useShared((s) => s.siteId);
  return useQuery({
    queryKey: queryKeys.time(siteId),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/time", { params: { query: { site_id: siteId } } });
      if (error || !data) throw new Error("Heure martienne indisponible");
      return data;
    },
    refetchInterval: 60_000,
  });
}
