# Justification des seuils de sécurité

Page de la tâche S1, pour le pitch. Elle explique d'où viennent les seuils du préréglage
`standard` de `config/safety.yaml`. La NASA n'a pas publié de normes définitives pour une sortie
à pied sur Mars : les valeurs ci-dessous s'appuient sur les études de la NASA pour la Lune et
sur les données des missions martiennes. Ce qui relève d'un choix du projet est signalé comme
**hypothèse du projet**. Les numéros renvoient aux sources de [jezero.md](jezero.md) et à celles
listées en bas de cette page.

| Seuil | Valeur | Rôle dans le planificateur |
| --- | --- | --- |
| Pente maximale | 20° | Au-delà, la case est interdite |
| Pente de vigilance | 10° à 20° | Case traversable mais pénalisée |
| Réserve au retour | 30 % | Le plan est refusé si la réserve à l'arrivée est plus basse |
| Bloc considéré comme obstacle | 0,5 m | Case interdite, avec un tampon de 2 m |

## Pente : 20° au plus, vigilance dès 10°

- La combinaison étudiée par la NASA pour Artemis doit permettre de marcher en montée, en
  descente et en travers d'une pente allant jusqu'à 20° [13].
- Les trajets types de ces études comportent des tronçons de 12° à 20°, et l'équipage
  d'Apollo 15 a parcouru des pentes d'environ 17° [13].
- Une étude des accès aux cratères du pôle Sud lunaire retient la même limite : tout trajet
  doit rester sous 20° [14].
- La pénalité commence à 10°, avant les tronçons de 12° des trajets types, pour que le
  planificateur préfère le terrain plat quand il existe. **Hypothèse du projet.**

Sur Mars, la gravité (0,38 g) est plus forte que sur la Lune (0,17 g), ce qui rend une pente donnée
plus fatigante. Garder la limite lunaire est donc prudent, mais pas conservateur pour la
dépense d'énergie : c'est pourquoi la vitesse et la consommation baissent aussi avec la pente
dans le modèle de marche (P3).

## Réserve : 30 % de consommables au retour

- Les études de la NASA limitent la marche à environ 2 km de l'atterrisseur, à environ 2 km/h
  sur terrain plat, et précisent que cette estimation **ne tient pas compte des pentes ni des
  blocs** [13].
- La réserve d'oxygène de secours de la combinaison ajoute environ une heure à une sortie de 6
  à 8 heures [13], soit 12 à 17 %. Elle sert aux pannes, pas aux erreurs de planification.
- La NASA ne publie pas de pourcentage de réserve pour une sortie martienne [13]. Le projet
  retient 30 % en plus du secours, pour couvrir l'incertitude du modèle de marche à 0,38 g, les
  détours imprévus et les arrêts plus longs que prévu. **Hypothèse du projet**, à présenter
  comme telle. Le préréglage `safety` monte à 40 %.

## Blocs : obstacle à partir de 0,5 m

- Au front du delta, les crues ont laissé des blocs atteignant environ 1 m [3].
- HiRISE ne voit pas tous les blocs de moins de 1,5 m, et descend à environ 1,2 m après
  déconvolution [15]. Un bloc de 0,5 m n'est donc pas visible directement : la couche
  `obstacles` de D2 le déduit de la rugosité du modèle de terrain et de la texture de l'image.
- Pour les sites d'atterrissage de Curiosity, la NASA estimait à environ 1 % la probabilité de
  rencontrer un bloc de plus de 0,6 m de haut sur la surface en jeu [15] : les blocs de cette
  taille sont rares, et les éviter coûte peu de détour.
- Le seuil de 0,5 m est la hauteur au-delà de laquelle on suppose qu'un astronaute en
  combinaison rigide doit contourner le bloc au lieu de l'enjamber. Le tampon de 2 m laisse la
  place de passer à côté avec l'incertitude de position. **Hypothèse du projet**, à valider
  avec les essais analogues.

## Sources propres à cette page

14. Peña-Asensio E., Kring D. A. et al., 2023. Étude des accès à pied aux régions ombrées en
    permanence du pôle Sud lunaire, *Acta Astronautica*. Résumé et citation de D. Kring :
    Universe Today, 24 octobre 2023.
    https://www.universetoday.com/163783/lunar-astronauts-will-need-easy-walking-trails-around-the-moons-south-pole/
15. Golombek M. et al., « Rocks », exposé au quatrième atelier des sites d'atterrissage de MSL,
    NASA. https://marsoweb.nas.nasa.gov/landingsites/msl/workshops/4th_workshop/talks/Golombek_Rocks_4th_Wkshp.pdf
