"""Exporte les contrats versionnés dans ``contracts/`` (T00).

- ``contracts/openapi.json`` : schéma OpenAPI de l'API (source : modèles Pydantic) ;
- ``contracts/site-manifest.schema.json`` : schéma JSON de ``manifest.json`` ;
- ``contracts/ws-message.schema.json`` : schéma JSON des messages du WebSocket.

``--check`` n'écrit rien et échoue si un fichier versionné diffère de l'export
(lancé par l'intégration continue).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from marswalk_core.paths import repo_root
from marswalk_core.schemas import SiteManifest, WsMessage


def render(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def exports() -> dict[Path, str]:
    from marswalk_api.main import create_app

    contracts = repo_root() / "contracts"
    manifest_schema = SiteManifest.model_json_schema()
    manifest_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    manifest_schema["$id"] = "https://marswalk.local/contracts/site-manifest.schema.json"
    ws_schema = TypeAdapter(WsMessage).json_schema()
    ws_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    ws_schema["title"] = "WsMessage"
    return {
        contracts / "openapi.json": render(create_app().openapi()),
        contracts / "site-manifest.schema.json": render(manifest_schema),
        contracts / "ws-message.schema.json": render(ws_schema),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="échoue si l'export diffère")
    args = parser.parse_args()
    failed = False
    for path, text in exports().items():
        rel = path.relative_to(repo_root())
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                print(f"DIFFÉRENT : {rel} (relancer tools/export_contracts.py)")
                failed = True
            else:
                print(f"identique : {rel}")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"écrit : {rel}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
