/**
 * Export et carnet de terrain (X1, EF-15) : GeoJSON et fiche imprimable du plan,
 * carnet de sortie horodaté en sol et heure locale.
 * Règle : ne jamais importer le code d'une autre fonctionnalité ; passer par le magasin
 * partagé (@/shared/store) ou par l'API (@/shared/api/client).
 */
import type { Feature } from "@/app/feature";
import { ExportPanel } from "./ExportPanel";
import { LogbookSheet } from "./LogbookSheet";
import { PlanSheet } from "./PlanSheet";

export const feature: Feature = {
  id: "export",
  panels: [{ slot: "right", order: 90, component: ExportPanel, modes: ["map"] }],
  routes: [
    { path: "/export/plan/:planId", component: PlanSheet },
    { path: "/export/logbook/:evaId", component: LogbookSheet },
  ],
};
