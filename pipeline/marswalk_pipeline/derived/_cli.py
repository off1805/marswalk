"""Point d'entrée CLI : ``marswalk derive <site_id>``."""

from __future__ import annotations

import sys
from pathlib import Path

from marswalk_core.paths import find_package
from marswalk_pipeline.derived import derive


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: marswalk-derive <site_id> [--out <out_dir>]", file=sys.stderr)
        sys.exit(1)
    site_id = sys.argv[1]
    out_dir: Path | None = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            out_dir = Path(sys.argv[idx + 1])

    pkg_root = find_package(site_id)
    derive(pkg_root, out_dir=out_dir)


if __name__ == "__main__":
    main()
