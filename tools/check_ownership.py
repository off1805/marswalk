"""Contrôle de propriété des dossiers (T00), lancé par l'intégration continue.

Compare les fichiers modifiés d'une branche ``task/<ID>-<slug>`` à ``tasks/ownership.yaml``
et échoue si un fichier sort du périmètre de la tâche. Les fichiers partagés (manifestes et
verrous de dépendances) et ``tasks/change-requests/<ID>-*.md`` sont toujours permis.
Une branche qui ne suit pas le motif ``task/<ID>-...`` n'est pas contrôlée.

Usage ::

    uv run python tools/check_ownership.py                    # branche courante contre origin/main
    uv run python tools/check_ownership.py --base main
    uv run python tools/check_ownership.py --branch task/P1-risque \
        --files planner/marswalk_planner/route.py
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BRANCH_RE = re.compile(r"^task/(?P<id>[A-Z][A-Z0-9]*)-[\w.-]+$")
SHARED_NOTE = "fichier partagé : ajout de dépendances seulement (vérifié en revue)"


@cache
def _pattern(glob: str) -> re.Pattern[str]:
    out = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            out += ".*"
            i += 2
        elif glob[i] == "*":
            out += "[^/]*"
            i += 1
        elif glob[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(glob[i])
            i += 1
    return re.compile(f"^{out}$")


def matches(path: str, globs: list[str]) -> bool:
    return any(_pattern(g).match(path) for g in globs)


@dataclass
class Ownership:
    shared: list[str]
    tasks: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = ROOT / "tasks" / "ownership.yaml") -> Ownership:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(shared=list(data["shared"]), tasks=dict(data["tasks"]))

    def check(self, task_id: str, files: list[str]) -> list[str]:
        """Liste des fichiers hors périmètre (vide si tout va bien)."""
        if task_id not in self.tasks:
            return [f"<tâche inconnue : {task_id}>"]
        spec = self.tasks[task_id]
        if spec.get("bootstrap"):
            return []
        paths = [str(p) for p in spec.get("paths", [])]  # type: ignore[attr-defined]
        exclude = [str(p) for p in spec.get("exclude", [])]  # type: ignore[attr-defined]
        allowed_cr = f"tasks/change-requests/{task_id}-*.md"
        bad: list[str] = []
        for f in files:
            if matches(f, self.shared) or matches(f, [allowed_cr]):
                continue
            if matches(f, paths) and not matches(f, exclude):
                continue
            bad.append(f)
        return bad


def current_branch() -> str:
    for var in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        if os.environ.get(var):
            return os.environ[var]
    out = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def changed_files(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return [line for line in out.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--files", nargs="*", default=None, help="fichiers à contrôler")
    args = parser.parse_args(argv)

    branch = args.branch or current_branch()
    m = BRANCH_RE.match(branch)
    if not m:
        print(f"Branche {branch} : pas de la forme task/<ID>-<slug>, contrôle ignoré.")
        return 0
    task_id = m.group("id")
    files = args.files if args.files is not None else changed_files(args.base)
    ownership = Ownership.load()
    bad = ownership.check(task_id, files)
    shared = [f for f in files if matches(f, ownership.shared)]
    for f in shared:
        print(f"note : {f} ({SHARED_NOTE})")
    if bad:
        print(f"ÉCHEC : {len(bad)} fichier(s) hors du périmètre de {task_id} :")
        for f in bad:
            print(f"  - {f}")
        print("Passer par tasks/change-requests/ pour un besoin hors périmètre.")
        return 1
    print(f"OK : {len(files)} fichier(s) dans le périmètre de {task_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
