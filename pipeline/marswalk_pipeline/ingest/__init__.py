"""Ingestion des données brutes de Jezero (D1).

Commande : ``marswalk ingest <site_id>``

Entrées : ``data/raw/<site_id>/`` avec ``sources.yaml`` (identifiant PDS, URL, date).
Sortie  : ``data/work/<site_id>/aligned/<layer_id>.tif`` (COG Float32 sur la grille
          d'analyse) + ``data/work/<site_id>/coreg_report.md``.

Règles :
- R1 : toutes les opérations en mètres dans ``analysis_crs`` (eqc martiennes).
- R2 : bbox et métadonnées en degrés (lon, lat) planétocentriques.
- R7 (ENF-07) : si le MNT HiRISE ne couvre pas l'emprise, repli sur CTX puis MOLA,
  marqué ``degraded`` dans le rapport.

Gestion des CRS réels (données Jezero) :
- ESRI:103885 : EQC Mars, lat_ts=0, lon_0=0, R=3396190 → CRS de référence commun.
- Géographique Mars (+proj=longlat +R=3396190) : HiRISE ortho, nécessite reprojection.
- EQC lat_ts=18.4663 : CTX DEM, nécessite reprojection (origine X incompatible).
- EQC lat_ts=0, lon_0=180, R=3394839.81 : JP2 HiRISE individuels, non intégrés en D1.

Gestion des NoData :
- NoData=0.0 sur Thermal Inertia : traité comme masque avant reprojection.
- NoData=-3.4028235e38 (float32 max) sur DEM : préservé tel quel.
- NoData absent (CRISM) : border_value utilisé à la place.

Gestion du CRISM multi-bandes :
- jezeroFinal.tif est une image RGB 3-bandes uint8.
- Chaque bande est reprojetée séparément en nearest neighbour.
- Le résultat est écrit en 3-bandes uint8 (pas de conversion Float32).

Le recalage (coreg) est délégué à ``marswalk_pipeline.coreg``.
"""

from __future__ import annotations

import contextlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rasterio.crs
import rasterio.enums
import rasterio.transform
import rasterio.warp
import yaml

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root

NODATA_FLOAT: float = -9999.0

# Valeur NoData canonique pour les DEM sources (float32 max ≈ -3.4028235e+38).
# rasterio lit cette valeur comme -3.4028226550889045e+38 ou -3.4028234663852886e+38
# selon la précision stockée dans les métadonnées TIFF.
_NODATA_FLOAT32_MAX: float = float(np.finfo(np.float32).min)  # ≈ -3.4028235e+38

# Valeur NoData du MOLA DEM (int16)
_NODATA_MOLA_INT16: float = -32768.0

# Résolutions cibles par couche (m/px), à titre documentaire.
# La résolution réelle de la grille est fixée par site.yaml (resolution_m).
_TARGET_RES: dict[str, float] = {
    "hirise_vis": 1.0,
    "ctx_vis": 6.0,
    "dem": 1.0,
    "dem_mola": 463.0,
    "thermal_inertia": 100.0,
    "crism_minerals": 36.0,
}

# Mapping nom-couche → clé(s) candidates dans sources.yaml, par ordre de priorité.
_SOURCE_KEYS: dict[str, list[str]] = {
    "hirise_vis": ["hirise_vis"],
    "ctx_vis": ["ctx_vis"],
    "dem": ["hirise_dem", "ctx_dem", "dem_mola"],  # ordre de repli R7
    "dem_mola": ["dem_mola"],
    "thermal_inertia": ["thermal_inertia"],
    "crism_minerals": ["crism_minerals"],
}

# Couches dont les valeurs sont catégorielles → nearest neighbour obligatoire.
_CATEGORICAL_LAYERS: frozenset[str] = frozenset({"crism_minerals"})

# Couches dont le NoData=0 est un marqueur NoData, pas une valeur valide.
_NODATA_ZERO_LAYERS: frozenset[str] = frozenset({"thermal_inertia"})


