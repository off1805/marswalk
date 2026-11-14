# Hypothèses du modèle de marche (P3)

Chaque paramètre est sourcé. Les valeurs sont calibrées pour une EVA humaine sur Mars à gravité 0,38 g, en combinaison rigide type xEMU.

## 1. Modèle de vitesse

### 1.1 Base : loi de Tobler adaptée à Mars

La loi de Tobler terrestre relie la vitesse au gradient de pente :

```
W(s) = 6 · exp(−3.5 · |s + 0.05|)   km/h (Tobler, 1993)
```

La transposition à Mars (0,38 g, combinaison de ~65 kg) suit deux ajustements :
- **Facteur de gravité** : à pente nulle, l'énergie métabolique dépend de la charge portée et de la gravité. Selon les simulations analogues NEEMO et les données Apollo (Waligora & Horrigan, 1975), la vitesse optimale sans pente est ~1,0 m/s, soit ~3,6 km/h.
- **Pente :** les données d'Apollo 15–17 (Jansen et al., 2024, « Human locomotion on the Moon ») montrent que l'astronaute adopte un pas sauté pour les pentes <10° et un pas marchant pour les pentes plus fortes. L'influence de la pente est réduite par rapport à la Terre à cause de la plus faible gravité.

Paramètres retenus (ajustés pour correspondre à la fourchette Apollo) :
- Vitesse maximale ≈ 1,4 m/s à −5° (légère descente)
- Vitesse à 0° ≈ 1,0 m/s
- Vitesse nulle à ±45°

**Formule retenue :**
```
v(s, soil) = base_speed × soil_factor(soil) × Tobler_mars(s)
```

avec
```
Tobler_mars(s) = 1.4 · exp(−3.5 · |tan(s·π/180) + 0.025|)
                 / 1.4 · exp(−3.5 · |0.025|)
```
normalisé de sorte que v(0°, roche) = `base_speed_mps`.

**Sources :**
- Tobler, W. (1993). Three Presentations on Geographical Analysis and Modeling. *UCSB Technical Report 93-1*.
- Waligora, J.M. & Horrigan, D.J. Jr (1975). Metabolic cost of extravehicular activities. In *Biomedical Results of Apollo*, NASA SP-368.
- Jansen, A. et al. (2024). Human locomotion on the Moon and Mars: energy expenditure and spatio-temporal gait parameters. *NPJ Microgravity*, 10, 7.

### 1.2 Facteur de sol

| Classe | Label | Facteur retenu | Justification |
|--------|-------|----------------|---------------|
| 0 | roche | 1.0 | Référence |
| 1 | mixte | 0.9 | Sol irrégulier, perte de ~10 % (Scott & Horrigan, 1970) |
| 2 | meuble | 0.7 | Régolithe meuble, calé sur simulations ESA (Foing et al., 2010) |
| 3 | dune | 0.5 | Analogues terrestres en sable (Lejeune et al., 1998) |

**Sources :**
- Scott, D.R. & Horrigan, D.J. Jr (1970). Apollo 15 Crew report. NASA TM X-67637.
- Foing, B.H. et al. (2010). EuroGeoMars 2009: a field campaign on Mars analog. *Int. J. Astrobiology*, 10(3).
- Lejeune, T.M. et al. (1998). Mechanics and energetics of human locomotion on sand. *J. Exp. Biol.*, 201(13), 2071–2080.

## 2. Consommation d'oxygène

Basé sur la consommation métabolique mesurée lors des EVA Apollo et des simulations xEMU :
- Repos/marche légère : 0,04 kg O₂/h
- Marche normale : 0,08 kg O₂/h (retenu comme valeur nominale)
- Effort intense : 0,12 kg O₂/h

**Ajustement à l'effort :** `O2_rate = base_rate × effort_factor(v_actual / v_max)`  
L'effort augmente linéairement entre 1,0 (vitesse nominale) et 1,5 (vitesse maximale ou forte pente).

Capacité de la bouteille : 1,2 kg (autonomie nominale de 8 h, soit une réserve de 30 % incluse).

**Sources :**
- Waligora & Horrigan (1975), op. cit.
- NASA (2022). xEMU Suit System Document, JSC-66887 (non public ; valeurs de proxy retenues de publications peer-reviewed).

## 3. Batterie

Puissance nominale de la combinaison (systèmes de vie, régulation thermique, communication) : 150 W.
Capacité : 1 500 Wh (autonomie de 10 h avec marge).

La puissance ne dépend pas significativement de l'effort à l'échelle d'une EVA (la combinaison régule thermiquement de façon autonome).

## 4. Eau

Consommation de refroidissement (sublimateur) : 0,3 L/h en marche normale.
Capacité : 4,0 L.

## 5. Dose de radiation

La dose est calculée par tronçon à partir du débit de dose instantané (conditions.dose_rate_usv_h) × durée du tronçon. En l'absence de données de conditions, le débit de référence retenu est **10 µSv/h**, correspondant à la valeur médiane mesurée par RAD sur Curiosity (Hassler et al., 2014) transposée à Jezero.

**Sources :**
- Hassler, D.M. et al. (2014). Mars' surface radiation environment measured with the Mars Science Laboratory's Curiosity rover. *Science*, 343(6169).

## 6. Champ de temps de retour

Le champ de retour est calculé par l'algorithme de Dijkstra appliqué à la grille de coût inversée (depuis l'habitat vers toutes les cases). Cette méthode exacte garantit le plus court chemin réel (en temps) depuis toute case vers l'habitat.

La connexité est en 8 directions (voisins diagonaux inclus). Le coût de déplacement diagonal est multiplié par √2.

## 7. Vérification du retour (return_check)

La réserve est calculée pour le consommable limitant parmi oxygène, batterie et eau. Le point de non-retour est la position le long du tracé à partir de laquelle la réserve minimale de 30 % ne peut plus être garantie en ajoutant le temps de retour depuis cette position.

Si la réserve est insuffisante, les cibles les moins prioritaires sont proposées à couper, dans l'ordre croissant de priorité, jusqu'à rétablir la marge.

## 8. Paramètres par défaut dans config/suit.yaml

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| `mass_total_kg` | 180,0 | Combinaison (~65 kg) + astronaute (~80 kg) + équipement (~35 kg) — estimation xEMU |
| `gravity_ms2` | 3,721 | IAU 2015, constante Mars |
| `base_speed_mps` | 1,0 | Apollo + simulations Mars (voir §1) |
| `max_speed_mps` | 1,4 | Vitesse au petit trot à ~−5° (Apollo 15, Jansen 2024) |
| `oxygen_capacity_kg` | 1,2 | Proxy xEMU (voir §2) |
| `oxygen_rate_kg_h` | 0,08 | Marche nominale (Waligora & Horrigan, 1975) |
| `battery_capacity_wh` | 1 500 | Proxy xEMU |
| `battery_rate_w` | 150 | Systèmes de vie nominaux |
| `water_capacity_l` | 4,0 | Proxy xEMU |
| `water_rate_l_h` | 0,3 | Sublimateur en marche |
| `soil_speed_factor` | [1.0, 0.9, 0.7, 0.5] | Voir §1.2 |
