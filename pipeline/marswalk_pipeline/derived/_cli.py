"""Point d'entrée CLI pour les couches dérivées D2.

Usage : python -m marswalk_pipeline.derived <site_id> [--aligned-dir DIR] [--derived-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import run_derive


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="marswalk-derive",
        description="Calcule les couches dérivées D2 pour un site Marswalk.",
    )
    parser.add_argument("site_id", help="Identifiant du site (ex: fictif, jezero)")
    parser.add_argument(
        "--aligned-dir",
        type=Path,
        default=None,
        help="Répertoire des rasters alignés sources (optionnel).",
    )
    parser.add_argument(
        "--derived-dir",
        type=Path,
        default=None,
        help="Répertoire de sortie des couches dérivées (optionnel).",
    )
    args = parser.parse_args()

    t0 = time.monotonic()
    print(f"[D2] Calcul des couches dérivées pour '{args.site_id}'...")

    results = run_derive(
        args.site_id,
        aligned_dir=args.aligned_dir,
        derived_dir=args.derived_dir,
    )

    elapsed = time.monotonic() - t0
    n_ok = sum(1 for s in results.values() if s == "ok")
    n_total = len(results)

    print(f"\n[D2] Résultats ({elapsed:.1f}s) :")
    for layer, stat in results.items():
        marker = "✓" if stat == "ok" else "✗" if stat.startswith("error") else "~"
        print(f"  {marker} {layer}: {stat}")

    print(f"\n[D2] {n_ok}/{n_total} couches produites en {elapsed:.1f}s")

    if any(s.startswith("error") for s in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
