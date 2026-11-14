# Pourquoi Jezero : objectif scientifique de la sortie

Page de la tâche S1, à valider par l'équipe. Chaque affirmation renvoie à une source numérotée,
listée en bas de page. Ce qui relève d'un choix du projet, et non d'une source, est signalé
comme **hypothèse du projet**.

## En une phrase

Jezero est un ancien lac de cratère dont le delta a piégé des argiles, des carbonates et de la
matière organique, et dont le plancher porte des roches ignées altérées par l'eau. C'est le
seul endroit de Mars où un rover a déjà prélevé et mis en dépôt des échantillons, ce qui en fait
un site où des astronautes peuvent reprendre le travail là où Perseverance s'est arrêté.

## Le site

- Jezero est un cratère de 45 km de diamètre, vers 18° N et 77° E, au bord ouest d'Isidis
  Planitia. Il a contenu un lac il y a environ 3,5 milliards d'années, alimenté par une rivière
  qui y a construit un delta [1].
- Perseverance s'est posé le 18 février 2021 au lieu nommé Octavia E. Butler Landing, vers
  18,44° N et 77,45° E [2], à un peu plus de 1,6 km du front du delta occidental [3].
- Le site a été choisi pour son potentiel astrobiologique : l'eau et les sédiments ont pu
  préserver des molécules organiques et d'autres traces d'une vie ancienne, et certaines zones
  semblent riches en carbonates, qui conservent des fossiles sur Terre [1].

## Ce que les orbiteurs ont vu

- **Argiles du delta.** Les données de Mars Reconnaissance Orbiter montrent des sédiments
  fluvio-lacustres riches en argiles : les deux deltas et la couche la plus basse observée
  contiennent des smectites ferro-magnésiennes, venues du bassin versant de Nili Fossae. Les
  auteurs jugent ce cadre deltaïque et ces argiles favorables à la préservation de matière
  organique [4].
- **Carbonates et olivine.** Les spectres CRISM montrent des smectites Fe/Mg, des carbonates
  magnésiens et de l'olivine dans le delta occidental, et un mélange de carbonates et d'olivine
  dans le delta nord. Ces minéraux semblent avoir été transportés depuis le bassin versant [5].
- **Carbonates de bordure.** Une bande de carbonates longe la bordure interne du cratère près du
  delta occidental et de l'entrée de la rivière. Ils pourraient s'être formés dans le lac, près
  du rivage, comme les microbialites terrestres [6]. Cette bande se trouve hors de l'emprise de
  5 × 5 km retenue pour la démonstration.

## Ce que Perseverance a mesuré et prélevé

- **Le delta est bien un delta.** Les images de Mastcam-Z et de SuperCam montrent, sur le front
  du delta et sur la butte isolée de Kodiak, des couches inclinées déposées par une rivière
  dans un lac. Au sommet, des blocs atteignant environ 1 m, venus de l'extérieur du cratère, ont
  été apportés par des crues tardives [3].
- **Le plancher est igné, puis altéré.** L'unité Séítah est une roche ignée grenue riche en
  olivine, formée à la base d'un corps magmatique (cumulat). Elle porte des carbonates Fe-Mg aux
  joints de grains, déposés par une eau riche en CO₂. L'unité Máaz la recouvre. Des sulfates et
  des perchlorates ont ensuite été déposés par une saumure qui s'évaporait [7].
- **De la matière organique.** SHERLOC a détecté des signaux organiques sur le plancher,
  associés à des minéraux d'altération (carbonates, sulfates) [8]. Au front du delta, la roche
  Wildcat Ridge, une boue fine déposée dans un lac salé en cours d'évaporation, a donné les
  détections organiques les plus abondantes de la mission en 2022, liées à des sulfates. Deux
  carottes y ont été prélevées [9].
- **Un dépôt d'échantillons.** Fin 2022, le rover a posé 10 tubes au lieu dit Three Forks, sur
  un terrain plat au pied du delta, en zigzag, chaque tube à 5 à 15 m du suivant [10].
- **Une biosignature possible.** En 2024, au nord de Neretva Vallis, la roche Cheyava Falls a
  livré la carotte Sapphire Canyon. Ses taches portent de la vivianite et de la greigite, deux
  minéraux que la vie peut produire, sans que ce soit la seule explication. C'est l'une des 27
  carottes de roche prélevées depuis 2021 [11, 12]. Cette zone est elle aussi hors de l'emprise
  de démonstration.

## Ce qu'un humain apporterait de plus qu'un rover

- **Couvrir plus de terrain en une sortie.** La NASA étudie des sorties à pied jusqu'à environ
  2 km de l'atterrisseur, à environ 2 km/h sur terrain plat, pendant 6 à 8 heures [13]. Les
  quatre cibles proposées sont à moins de 2,2 km du site d'atterrissage, à la limite de ce rayon.
