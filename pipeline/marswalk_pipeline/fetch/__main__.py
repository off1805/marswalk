"""`python -m marswalk_pipeline.fetch <site_id> [--dry-run] [--only id,...]`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fetch import human, plan, run
from .http import UrllibHttp
from .sources import DEFAULT_CONFIG_ROOT, load_sources


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="marswalk_pipeline.fetch", description=__doc__)
    ap.add_argument("site_id")
    ap.add_argument("--dry-run", action="store_true", help="liste les fichiers et la taille totale")
    ap.add_argument("--only", default="", help="identifiants de produits, séparés par des virgules")
    ap.add_argument("--config-root", type=Path, default=DEFAULT_CONFIG_ROOT)
    ap.add_argument("--out", type=Path, default=None, help="défaut : data/raw/<site_id>")
    args = ap.parse_args(argv)

    sources = load_sources(args.site_id, args.config_root)
    only = {s for s in args.only.split(",") if s} or None
    if only and (unknown := only - {p.id for p in sources.products}):
        ap.error(f"produits inconnus : {', '.join(sorted(unknown))}")
    out = args.out or Path("data/raw") / args.site_id
    http = UrllibHttp()

    if args.dry_run:
        items = plan(sources, http, out, only)
        for it in items:
            mode = "découpe" if it.clip else "complet"
            print(f"{it.product.id:14} {human(it.size):>10}  {mode:8} {it.url}")
        total = sum(it.size for it in items)
        print(f"\n{len(items)} fichiers, {human(total)} au plus.")
        print("Les découpes (/vsicurl/) ne transfèrent que les blocs de l'emprise.")
        return 0

    outcomes = run(sources, http, out, only)
    failed = [o for o in outcomes if o.status == "échec"]
    print(
        f"\nTerminé : {len(outcomes) - len(failed)} fichiers prêts, {len(failed)} échecs. "
        f"Voir {out / 'fetch_report.md'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
