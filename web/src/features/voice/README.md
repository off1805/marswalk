# V1 — Assistant vocal

Reconnaissance vocale et synthèse pour Marswalk. Permet à l'opérateur de donner des commandes mains-libres et de recevoir les alertes danger à voix haute.

## Architecture (principes SOLID)

```
voice/
├── types.ts                 Interfaces : VoiceCommand, RecognitionState, SynthRequest (I)
├── commandParser.ts         Parseur pur texte → commande (S + O)
├── speechRecognition.ts     Abstraction Web Speech API (S + D)
├── speechSynthesis.ts       Abstraction synthèse, BrowserSynthesizer + PiperSynthesizer (S + O + D)
├── serviceRegistry.ts       Composition root des singletons (D)
├── useSpeechQueue.ts        File de synthèse sans chevauchement (S)
├── useVoiceRecognition.ts   Hook micro → transcription (S + I)
├── useVoiceCommands.ts      Hook transcription → action magasin/API (S + D)
├── useAlertSpeaker.ts       Lecture automatique des alertes danger (S + D)
├── VoiceButton.tsx          Bouton micro avec état visible + textuel (S + I)
├── VoicePanel.tsx           Assembleur des hooks et composants (S + D)
├── voice.test.ts            Tests unitaires du parseur
└── index.ts                 Export feature, setup() via portail React
```

## Commandes reconnues

| Ce que l'opérateur dit | Commande déclenchée |
|---|---|
| « Ajoute une cible » | Mode placement de cible sur la carte |
| « Choisis la variante la plus sûre / rapide / science » | Sélection de variante via PATCH /api/plans/{id} |
| « Retour à l'habitat / base / abri » | Recalcul d'itinéraire vers l'habitat |
| « Acquitte l'alerte » | Acquittement de la première alerte active |
| « Lance le survol » | Navigation vers /3d |
| « Pause le survol » | Événement DOM f6:flyover:pause |
| « Vitesse 2 / 5 » | Événement DOM f6:flyover:speed |
| « Interroge la pente » | Mode query sur la carte |

## Voix utilisées

| Mode | Synthétiseur | Voix |
|---|---|---|
| En ligne | `PiperSynthesizer` → `/api/tts` → Piper `fr_FR-upmc-medium` | Neutre, claire, cohérente |
| Hors ligne / repli | `BrowserSynthesizer` → `window.speechSynthesis` | Thomas (macOS), Hortense (Windows) |

## Lecture automatique des alertes

`useAlertSpeaker` s'abonne au cache TanStack Query sous `queryKeys.alerts(evaId)`.
Dès qu'une nouvelle alerte non acquittée apparaît, elle est lue à voix haute.
Les alertes `danger` interrompent la synthèse en cours (priorité `high`).

## Contrainte de registry

`registry.ts` est gelé (T00) et ne liste pas V1. `setup()` monte `VoicePanel` via
un portail React dans un div `#v1-voice-host` injecté dans `document.body`.
Demande de changement : `tasks/change-requests/V1-registry-voice.md`.

## Critères d'acceptation

| Critère | Démonstration |
|---|---|
| « Retour à l'habitat » déclenche le recalcul | `useVoiceCommands` → `POST /api/eva/{id}/obstacles` → invalidation plans |
| Alerte danger lue < 1 s | `useAlertSpeaker` → abonnement synchrone au cache TanStack Query |
| Acquittement vocal en 1 action | `parseCommand("acquitte l'alerte")` → `POST /api/alerts/{id}/ack` |
| Bouton avec état visible et textuel | `VoiceButton` : icône + animation + aria-label (ENF-06) |
| Hors ligne : reconnaissance désactivée, synthèse active | `BrowserSpeechRecognizer.isSupported()` → état `unsupported` si pas de réseau |
