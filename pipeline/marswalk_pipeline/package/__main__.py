"""``python -m marswalk_pipeline.package <site_id>`` : construit et valide le paquet (D3)."""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .build import MAX_BYTES, PackageError, build_package, default_out_dir, default_work_dir
from .fixture import export_work_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="marswalk package", description=__doc__)
    parser.add_argument("site_id")
    parser.add_argument("--work", type=Path, help="entrées (défaut : data/work/<site_id>)")
    parser.add_argument("--out", type=Path, help="paquet (défaut : data/packages/<site_id>)")
    parser.add_argument(
        "--from-package",
        type=Path,
        help="reprend les sources d'un paquet existant (par ex. fixtures/sites/fictif)",
    )
    parser.add_argument("--max-mb", type=float, help="taille maximale (défaut : 2 Go)")
    parser.add_argument(
        "--generated-at",
        type=datetime.fromisoformat,
        help="date du manifeste, pour un paquet reproductible (sinon SOURCE_DATE_EPOCH)",
    )
    args = parser.parse_args(argv)
    max_bytes = int(args.max_mb * 1e6) if args.max_mb else MAX_BYTES
    out = args.out or default_out_dir(args.site_id)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            work = args.work or default_work_dir(args.site_id)
            if args.from_package:
                work = Path(tmp) / "work"
                export_work_dir(args.from_package, work)
            report = build_package(
                args.site_id,
                work,
                out,
                max_bytes=max_bytes,
                generated_at=args.generated_at,
                log=lambda m: print(f"  {m}", flush=True),
            )
    except PackageError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1
    print(report.summary())
    print("paquet valide")
    return 0


if __name__ == "__main__":
    sys.exit(main())
