/**
 * Registre des fonctionnalités (gelé avec contrats-v2). Toutes les fonctionnalités y sont
 * listées dès T00 ; chaque tâche F remplit son module sans toucher à ce fichier.
 *
 * Modification contracts/add-voice-to-registry : ajout de V1 (assistant vocal).
 * Demande de changement : tasks/change-requests/V1-registry-voice.md
 */
import type { Feature } from "./feature";
import { feature as exportFeature } from "@/features/export";
import { feature as groundImages } from "@/features/ground-images";
import { feature as map } from "@/features/map";
import { feature as offline } from "@/features/offline";
import { feature as profile } from "@/features/profile";
import { feature as safety } from "@/features/safety";
import { feature as targets } from "@/features/targets";
import { feature as terrain3d } from "@/features/terrain3d";
import { feature as voice } from "@/features/voice";

export const registry: readonly Feature[] = [
  map,          // F1
  targets,      // F2
  profile,      // F3
  safety,       // F4
  terrain3d,    // F6
  offline,      // F7
  groundImages, // G1
  exportFeature, // X1
  voice,        // V1
];