# ---------------------------------------------------------------------------
# Utilitaires CRS
# ---------------------------------------------------------------------------


def _analysis_crs_obj(crs_str: str) -> rasterio.crs.CRS:
    """Crée un objet CRS rasterio depuis une chaîne PROJ."""
    return rasterio.crs.CRS.from_proj4(crs_str)


def _crs_is_geographic(crs: rasterio.crs.CRS) -> bool:
    """Vrai si le CRS est géographique (non projeté, coordonnées en degrés)."""
    if crs is None:
        return False
    wkt = crs.to_wkt()
    return "GEOGCS" in wkt and "PROJCS" not in wkt


def _crs_needs_reprojection(src_crs: rasterio.crs.CRS, dst_crs: rasterio.crs.CRS) -> bool:
    """Vrai si src_crs et dst_crs sont différents (reprojection nécessaire)."""
    if src_crs is None or dst_crs is None:
        return True
    try:
        return not src_crs.equals(dst_crs)
    except Exception:
        return src_crs.to_proj4() != dst_crs.to_proj4()


def _describe_crs(crs: rasterio.crs.CRS | None) -> str:
    """Retourne une description courte du CRS pour les logs et rapports."""
    if crs is None:
        return "ABSENT"
    auth = crs.to_authority()
    if auth:
        return f"{auth[0]}:{auth[1]}"
    proj4 = crs.to_proj4()
    # Extraire les paramètres clés
    parts = []
    for param in ("proj", "lat_ts", "lon_0", "R"):
        for token in proj4.split():
            if token.startswith(f"+{param}="):
                parts.append(token.lstrip("+"))
    return " ".join(parts) or proj4[:60]


# ---------------------------------------------------------------------------
# Grille d'analyse
# ---------------------------------------------------------------------------


def _analysis_crs(cfg: dict[str, Any]) -> str:
    """Chaîne PROJ du système d'analyse depuis la config du site."""
    return str(cfg.get("analysis_crs", ""))


def _make_analysis_transform(
    cfg: dict[str, Any],
) -> tuple[rasterio.transform.Affine, int, int]:
    """Transformation affine et dimensions (width, height) de la grille d'analyse.

    La grille couvre ``size_m`` mètres centrée sur le point (center.lon, center.lat).

    Calcul de l'origine Y :
    Dans le CRS d'analyse (EQC PROJ avec +lat_ts et +lon_0 mais sans +lat_0), la
    coordonnée Y est en mètres depuis l'équateur, indépendamment du centre de la zone.
    Il faut donc décaler l'origine de la grille par y_center = lat_center * pi/180 * R.

    Pour le site fictif (size_m=2000, res=2m) : grille 1000×1000 px.
    Pour Jezero (size_m=5000, res=1m) : grille 5000×5000 px.

    Note : si ``ingest.grid_includes_buffer=True``, la grille inclut le buffer de
    ``ingest.bbox_buffer_m`` mètres de chaque côté.
    """
    import math

    res_m = float(cfg.get("resolution_m", 1.0))
    size_m = float(cfg.get("size_m", 5000))
    include_buffer = bool(cfg.get("ingest", {}).get("grid_includes_buffer", False))
    buffer_m = float(cfg.get("ingest", {}).get("bbox_buffer_m", 0)) if include_buffer else 0.0
    total_m = size_m + 2.0 * buffer_m
    n_w = round(total_m / res_m)
    n_h = round(total_m / res_m)
    half = total_m / 2.0

    # Y-center en mètres depuis l'équateur dans le CRS d'analyse.
    # Avec +proj=eqc et sans +lat_0, Y = lat * pi/180 * R.
    # On lit la lat du centre depuis la config, et le rayon depuis le CRS.
    center = cfg.get("center", {})
    lat_center = float(center.get("lat", 0.0))
    crs_str = str(cfg.get("analysis_crs", ""))
    r = 3_396_190.0
    for token in crs_str.split():
        if token.startswith("+R="):
            with contextlib.suppress(ValueError):
                r = float(token[3:])
    y_center = lat_center * math.pi / 180.0 * r

    # Coin supérieur-gauche : X = -half (lon_0 est le centre, donc x_center=0)
    # Y = y_center + half (Y décroît vers le bas, donc le coin haut est y_center + half)
    transform = rasterio.transform.Affine(
        res_m,
        0.0,
        -half,
        0.0,
        -res_m,
        y_center + half,
    )
    return transform, n_w, n_h


