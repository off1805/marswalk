"""Sous-module interne de P1 : moteur de risque et grille de coût.

Sous-modules :
- ``layers``  : lecture et dégradation gracieuse des couches
- ``masks``   : construction vectorisée des masques interdits et pénalisés
- ``cost``    : formule de coût C = w_t·t + w_r·R − w_s·S
- ``explain`` : décomposition du coût d'une case
- ``polygon`` : vectorisation des masques en polygones GeoJSON

Ce paquet est privé à ``marswalk_planner``. L'API publique passe par
``marswalk_planner.hazards`` et ``marswalk_planner.cost``.
"""
