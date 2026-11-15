"""Images au sol de Perseverance (G1) : index positionné, trajet du rover, vignettes.

Commande : ``python -m marswalk_pipeline.ground_images <site>`` (voir ``README.md``).
Elle interroge les serveurs du JPL et s'exécute donc sur l'ordinateur de la personne,
comme D0. Les tests tournent sans réseau, sur des réponses enregistrées.
"""

from .index import (
    GroundImage,
    IndexOptions,
    IndexResult,
    Waypoint,
    build_index,
    parse_images,
    parse_waypoints,
    traverse_features,
)
from .sources import DirFetcher, Fetcher, HttpFetcher

__all__ = [
    "DirFetcher",
    "Fetcher",
    "GroundImage",
    "HttpFetcher",
    "IndexOptions",
    "IndexResult",
    "Waypoint",
    "build_index",
    "parse_images",
    "parse_waypoints",
    "traverse_features",
]