def _analysis_bbox_m(cfg: dict[str, Any]) -> tuple[float, float, float, float]:
    """Emprise de la grille d'analyse en mètres (xmin, ymin, xmax, ymax) depuis center+size."""
    center = cfg["center"]
    lon0, lat0 = float(center["lon"]), float(center["lat"])
    size_m = float(cfg.get("size_m", 5000))
    buffer_m = float(cfg.get("ingest", {}).get("bbox_buffer_m", 500))
    half = size_m / 2.0 + buffer_m
    r = 3_396_190.0
    k = math.cos(math.radians(lat0))
    dlon = math.degrees(half / (r * k))
    dlat = math.degrees(half / r)
    return (lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat)


# ---------------------------------------------------------------------------
# Préparation du NoData avant reprojection
# ---------------------------------------------------------------------------


def _normalize_nodata(
    data: np.ndarray,
    src_nodata: float | int | None,
    layer_id: str,
) -> tuple[np.ndarray, float]:
    """Normalise les pixels NoData vers NODATA_FLOAT (-9999).

    Cas particuliers :
    - NoData=0 sur thermal_inertia : les zéros sont des pixels manquants.
    - NoData float32 max (±3.4e38) : remplacé par NODATA_FLOAT.
    - NoData int16 -32768 (MOLA) : remplacé par NODATA_FLOAT.

    Retourne (data_normalisé, nodata_utilisé).
    """
    out = data.astype(np.float32)
    nd_out = NODATA_FLOAT

    if src_nodata is not None:
        # Masquer les pixels NoData sources
        mask = np.isclose(out, float(src_nodata), rtol=0, atol=1.0)
        out[mask] = nd_out
    elif layer_id in _NODATA_ZERO_LAYERS:
        # Pas de NoData déclaré mais on sait que 0.0 == manquant
        out[out == 0.0] = nd_out

    # Capturer les valeurs float32-max qui seraient encore présentes
    out[out < _NODATA_FLOAT32_MAX * 0.5] = nd_out  # < ~-1.7e38 → remplace les -3.4e38

    return out, nd_out


# ---------------------------------------------------------------------------
# Reprojection générique
# ---------------------------------------------------------------------------


