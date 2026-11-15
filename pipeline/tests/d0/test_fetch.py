"""Tests de D0 sans réseau : un faux serveur HTTP en mémoire."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from marswalk_pipeline.fetch import fetch as fetch_mod
from marswalk_pipeline.fetch.__main__ import main
from marswalk_pipeline.fetch.fetch import LOCK_NAME, REPORT_NAME, plan, run
from marswalk_pipeline.fetch.parallel import fetch_ranges, merge_ranges, split
from marswalk_pipeline.fetch.sources import load_sources

ROOT = Path(__file__).resolve().parents[3]
BASE = "https://exemple.test"


class FakeHttp:
    def __init__(self, files: dict[str, bytes], pages: dict[str, str] | None = None) -> None:
        self.files = files
        self.pages = pages or {}
        self.gets: list[tuple[str, int]] = []
        self.fail_after: int | None = None

    def size(self, url: str) -> int:
        return len(self.files[url])

    def resolve(self, url: str) -> str:
        return url

    def stream(self, url: str, start: int = 0, end: int | None = None) -> Iterator[bytes]:
        self.gets.append((url, start))
        data = self.files[url][start:end]
        if self.fail_after is not None:
            yield data[: self.fail_after]
            raise OSError("coupure réseau")
        yield data

    def text(self, url: str) -> str:
        return self.pages[url]


def write_config(tmp: Path, products: list[dict[str, object]]) -> Path:
    root = tmp / "config"
    (root / "s").mkdir(parents=True)
    cfg = {
        "site_id": "s",
        "extent": {"center": {"lon": 77.45, "lat": 18.44}, "size_m": 5000, "margin_m": 1000},
        "products": products,
    }
    (root / "s" / "sources.yaml").write_text(yaml.safe_dump(cfg), "utf-8")
    return root


def product(pid: str, **kw: object) -> dict[str, object]:
    return {"id": pid, "product": pid, "layer": pid, "priority": "utile"} | kw


def test_real_sources_yaml_is_valid() -> None:
    src = load_sources("jezero", ROOT / "config" / "sites")
    ids = {p.id for p in src.products}
    assert {"hirise_ortho", "hirise_dtm", "ctx_ortho", "ctx_dtm", "mola_dem"} <= ids
    for p in src.products:
        assert p.files or p.listing, p.id
        assert p.license and p.citation, p.id
    w, s, e, n = src.extent.bounds()
    assert (n - s) * 3396190 * 3.14159265 / 180 == pytest.approx(7000, rel=1e-3)
    assert w < 77.4509 < e


def test_download_lock_and_second_run_is_noop(tmp_path: Path) -> None:
    url = f"{BASE}/a.tif"
    root = write_config(tmp_path, [product("a", files=[{"url": url, "size": 10}])])
    http = FakeHttp({url: b"0123456789"})
    out = tmp_path / "raw"
    src = load_sources("s", root)
    first = run(src, http, out, log=lambda _: None)
    assert [o.status for o in first] == ["téléchargé"]
    assert (out / "a" / "a.tif").read_bytes() == b"0123456789"
    lock = yaml.safe_load((out / LOCK_NAME).read_text("utf-8"))["files"]["a/a.tif"]
    assert lock["size"] == 10 and len(lock["sha256"]) == 64 and lock["url"] == url
    assert (out / REPORT_NAME).exists()
    http.gets.clear()
    second = run(src, http, out, log=lambda _: None)
    assert [o.status for o in second] == ["déjà présent"]
    assert http.gets == []


def test_resume_after_interruption(tmp_path: Path) -> None:
    url = f"{BASE}/b.bin"
    root = write_config(tmp_path, [product("b", files=[{"url": url}])])
    http = FakeHttp({url: b"abcdefghij"})
    http.fail_after = 4
    out = tmp_path / "raw"
    src = load_sources("s", root)
    assert run(src, http, out, log=lambda _: None)[0].status == "échec"
    http.fail_after = None
    assert run(src, http, out, log=lambda _: None)[0].status == "téléchargé"
    assert http.gets[-1] == (url, 4)
    assert (out / "b" / "b.bin").read_bytes() == b"abcdefghij"


def test_listing_filters_and_recurses(tmp_path: Path) -> None:
    d = f"{BASE}/dir/"
    pages = {
        d: '<a href="../">p</a><a href="sol_1/">s</a><a href="sol_9/">s</a>'
        '<a href="X_01.CSV">x</a><a href="nope.txt">n</a>',
        f"{d}sol_1/": '<a href="X_02.CSV">x</a>',
    }
    files = {f"{d}X_01.CSV": b"1", f"{d}sol_1/X_02.CSV": b"22"}
    root = write_config(
        tmp_path,
        [
            product(
                "m",
                listing={
                    "url": d,
                    "pattern": r"^X_\d+\.CSV$",
                    "recursive": True,
                    "dir_pattern": r"^sol_1$",
                },
            )
        ],
    )
    items = plan(load_sources("s", root), FakeHttp(files, pages), tmp_path)
    assert [(i.url, i.size) for i in items] == [(f"{d}X_01.CSV", 1), (f"{d}sol_1/X_02.CSV", 2)]


def test_clip_and_fallback(tmp_path: Path) -> None:
    ok, ko = f"{BASE}/ok.tif", f"{BASE}/ko.tif"
    root = write_config(
        tmp_path,
        [
            product("c", clip=True, files=[{"url": ok}]),
            product("d", clip=True, files=[{"url": ko}]),
        ],
    )
    http = FakeHttp({ok: b"x" * 100, ko: b"full"})

    def clipper(url: str, dest: Path, bounds: tuple[float, float, float, float]) -> None:
        if url == ko:
            raise RuntimeError("non découpable")
        assert bounds[0] < 77.45 < bounds[2]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"clip")

    out = tmp_path / "raw"
    src = load_sources("s", root)
    res = run(src, http, out, clipper=clipper, log=lambda _: None)
    assert [o.status for o in res] == ["découpé", "téléchargé"]
    assert (out / "c" / "ok_clip.tif").read_bytes() == b"clip"
    assert (out / "d" / "ko.tif").read_bytes() == b"full"
    again = run(src, http, out, clipper=clipper, log=lambda _: None)
    assert [o.status for o in again] == ["déjà présent", "déjà présent"]


def test_dry_run_announces_total(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_config(tmp_path, [product("a", files=[{"url": f"{BASE}/a", "size": 2048}])])
    monkeypatch.setattr("marswalk_pipeline.fetch.__main__.UrllibHttp", lambda: FakeHttp({}))
    assert main(["s", "--dry-run", "--config-root", str(root), "--out", str(tmp_path / "o")]) == 0
    assert "2.0 Ko" in capsys.readouterr().out
    assert not (tmp_path / "o").exists()


def test_merge_and_split_ranges() -> None:
    assert merge_ranges([(10, 20), (0, 5), (21, 30), (100, 100)], gap=1) == [(0, 5), (10, 30)]
    assert merge_ranges([(0, 5), (10, 20)], gap=5) == [(0, 20)]
    assert split([(0, 10), (20, 25)], size=4) == [(0, 4), (4, 8), (8, 10), (20, 24), (24, 25)]


def test_fetch_ranges_parallel_with_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("marswalk_pipeline.fetch.parallel.SEGMENT", 4)
    data = bytes(range(40))
    url = f"{BASE}/big"
    http = FakeHttp({url: data})
    path = tmp_path / "mirror"
    real_stream = http.stream
    calls = {"n": 0}

    def flaky(u: str, start: int = 0, end: int | None = None) -> Iterator[bytes]:
        calls["n"] += 1
        if start == 12:
            raise OSError("coupure")
        return real_stream(u, start, end)

    monkeypatch.setattr(http, "stream", flaky)
    with pytest.raises(OSError):
        fetch_ranges(http, url, [(0, 16), (30, 38)], path, len(data), workers=1)
    assert path.with_name("mirror.segments").exists()
    monkeypatch.setattr(http, "stream", real_stream)
    http.gets.clear()
    got: list[int] = []
    fetch_ranges(http, url, [(0, 16), (30, 38)], path, len(data), got.append, workers=3)
    starts = {s for _, s in http.gets}
    assert 12 in starts and 0 not in starts  # seuls les segments manquants
    content = path.read_bytes()
    assert len(content) == 40
    assert content[0:16] == data[0:16] and content[30:38] == data[30:38]
    assert content[20:30] == bytes(10)  # hors plages : non transféré
    assert sum(got) == 24
    assert not path.with_name("mirror.segments").exists()


def test_large_download_uses_parallel_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_mod, "PARALLEL_MIN", 8)
    monkeypatch.setattr("marswalk_pipeline.fetch.parallel.SEGMENT", 4)
    url = f"{BASE}/g.tif"
    data = b"abcdefghijklmnopqrstuvwxyz"
    root = write_config(tmp_path, [product("g", files=[{"url": url, "size": len(data)}])])
    http = FakeHttp({url: data})
    out = tmp_path / "raw"
    assert run(load_sources("s", root), http, out, log=lambda _: None)[0].status == "téléchargé"
    assert (out / "g" / "g.tif").read_bytes() == data
    assert len(http.gets) == 7


@pytest.mark.parametrize("bigtiff", ["NO", "YES"])
def test_tiff_structure_ranges_make_sparse_copy_openable(tmp_path: Path, bigtiff: str) -> None:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    from marswalk_pipeline.fetch.tiff import structure_ranges

    src = tmp_path / "src.tif"
    data = np.arange(64 * 50, dtype="float32").reshape(1, 64, 50)
    with rasterio.open(
        src,
        "w",
        driver="GTiff",
        width=50,
        height=64,
        count=1,
        dtype="float32",
        transform=from_origin(0, 0, 1, 1),
        BIGTIFF=bigtiff,
    ) as dst:
        dst.write(data)
    raw = src.read_bytes()
    url = f"{BASE}/src.tif"
    ranges = structure_ranges(FakeHttp({url: raw}), url)
    sparse = bytearray(len(raw))
    for start, end in ranges:
        sparse[start:end] = raw[start:end]
    copy = tmp_path / "copy.tif"
    copy.write_bytes(bytes(sparse))
    with rasterio.open(copy) as r:
        assert (r.width, r.height) == (50, 64)
    assert sum(e - s for s, e in ranges) < len(raw) // 2  # pas les pixels
