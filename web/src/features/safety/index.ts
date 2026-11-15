/**
 * Panneau sécurité et conditions (F4) : bandeau d'alertes avec acquittement, jauges,
 * comptes à rebours, horloge martienne, météo et météo spatiale, réglage des seuils.
 * Règle : ne jamais importer le code d'une autre fonctionnalité ; passer par le magasin
 * partagé (@/shared/store) ou par l'API (@/shared/api/client).
 */
import type { Feature } from "@/app/feature";
import { AlertBanner } from "./AlertBanner";
import { ConditionsPanel } from "./ConditionsPanel";
import { SafetyPanel } from "./SafetyPanel";
import { ThresholdsPanel } from "./ThresholdsPanel";

export const feature: Feature = {
  id: "safety",
  panels: [
    { slot: "top-banner", order: 10, component: AlertBanner },
    { slot: "right", order: 5, component: SafetyPanel },
    { slot: "right", order: 30, component: ConditionsPanel },
    { slot: "right", order: 35, component: ThresholdsPanel },
  ],
  routes: [],
};