- **Choisir les échantillons sur place.** Le rover n'a que 27 carottes de roche en plus de
  quatre ans [12]. Un géologue en scaphandre peut comparer plusieurs affleurements dans la même
  sortie et ne prélever que les meilleurs. **Hypothèse du projet**, appuyée par l'expérience
  Apollo citée dans [13].
- **Reprendre les tubes.** Le dépôt de Three Forks [10] montre que des échantillons attendent
  déjà sur place. Une sortie humaine peut les inspecter et les compléter par des prélèvements
  choisis à la main.

## Emprise de démonstration et cibles

L'emprise réelle de Jezero (5 × 5 km) est définie par D1. Les cibles proposées
(`config/sites/jezero/targets-seed.geojson`) tiennent dans un carré centré vers 18,436° N et
77,430° E, entre le site d'atterrissage et le front du delta.

| Cible | Objectif | Couche d'appui | Sources |
| --- | --- | --- | --- |
| J1 Front du delta (Wildcat Ridge) | Boues lacustres à sulfates et matière organique | `crism_minerals`, `hirise_vis` | [4, 5, 9] |
| J2 Séítah | Cumulat à olivine et carbonates d'altération | `crism_minerals`, `thermal_inertia` | [5, 7] |
| J3 Contact Séítah et Máaz | Ordre de mise en place des deux unités ignées | `hirise_vis`, `slope` | [7, 8] |
| J4 Kodiak et blocs de crue | Couches du delta et blocs apportés par les crues | `hirise_vis`, `obstacles` | [3] |

**Les positions sont approximatives** (incertitude de quelques centaines de mètres). Elles sont
déduites des distances publiées au site d'atterrissage, car les cartes de traverse de la NASA ne
sont pas joignables depuis l'environnement de développement. Il faut les recaler sur HiRISE
une fois que D1 a produit `hirise_vis` (propriété `position_note` de chaque cible).

Les seuils de sécurité utilisés pour planifier ces sorties sont justifiés dans
[seuils-securite.md](seuils-securite.md).

## Sources

1. NASA JPL, *Mars 2020 Perseverance Launch Press Kit*, « Landing Site ».
   https://www.jpl.nasa.gov/news/press_kits/mars_2020/landing/mission/landing_site
2. NASA, « Welcome to Octavia E. Butler Landing », 2021.
   https://www.nasa.gov/image-article/welcome-octavia-e-butler-landing/
3. Mangold N., Gupta S., Gasnault O. et al., 2021. « Perseverance rover reveals an ancient
   delta-lake system and flood deposits at Jezero crater, Mars ». *Science* 374.
   https://doi.org/10.1126/science.abl4051
4. Ehlmann B. L., Mustard J. F., Fassett C. I. et al., 2008. « Clay minerals in delta deposits
   and organic preservation potential on Mars ». *Nature Geoscience* 1, 355–358.
   https://doi.org/10.1038/ngeo207
5. Goudge T. A., Mustard J. F., Head J. W., Fassett C. I., Wiseman S. M., 2015. « Assessing the
   mineralogy of the watershed and fan deposits of the Jezero crater paleolake system, Mars ».
   *JGR Planets* 120, 775–808. https://doi.org/10.1002/2014JE004782
6. Horgan B. H. N., Anderson R. B., Dromart G., Amador E. S., Rice M. S., 2020. « The mineral
   diversity of Jezero crater: Evidence for possible lacustrine carbonates on Mars ». *Icarus*
   339. https://doi.org/10.1016/j.icarus.2019.113526
7. Farley K. A., Stack K. M., Shuster D. L. et al., 2022. « Aqueously altered igneous rocks
   sampled on the floor of Jezero crater, Mars ». *Science* 377.
   https://doi.org/10.1126/science.abo2196
8. Sharma S., Roppel R. D., Murphy A. E. et al., 2023. « Diverse organic-mineral associations in
   Jezero crater, Mars ». *Nature* 619, 724–732. https://doi.org/10.1038/s41586-023-06143-z
9. NASA JPL, « NASA's Perseverance Rover Investigates Geologically Rich Mars Terrain »,
   15 septembre 2022.
   https://www.jpl.nasa.gov/news/nasas-perseverance-rover-investigates-geologically-rich-mars-terrain/
10. NASA JPL, « NASA's Perseverance Rover to Begin Building Martian Sample Depot »,
    décembre 2022.
    https://www.jpl.nasa.gov/news/nasas-perseverance-rover-to-begin-building-martian-sample-depot/
11. Hurowitz J. A. et al., 2025. « Redox-driven mineral and organic associations in Jezero
    Crater, Mars ». *Nature* 645. https://doi.org/10.1038/s41586-025-09413-0
12. NASA, « NASA Says Mars Rover Discovered Potential Biosignature Last Year »,
    10 septembre 2025.
    https://www.nasa.gov/news-release/nasa-says-mars-rover-discovered-potential-biosignature-last-year/
13. Coan D., 2021. *NASA Exploration EVA Integrated HITL Testing and Analogs*, rév. A, NASA
    EVA Strategic Integration Office, NTRS 20210000827.
    https://ntrs.nasa.gov/citations/20210000827