def reproject_to_analysis(
    src_path: Path,
    dst_path: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
    resampling: rasterio.enums.Resampling = rasterio.enums.Resampling.bilinear,
    nodata: float = NODATA_FLOAT,
    dtype: str = "float32",
) -> None:
    """Reprojette un raster source (1 bande) vers la grille d'analyse.

    Écrit un GeoTIFF Float32 avec nodata=-9999 dans dst_path.
    La reprojection utilise ``rasterio.warp.reproject`` qui gère correctement
    tous les CRS Mars (géographique, EQC avec différents lat_ts).

    Paramètres
    ----------
    src_path  : fichier source (GeoTIFF, JP2, etc.)
    dst_path  : fichier de sortie
    crs_str   : chaîne PROJ de l'analyse (R1)
    transform, width, height : grille cible
    resampling : méthode de rééchantillonnage (bilinear par défaut, nearest pour catégoriels)
    nodata    : valeur NoData de sortie (−9999 par défaut)
    dtype     : type de sortie (float32 par défaut)
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_crs = _analysis_crs_obj(crs_str)

    with rasterio.open(src_path) as src:
        dst_data = np.full((height, width), nodata, dtype=np.float32)
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst_data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=resampling,
            dst_nodata=nodata,
        )

    with rasterio.open(
        dst_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=dst_crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(dst_data, 1)


def _reproject_single_band(
    src_path: Path,
    band_index: int,
    src_nodata: float | None,
    layer_id: str,
    dst_crs: rasterio.crs.CRS,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
    resampling: rasterio.enums.Resampling,
) -> np.ndarray:
    """Reprojette une bande et retourne le tableau float32 sur la grille cible."""
    dst_data = np.full((height, width), NODATA_FLOAT, dtype=np.float32)
    with rasterio.open(src_path) as src:
        rasterio.warp.reproject(
            source=rasterio.band(src, band_index),
            destination=dst_data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=resampling,
            dst_nodata=NODATA_FLOAT,
        )
    return dst_data


def _reproject_multibands_uint8(
    src_path: Path,
    dst_path: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
    resampling: rasterio.enums.Resampling,
    nodata: int = 0,
) -> None:
    """Reprojette un raster multi-bandes uint8 (ex. CRISM RGB) vers la grille d'analyse.

    Chaque bande est reprojetée séparément. Le résultat est un GeoTIFF multi-bandes uint8.
    La valeur nodata=0 est utilisée pour les pixels hors emprise.

    Note : le rééchantillonnage nearest neighbour est imposé pour préserver les codes
    de couleur catégoriels.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_crs = _analysis_crs_obj(crs_str)

    with rasterio.open(src_path) as src:
        n_bands = src.count

    bands_out: list[np.ndarray] = []
    for b in range(1, n_bands + 1):
        dst_band = np.zeros((height, width), dtype=np.uint8)
        with rasterio.open(src_path) as src:
            rasterio.warp.reproject(
                source=rasterio.band(src, b),
                destination=dst_band,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=resampling,
                dst_nodata=nodata,
            )
        bands_out.append(dst_band)

    with rasterio.open(
        dst_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=n_bands,
        dtype="uint8",
        crs=dst_crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        for i, band_data in enumerate(bands_out, start=1):
            dst.write(band_data, i)


# ---------------------------------------------------------------------------
# Résultat d'ingestion
# ---------------------------------------------------------------------------


class IngestResult:
    """Résultat de l'ingestion d'une couche."""

    def __init__(
        self,
        layer_id: str,
        out_path: Path,
        source_key: str,
        resolution_m: float,
        status: str,
        note: str = "",
    ) -> None:
        self.layer_id = layer_id
        self.out_path = out_path
        self.source_key = source_key
        self.resolution_m = resolution_m
        self.status = status  # "ok", "degraded", "missing"
        self.note = note


# ---------------------------------------------------------------------------
# Utilitaires sources
# ---------------------------------------------------------------------------


def _load_sources(site_id: str) -> dict[str, Any]:
    """Charge ``config/sites/<site_id>/sources.yaml``."""
    path = repo_root() / "config" / "sites" / site_id / "sources.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return dict(data.get("layers", {}))


def _raw_dir(site_id: str) -> Path:
    """Dossier des données brutes téléchargées : ``data/raw/<site_id>/``."""
    return repo_root() / "data" / "raw" / site_id


def _work_dir(site_id: str) -> Path:
    """Dossier de travail : ``data/work/<site_id>/``."""
    return repo_root() / "data" / "work" / site_id


def _resolve_source_file(raw_dir: Path, src_info: dict[str, Any], key: str) -> Path | None:
    """Résout le chemin du fichier source en testant plusieurs extensions."""
    declared = src_info.get("file", f"{key}.tif")
    candidate = raw_dir / str(declared)
    if candidate.exists():
        return candidate
    for ext in (".img", ".tif", ".tiff", ".fits", ".jp2"):
        alt = candidate.with_suffix(ext)
        if alt.exists():
            return alt
    return None


# ---------------------------------------------------------------------------
# Ingestion d'une couche
# ---------------------------------------------------------------------------


def _select_resampling(layer_id: str) -> rasterio.enums.Resampling:
    """Choisit la méthode de rééchantillonnage selon la nature de la couche."""
    if layer_id in _CATEGORICAL_LAYERS:
        return rasterio.enums.Resampling.nearest
    return rasterio.enums.Resampling.bilinear


def _probe_raster(src_path: Path) -> dict[str, Any]:
    """Ouvre un raster et retourne ses métadonnées sans charger les données."""
    with rasterio.open(src_path) as src:
        return {
            "crs": src.crs,
            "crs_str": _describe_crs(src.crs),
            "bounds": src.bounds,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtypes": list(src.dtypes),
            "nodata": src.nodata,
            "res": src.res,
            "transform": src.transform,
        }


def _check_coverage(
    src_bounds: rasterio.coords.BoundingBox,
    src_crs: rasterio.crs.CRS,
    dst_transform: rasterio.transform.Affine,
    dst_width: int,
    dst_height: int,
    dst_crs: rasterio.crs.CRS,
) -> tuple[bool, float]:
    """Vérifie si le raster source couvre l'emprise de la grille cible.

    Reprojette les coins de la grille cible dans le CRS source et compare aux bounds.
    Retourne (couvre_entièrement, fraction_couverte).

    Les coins de la grille cible sont calculés à partir du transform affine :
    - coin haut-gauche : (c, f)
    - coin haut-droit : (c + a*w, f)
    - coin bas-gauche : (c, f + e*h)
    - coin bas-droit  : (c + a*w, f + e*h)
    """
    left = dst_transform.c
    top = dst_transform.f
    right = left + dst_transform.a * dst_width
    bottom = top + dst_transform.e * dst_height  # e est négatif → bottom < top

    # Reprojeter les 4 coins depuis dst_crs vers src_crs
    try:
        xs, ys = rasterio.warp.transform(
            dst_crs,
            src_crs,
            [left, right, left, right],
            [top, top, bottom, bottom],
        )
        src_left = min(xs)
        src_right = max(xs)
        src_bottom = min(ys)
        src_top = max(ys)
    except Exception:
        return False, 0.0

    b = src_bounds
    covers = (
        b.left <= src_left and b.right >= src_right and b.bottom <= src_bottom and b.top >= src_top
    )

    if covers:
        return True, 1.0

    # Calculer la fraction de couverture (intersection / total en coordonnées source)
    ix_min = max(b.left, src_left)
    ix_max = min(b.right, src_right)
    iy_min = max(b.bottom, src_bottom)
    iy_max = min(b.top, src_top)

    if ix_min >= ix_max or iy_min >= iy_max:
        return False, 0.0

    target_area = (src_right - src_left) * (src_top - src_bottom)
    if target_area <= 0:
        return False, 0.0
    intersection_area = (ix_max - ix_min) * (iy_max - iy_min)
    return False, min(intersection_area / target_area, 1.0)


def ingest_layer(
    layer_id: str,
    cfg: dict[str, Any],
    sources: dict[str, Any],
    raw_dir: Path,
    work_aligned_dir: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
) -> IngestResult:
    """Ingeste une couche : trouve le fichier source, reprojette, écrit aligned/<layer_id>.tif.

    Applique le repli automatique (DEM : HiRISE → CTX → MOLA) et marque ``degraded``
    si un repli est utilisé.

    Traitements spéciaux :
    - CRISM multi-bandes (jezeroFinal.tif) : reprojection bande par bande, nearest neighbour.
    - Thermal Inertia (NoData=0) : masquage des zéros avant reprojection.
    - CRS géographique (HiRISE ortho) : reprojection automatique via rasterio.warp.
    - CTX DEM lat_ts=18.47 : reprojection automatique via rasterio.warp.
    """
    source_keys = _SOURCE_KEYS.get(layer_id, [layer_id])
    out_path = work_aligned_dir / f"{layer_id}.tif"
    dst_crs = _analysis_crs_obj(crs_str)
    resampling = _select_resampling(layer_id)

    for key in source_keys:
        src_info = sources.get(key)
        if src_info is None:
            continue
        src_file = _resolve_source_file(raw_dir, src_info, key)
        if src_file is None:
            continue

        try:
            meta = _probe_raster(src_file)
        except Exception:
            continue

        # Vérifier la couverture
        _covers, fraction = _check_coverage(
            meta["bounds"],
            meta["crs"],
            transform,
            width,
            height,
            dst_crs,
        )
        if fraction < 0.5:
            # Moins de 50% de couverture : passer à la source suivante
            print(
                f"[D1] {layer_id}: {key} couvre {fraction * 100:.0f}% de l'emprise, "
                f"essai de la source suivante"
            )
            continue

        try:
            is_categorical = layer_id in _CATEGORICAL_LAYERS
            is_multiband = meta["count"] > 1

            if is_categorical and is_multiband:
                # CRISM : multi-bandes uint8, nearest neighbour sur chaque bande
                _reproject_multibands_uint8(
                    src_file,
                    out_path,
                    crs_str,
                    transform,
                    width,
                    height,
                    resampling=rasterio.enums.Resampling.nearest,
                    nodata=0,
                )
            elif layer_id in _NODATA_ZERO_LAYERS and meta["nodata"] == 0.0:
                # Thermal Inertia : NoData=0 — le pré-masquer avant reprojection
                _reproject_with_nodata_mask(
                    src_file,
                    out_path,
                    crs_str,
                    transform,
                    width,
                    height,
                    resampling,
                    src_nodata=0.0,
                    dst_nodata=NODATA_FLOAT,
                )
            else:
                # Cas général : reprojection bande 1 → Float32
                reproject_to_analysis(
                    src_file,
                    out_path,
                    crs_str,
                    transform,
                    width,
                    height,
                    resampling=resampling,
                    nodata=NODATA_FLOAT,
                )

            status = "ok" if key == source_keys[0] else "degraded"
            note_parts = []
            if key != source_keys[0]:
                note_parts.append(f"repli sur '{key}' (fichier préféré manquant)")
            if fraction < 1.0:
                note_parts.append(f"couverture partielle ({fraction * 100:.0f}%)")

            # Documenter la reprojection si le CRS source diffère
            src_crs_desc = meta["crs_str"]
            dst_crs_desc = _describe_crs(dst_crs)
            if _crs_needs_reprojection(meta["crs"], dst_crs):
                note_parts.append(f"reprojeté {src_crs_desc} → {dst_crs_desc}")

            return IngestResult(
                layer_id=layer_id,
                out_path=out_path,
                source_key=key,
                resolution_m=float(src_info.get("resolution_m", _TARGET_RES.get(layer_id, 1.0))),
                status=status,
                note="; ".join(note_parts) if note_parts else "",
            )

        except Exception as exc:
            print(f"[D1] {layer_id}: erreur sur '{key}': {exc}")
            continue

    # Aucune source disponible
    return IngestResult(
        layer_id=layer_id,
        out_path=out_path,
        source_key="none",
        resolution_m=0.0,
        status="missing",
        note="Aucun fichier source disponible. Télécharger via D0.",
    )


def _reproject_with_nodata_mask(
    src_path: Path,
    dst_path: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
    resampling: rasterio.enums.Resampling,
    src_nodata: float,
    dst_nodata: float,
) -> None:
    """Reprojette en remplaçant d'abord src_nodata par dst_nodata dans les données source.

    Utilisé pour le Thermal Inertia où NoData=0 risque d'être interpolé comme une
    vraie valeur pendant la reprojection bilinéaire.

    Stratégie : lire les données, remplacer les NoData, écrire dans un buffer en mémoire,
    puis laisser rasterio.warp.reproject opérer sur ce buffer.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_crs = _analysis_crs_obj(crs_str)

    with rasterio.open(src_path) as src:
        src_data = src.read(1).astype(np.float32)
        src_transform = src.transform
        src_crs = src.crs

        # Remplacer NoData source
        src_data[np.isclose(src_data, src_nodata, rtol=0, atol=1e-6)] = dst_nodata

        dst_data = np.full((height, width), dst_nodata, dtype=np.float32)
        rasterio.warp.reproject(
            source=src_data,
            destination=dst_data,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=resampling,
            src_nodata=dst_nodata,
            dst_nodata=dst_nodata,
        )

    with rasterio.open(
        dst_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=dst_crs,
        transform=transform,
        nodata=dst_nodata,
    ) as dst:
        dst.write(dst_data, 1)


# ---------------------------------------------------------------------------
# Validation post-ingestion
# ---------------------------------------------------------------------------


class IngestValidation:
    """Résultat de la validation d'un raster aligné."""

    def __init__(
        self,
        layer_id: str,
        path: Path,
        ok: bool,
        issues: list[str],
        metrics: dict[str, Any],
    ) -> None:
        self.layer_id = layer_id
        self.path = path
        self.ok = ok
        self.issues = issues
        self.metrics = metrics

    def __repr__(self) -> str:
        status = "OK" if self.ok else f"ISSUES({len(self.issues)})"
        return f"IngestValidation({self.layer_id}, {status})"


def validate_aligned_raster(
    layer_id: str,
    path: Path,
    expected_crs: rasterio.crs.CRS,
    expected_transform: rasterio.transform.Affine,
    expected_width: int,
    expected_height: int,
) -> IngestValidation:
    """Valide un raster aligné après ingestion.

    Contrôles :
    - Le fichier existe.
    - Le CRS correspond à l'analyse.
    - Les dimensions correspondent à la grille.
    - La transformation affine correspond.
    - La fraction de pixels valides (non-NoData) est raisonnable (> 1%).
    - Les valeurs ne sont pas toutes identiques (données non dégénérées).
    """
    issues: list[str] = []
    metrics: dict[str, Any] = {}

    if not path.exists():
        return IngestValidation(layer_id, path, False, ["Fichier absent"], {})

    try:
        with rasterio.open(path) as ds:
            crs_ok = not _crs_needs_reprojection(ds.crs, expected_crs)
            if not crs_ok:
                issues.append(
                    f"CRS inattendu : {_describe_crs(ds.crs)} "
                    f"(attendu {_describe_crs(expected_crs)})"
                )

            if ds.width != expected_width or ds.height != expected_height:
                issues.append(
                    f"Dimensions {ds.width}×{ds.height} "
                    f"(attendu {expected_width}×{expected_height})"
                )

            tf = ds.transform
            if abs(tf.a - expected_transform.a) > 1e-3 or abs(tf.c - expected_transform.c) > 1.0:
                issues.append(
                    f"Transform diverge : a={tf.a:.4f} (attendu {expected_transform.a:.4f}), "
                    f"c={tf.c:.2f} (attendu {expected_transform.c:.2f})"
                )

            # Statistiques sur la bande 1
            band = ds.read(1).astype(np.float32)
            nd = ds.nodata if ds.nodata is not None else NODATA_FLOAT
            valid_mask = np.isfinite(band) & ~np.isclose(band, nd, rtol=0, atol=1.0)
            n_valid = int(np.sum(valid_mask))
            n_total = band.size
            valid_pct = n_valid / n_total * 100

            metrics["n_valid"] = n_valid
            metrics["n_total"] = n_total
            metrics["valid_pct"] = round(valid_pct, 2)

            if n_valid == 0:
                issues.append("Aucun pixel valide (100% NoData après reprojection)")
            elif valid_pct < 1.0:
                issues.append(f"Couverture très faible : {valid_pct:.2f}% de pixels valides")

            if n_valid > 0:
                valid_values = band[valid_mask]
                metrics["min"] = float(np.min(valid_values))
                metrics["max"] = float(np.max(valid_values))
                metrics["mean"] = float(np.mean(valid_values))
                if np.all(valid_values == valid_values[0]):
                    issues.append("Toutes les valeurs valides sont identiques (données dégénérées)")

    except Exception as exc:
        issues.append(f"Erreur de lecture : {exc}")

    return IngestValidation(layer_id, path, len(issues) == 0, issues, metrics)


# ---------------------------------------------------------------------------
# Ingestion complète d'un site
# ---------------------------------------------------------------------------


def ingest(
    site_id: str,
    raw_dir: Path | None = None,
    work_dir: Path | None = None,
) -> list[IngestResult]:
    """Ingeste toutes les couches d'un site.

    Paramètres
    ----------
    site_id  : identifiant du site (ex. ``jezero``, ``fictif``).
    raw_dir  : dossier des bruts (défaut ``data/raw/<site_id>``).
    work_dir : dossier de travail (défaut ``data/work/<site_id>``).

    Retourne la liste des résultats par couche.
    La commande CLI ``marswalk ingest <site_id>`` appelle cette fonction puis
    ``marswalk_pipeline.coreg.coregister`` sur les résultats.
    """
    cfg = load_site_config(site_id)
    crs_str = _analysis_crs(cfg)
    transform, width, height = _make_analysis_transform(cfg)
    sources = _load_sources(site_id)

    if raw_dir is None:
        raw_dir = _raw_dir(site_id)
    if work_dir is None:
        work_dir = _work_dir(site_id)

    work_aligned_dir = work_dir / "aligned"
    work_aligned_dir.mkdir(parents=True, exist_ok=True)

    layers: list[str] = list(cfg.get("layers", list(_SOURCE_KEYS.keys())))
    ingestable = [lid for lid in layers if lid in _SOURCE_KEYS]

    results: list[IngestResult] = []
    for layer_id in ingestable:
        result = ingest_layer(
            layer_id=layer_id,
            cfg=cfg,
            sources=sources,
            raw_dir=raw_dir,
            work_aligned_dir=work_aligned_dir,
            crs_str=crs_str,
            transform=transform,
            width=width,
            height=height,
        )
        results.append(result)
        print(f"[D1] {layer_id:25s} {result.status:9s} {result.note}")

    return results


# ---------------------------------------------------------------------------
# Variante paquet (pour les tests sur site fictif)
# ---------------------------------------------------------------------------


def ingest_from_package(
    site_id: str,
    package_root: Path,
    work_dir: Path | None = None,
) -> list[IngestResult]:
    """Variante de ``ingest`` qui utilise les COG d'un paquet existant comme sources.

    Utile pour tester D1 sur le site fictif sans données réelles.
    Reprojette les COG du paquet vers la grille d'analyse du site_id cible.
    """
    from marswalk_core.site_package import open_package

    src_site = open_package(package_root)
    cfg = load_site_config(site_id)
    crs_str = _analysis_crs(cfg)
    transform, width, height = _make_analysis_transform(cfg)

    if work_dir is None:
        work_dir = _work_dir(site_id)
    work_aligned_dir = work_dir / "aligned"
    work_aligned_dir.mkdir(parents=True, exist_ok=True)

    results: list[IngestResult] = []
    for layer_id in _SOURCE_KEYS:
        src_layer_key = layer_id if layer_id != "dem" else "dem"
        if not src_site.has_layer(src_layer_key):
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=work_aligned_dir / f"{layer_id}.tif",
                    source_key="none",
                    resolution_m=0.0,
                    status="missing",
                    note="Couche absente du paquet source",
                )
            )
            continue

        src_cog = package_root / str(src_site.layer(src_layer_key).cog)
        out_path = work_aligned_dir / f"{layer_id}.tif"
        resampling = _select_resampling(layer_id)

        try:
            reproject_to_analysis(src_cog, out_path, crs_str, transform, width, height, resampling)
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=out_path,
                    source_key=src_layer_key,
                    resolution_m=float(src_site.layer(src_layer_key).resolution_m or 1.0),
                    status="ok",
                    note="source: paquet fictif (SYNTHETIC)",
                )
            )
        except Exception as exc:
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=out_path,
                    source_key=src_layer_key,
                    resolution_m=0.0,
                    status="missing",
                    note=f"Erreur reprojection : {exc}",
                )
            )

    return results
