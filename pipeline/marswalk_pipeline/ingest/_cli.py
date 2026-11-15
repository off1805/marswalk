"""Point d'entrée CLI : ``marswalk ingest <site_id>``."""

from __future__ import annotations

import sys
from pathlib import Path

from marswalk_pipeline.coreg import coregister, write_coreg_report
from marswalk_pipeline.ingest import _work_dir, ingest


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: marswalk-ingest <site_id> [--raw <raw_dir>] [--work <work_dir>]",
            file=sys.stderr,
        )
        sys.exit(1)

    site_id = sys.argv[1]
    raw_dir: Path | None = None
    work_dir: Path | None = None

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--raw" and i + 1 < len(args):
            raw_dir = Path(args[i + 1])
            i += 2
        elif args[i] == "--work" and i + 1 < len(args):
            work_dir = Path(args[i + 1])
            i += 2
        else:
            i += 1

    if work_dir is None:
        work_dir = _work_dir(site_id)

    print(f"[D1] Ingestion du site : {site_id}")
    ingest_results = ingest(site_id, raw_dir=raw_dir, work_dir=work_dir)

    work_aligned_dir = work_dir / "aligned"
    print("[D1] Recalage sur HiRISE...")
    native = {r.layer_id: r.resolution_m for r in ingest_results if r.status != "missing"}
    coreg_results = coregister(work_aligned_dir, native_res_m=native)

    write_coreg_report(work_dir, ingest_results, coreg_results, site_id)
    print("[D1] Terminé.")


if __name__ == "__main__":
    main()
