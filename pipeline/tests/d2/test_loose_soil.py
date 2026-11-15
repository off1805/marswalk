"""Tests de la couche dérivée : loose_soil."""

from __future__ import annotations

import numpy as np

from marswalk_pipeline.derived.loose_soil import compute_loose_soil

NODATA = -9999.0
SIZE = 100


def _make_ti(val: float) -> np.ndarray:
    return np.full((SIZE, SIZE), val, dtype=np.float32)


def _make_hi(val: float, noisy: bool = False) -> np.ndarray:
    if noisy:
        rng = np.random.default_rng(0)
        return (np.full((SIZE, SIZE), val, dtype=np.float32)
                + rng.normal(0, 20.0, (SIZE, SIZE)).astype(np.float32))
    return np.full((SIZE, SIZE), val, dtype=np.float32)


class TestHighTiGivesRock:
    def test_high_ti_gives_rock(self):
        """TI=400 → classe 0 (roche)."""
        ti = _make_ti(400.0)
        hi = _make_hi(128.0)
        result = compute_loose_soil(ti, hi, nodata=NODATA)
        valid = result != NODATA
        assert valid.any()
        assert np.all(result[valid] == 0.0), (
            f"TI=400 devrait donner classe 0, got {np.unique(result[valid])}"
        )


class TestLowTiLoose:
    def test_low_ti_loose(self):
        """TI=180 → classe 2 (meuble)."""
        ti = _make_ti(180.0)
        # Texture élevée pour éviter la classification dune
        hi = _make_hi(128.0, noisy=True)
        result = compute_loose_soil(ti, hi, nodata=NODATA, texture_dune_threshold=5.0)
        valid = result != NODATA
        assert valid.any()
        # La majorité devrait être classe 2 (meuble)
        # (les pixels avec texture faible peuvent être classés dune)
        counts = {v: int(np.sum(result[valid] == v)) for v in [0, 1, 2, 3]}
        assert counts[2] > 0, f"TI=180 devrait produire des pixels classe 2, counts={counts}"


class TestDuneCondition:
    def test_dune_condition(self):
        """TI=150 + texture faible → classe 3 (dune)."""
        ti = _make_ti(150.0)
        hi = _make_hi(128.0, noisy=False)  # texture=0 → classe dune
        result = compute_loose_soil(
            ti, hi, nodata=NODATA, ti_dune=170.0, texture_dune_threshold=5.0
        )
        valid = result != NODATA
        assert valid.any()
        # Avec texture=0 et TI=150 < 170 → tout devrait être classe 3
        center = result[5:-5, 5:-5]  # éviter les bords où la fenêtre de texture peut varier
        valid_c = center != NODATA
        assert valid_c.any()
        assert np.all(center[valid_c] == 3.0), (
            f"TI=150 + texture=0 devrait donner classe 3 (dune), got {np.unique(center[valid_c])}"
        )


class TestNodataPropagation:
    def test_nodata_propagation(self):
        """Pixels nodata TI ou hirise_vis → nodata en sortie."""
        ti = _make_ti(300.0)
        hi = _make_hi(128.0)
        ti[10, 10] = NODATA
        hi[20, 20] = NODATA
        result = compute_loose_soil(ti, hi, nodata=NODATA)
        assert result[10, 10] == NODATA
        assert result[20, 20] == NODATA


class TestClassesInRange:
    def test_classes_in_range(self, synthetic_ti):
        """Valeurs ∈ {0,1,2,3,-9999}."""
        hi = np.full(synthetic_ti.shape, 128.0, dtype=np.float32)
        result = compute_loose_soil(synthetic_ti, hi, nodata=NODATA)
        allowed = {0.0, 1.0, 2.0, 3.0, NODATA}
        unique_vals = set(np.unique(result).tolist())
        assert unique_vals.issubset(allowed), f"Valeurs inattendues : {unique_vals - allowed}"
