# Demande de changement : ajout de planner/README.md au périmètre P3

**Tâche demandeuse :** P3 — Modèle de marche, budgets et retour garanti  
**Fichier cible :** `tasks/ownership.yaml`  
**Propriétaire :** T00

## Contexte

La branche `task/P3-marche-budgets` crée `planner/README.md`, un fichier de documentation
du paquet `marswalk-planner` introduisant les tâches P1, P2 et P3 avec un focus détaillé
sur P3 (modèle de vitesse, consommables, champ de retour).

Ce fichier n'est pas listé dans les chemins de P3 dans `tasks/ownership.yaml`, ce qui
bloque le contrôle d'ownership en CI.

## Modification demandée

Dans la section `tasks.P3.paths` de `tasks/ownership.yaml`, ajouter :

```yaml
- planner/README.md
```

## Justification

`planner/README.md` est un livrable de documentation de la tâche P3 : il documente les
interfaces et le modèle scientifique implémentés par P3. Il n'empiète sur aucun autre
périmètre et ne modifie aucune interface partagée. Les sections P1 et P2 du README se
limitent à lister les fichiers déjà existants sans les modifier.
