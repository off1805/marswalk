"""Import K1 : ``uv run python -m marswalk_conditions import``.

Lit ``data/raw/jezero/meda`` et ``data/raw/jezero/rad_may2024`` (téléchargés par D0) et écrit
le jeu compact ``data/work/conditions/jezero.json``. ``show`` résume un jeu déjà importé.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from marswalk_conditions.dataset import (
    Q_GCR,
    ConditionsDataset,
    default_path,
    equivalent_dose_usv_h,
)
from marswalk_conditions.importers import import_all
from marswalk_core.paths import repo_root


def summary(ds: ConditionsDataset) -> str:
    lines = []
    if ds.meda:
        n_wind = sum(any(v is not None for v in s.wind_mps) for s in ds.meda.values())
        temps = [v for s in ds.meda.values() for v in s.temperature_c if v is not None]
        press = [v for s in ds.meda.values() for v in s.pressure_pa if v is not None]
        lines.append(
            f"MEDA : {len(ds.meda)} sols ({ds.sols[0]} à {ds.sols[-1]}), vent sur {n_wind} sols, "
            f"{len(ds.meda_sources)} fichiers"
        )
        if temps:
            lines.append(f"  température {min(temps):.1f} à {max(temps):.1f} °C")
        if press:
            lines.append(f"  pression {min(press):.0f} à {max(press):.0f} Pa")
    else:
        lines.append("MEDA : aucun sol importé")
    r = ds.rad
    if r:
        peak_eq = equivalent_dose_usv_h(r.peak_e_ugy_h, r.baseline_e_ugy_h)
        lines += [
            f"RAD : {len(r.samples)} mesures, {len(r.sources)} sols",
            f"  fond {r.baseline_e_ugy_h:.2f} µGy/h (soit {Q_GCR * r.baseline_e_ugy_h:.1f} µSv/h)",
            f"  début {r.onset_utc:%Y-%m-%d %H:%M} UTC, pic {r.peak_utc:%Y-%m-%d %H:%M} UTC "
            f"à {r.peak_e_ugy_h:.1f} µGy/h (soit {peak_eq:.0f} µSv/h)",
            f"  fin {r.end_utc:%Y-%m-%d %H:%M} UTC, dose de l'événement {r.event_dose_ugy:.0f} µGy",
        ]
    else:
        lines.append("RAD : aucune série importée")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m marswalk_conditions")
    sub = parser.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import", help="Importer MEDA et RAD vers le jeu compact")
    imp.add_argument("--raw", type=Path, default=repo_root() / "data" / "raw" / "jezero")
    imp.add_argument("--out", type=Path, default=None)
    show = sub.add_parser("show", help="Résumer le jeu compact")
    show.add_argument("--file", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.cmd == "import":
        out = args.out or default_path()
        try:
            ds = import_all(args.raw)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Échec de l'import : {exc}", file=sys.stderr)
            return 1
        ds.save(out)
        print(summary(ds))
        print(f"Écrit : {out} ({out.stat().st_size / 1024:.0f} Ko)")
        return 0

    path = args.file or default_path()
    if not path.is_file():
        print(f"Aucun jeu importé à {path}", file=sys.stderr)
        return 1
    print(summary(ConditionsDataset.load(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
