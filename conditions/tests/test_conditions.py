"""Acceptation K1.

1. Le mode ``historical`` renvoie les valeurs MEDA importées pour un sol donné.
2. Le scénario ``solar-event`` produit un pic de dose à l'instant prévu, de façon reproductible.
3. Sans réseau, tout fonctionne et ``live`` renvoie la dernière valeur en cache avec sa date.

Les fichiers d'entrée sont fabriqués ici au format exact des produits PDS (MEDA calibré CSV,
RAD RDR texte) avec des valeurs inventées : aucune donnée réelle n'est versionnée.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from marswalk_conditions import (
    ConditionsDataset,
    ConditionsProvider,
    HistoricalProvider,
    JsonFileCacheStore,
    LiveProvider,
    ScenarioProvider,
    get_provider,
    get_scenario_manager,
    list_scenarios,
)
from marswalk_conditions.__main__ import main as cli
from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.dataset import Q_GCR, bin_index
from marswalk_conditions.importers import (
    drop_outliers,
    import_all,
    iter_rad_observations,
    parse_lmst,
)
from marswalk_conditions.live import InMemoryCacheStore, classify
from marswalk_conditions.scenario import (
    DURATION_S,
    FALLBACK_PEAK_AT_S,
    ONSET_AT_S,
    ScenarioManager,
)
from marswalk_core.marstime import mars_time
from marswalk_core.schemas import SpaceWeather, SpaceWeatherLevel

EPOCH = datetime(2026, 11, 1, tzinfo=UTC)
DANGER_USV_H = 50.0  # seuil de danger de A3 (rules.py)


# -- fabrication des fichiers PDS ---------------------------------------------------


def _lmst(sol: int, hours: float) -> str:
    h = int(hours)
    m = int((hours - h) * 60)
    s = (hours - h - m / 60) * 3600
    return f"{sol:05d}M{h:02d}:{m:02d}:{s:06.3f}"


def _temp_k(hours: float) -> float:
    return 200.0 + 2.0 * hours  # 0 h : 200 K, 12 h : 224 K


def write_meda(
    d: Path, sols: tuple[int, ...] = (30, 31), wind_sols: tuple[int, ...] = (31,)
) -> None:
    d.mkdir(parents=True)
    hours = [i / 4 for i in range(96)]  # tous les quarts d'heure
    for sol in sols:
        ats = [
            "SCLK,LMST,LTST,ATS_LOCAL_TEMP1,ATS_LOCAL_TEMP2,ATS_LOCAL_TEMP3,ATS_LOCAL_TEMP4,ATS_LOCAL_TEMP5"
        ]
        ps = [
            "SCLK,LMST,LTST,BAROCAP1_PRESSURE,BAROCAP1_PRESSURE_UNCERTAINTY,BAROCAP2_PRESSURE,"
            "BAROCAP2_PRESSURE_UNCERTAINTY,BAROCAP3_PRESSURE,BAROCAP3_PRESSURE_UNCERTAINTY,"
            "THERMOCAP1_TEMP,THERMOCAP1_TEMP_UNCERTAINTY,THERMOCAP2_TEMP,"
            "THERMOCAP2_TEMP_UNCERTAINTY,PRESSURE_MEASUREMENT_MODE,TRANSDUCER"
        ]
        ws = [
            "SCLK,LMST,LTST,BOOM1_HORIZONTAL_WIND_SPEED,BOOM1_HORIZONTAL_WIND_SPEED_UNCERTAINTY,"
            "BOOM1_VERTICAL_WIND_SPEED,BOOM1_VERTICAL_WIND_SPEED_UNCERTAINTY,BOOM1_WIND_DIRECTION,"
            "BOOM1_WIND_DIRECTION_UNCERTAINTY,BOOM2_HORIZONTAL_WIND_SPEED,"
            "BOOM2_HORIZONTAL_WIND_SPEED_UNCERTAINTY,BOOM2_VERTICAL_WIND_SPEED,"
            "BOOM2_VERTICAL_WIND_SPEED_UNCERTAINTY,BOOM2_WIND_DIRECTION,"
            "BOOM2_WIND_DIRECTION_UNCERTAINTY,BOOM1_ALG_STATE_STABLE,BOOM2_ALG_STATE_STABLE,ROVER_STILL"
        ]
        for i, h in enumerate(hours):
            t = _temp_k(h) + (sol - 30)
            lm = _lmst(sol, h)
            ats.append(f"{i},{lm},x,{t:.2f},{t:.2f},{t:.2f},999,999")
            p = 740.0 + sol - 30
            ps.append(f"{i},{lm},x,{p:.2f},,0,,0,,280,,280,,nominal,1")
            ws.append(f"{i},{lm},x,3.0,,,,90,,5.0,,,,90,,1,1,1")
        # Ligne défectueuse : ignorée.
        ats.append(f"0,{_lmst(sol, 1.0)},x,,,,,")
        (d / f"WE__{sol:04d}___________CAL_ATS_________________P01.CSV").write_text("\n".join(ats))
        (d / f"WE__{sol:04d}___________CAL_PS__________________P02.CSV").write_text("\n".join(ps))
        if sol in wind_sols:
            (d / f"WE__{sol:04d}___________CAL_WS__________________P03.CSV").write_text(
                "\n".join(ws)
            )
    # Ancienne version d'un produit : ignorée au profit de P02.
    (d / "WE__0030___________CAL_PS__________________P01.CSV").write_text(
        "SCLK,LMST,LTST,BAROCAP1_PRESSURE\n0,00030M12:00:00.000,x,1100.0\n"
    )


# Événement inventé : fond 5 µGy/h, début le 20/05/2024 à 05:40, pic de 300 µGy/h à 06:20.
ONSET = datetime(2024, 5, 20, 5, 40, tzinfo=UTC)
PEAK = datetime(2024, 5, 20, 6, 20, tzinfo=UTC)


def _dose_e(t: datetime) -> float:
    if t < ONSET:
        return 5.0
    if t < PEAK:
        return 60.0
    hours = (t - PEAK).total_seconds() / 3600
    return 5.0 + 295.0 * math.pow(0.7, hours)


def write_rad(d: Path) -> None:
    d.mkdir(parents=True)
    start = datetime(2024, 5, 18, 12, 0, tzinfo=UTC)
    for day in range(4):
        sol = 4188 + day
        t0 = start + timedelta(days=day)
        blocks = [
            "[FILE]",
            "SOFTWARE_VERSION=1.0",
            f"START_SOL={sol}",
            "",
        ]
        for n in range(36):  # une pose de 8 min toutes les 40 min
            t = t0 + timedelta(minutes=40 * n)
            short = day == 0 and n == 10  # pose interrompue : dose effondrée
            dose = 0.8 if short else _dose_e(t + timedelta(minutes=4))
            blocks += [
                f"[OBSERVATION: {n:02d}]",
                f'START_OBS_UTC="{t:%Y-%j %H:%M:%S}"',
                f"OBS_DURATION={300 if short else 480}",
                "",
                f"[COUNTERS: {n:02d}]",
                " ch name fast slow",
                "  2 F2H-x8 -1 109152",
                "",
                f"[DOSIMETRY: {n:02d}]",
                "DETECTOR_B_MASS=0.134208",
                "",
                f"[DOSIMETRY_TOTAL_DOSE_B: {n:02d}]",
                "",
                f"{dose * 0.95:.5f}",
                "",
                f"[DOSIMETRY_TOTAL_DOSE_E: {n:02d}]",
                "",
                f"{dose:.5f}",
                "",
                f"[DOSIMETRY_LET_B_A1: {n:02d}]",
                "NUM_ROWS=1",
                "",
            ]
        name = f"RAD_RDR_2024_{t0:%j}_{t0:%H}_{t0:%M}_{sol}_V00.TXT"
        (d / name).write_text("\n".join(blocks), encoding="ascii")


@pytest.fixture
def raw(tmp_path: Path) -> Path:
    root = tmp_path / "raw" / "jezero"
    write_meda(root / "meda")
    write_rad(root / "rad_may2024")
    return root


@pytest.fixture
def dataset(raw: Path, tmp_path: Path) -> ConditionsDataset:
    ds = import_all(raw)
    path = tmp_path / "work" / "jezero.json"
    ds.save(path)
    return ConditionsDataset.load(path)


def utc_at(mission_sol: int, lmst_h: float) -> datetime:
    """Premier instant UTC du sol de mission dont l'heure locale de Jezero vaut lmst_h."""
    t = EPOCH
    while True:
        mt = mars_time(t, 77.58, EPOCH)
        if mt.sol == mission_sol and abs(mt.lmst_hours - lmst_h) < 0.02:
            return t
        t += timedelta(minutes=1)


# -- import ---------------------------------------------------------------------------


def test_parse_lmst() -> None:
    assert parse_lmst("00030M12:30:00.000") == (30, 12.5)
    assert parse_lmst("0029 23:32:26") is None


def test_import_meda_bins(dataset: ConditionsDataset) -> None:
    assert dataset.sols == [30, 31]
    sol30 = dataset.meda[30]
    idx = bin_index(12.0)  # tranche 12:00-12:30 : moyenne de 12:00, 12:15
    expected_c = (_temp_k(12.0) + _temp_k(12.25)) / 2 - 273.15
    assert sol30.temperature_c[idx] == pytest.approx(expected_c, abs=1e-3)
    assert sol30.pressure_pa[idx] == pytest.approx(740.0)  # P02 retenu, pas P01
    assert all(v is None for v in sol30.wind_mps)  # pas de WS au sol 30
    assert dataset.meda[31].wind_mps[idx] == pytest.approx(4.0)  # moyenne des deux mâts
    assert "WE__0030___________CAL_PS__________________P01.CSV" not in dataset.meda_sources


def test_import_rad_event(dataset: ConditionsDataset) -> None:
    rad = dataset.rad
    assert rad is not None
    assert rad.baseline_e_ugy_h == pytest.approx(5.0)
    assert 200.0 < rad.peak_e_ugy_h <= 300.0  # pic entre deux poses
    assert abs((rad.onset_utc - ONSET).total_seconds()) < 45 * 60
    assert abs((rad.peak_utc - PEAK).total_seconds()) < 45 * 60
    assert rad.event_dose_ugy > 0
    assert len(rad.sources) == 4
    assert min(s.dose_e_ugy_h for s in rad.samples) > 1.0  # pose interrompue écartée


def test_rad_parser_and_outliers(raw: Path) -> None:
    path = sorted((raw / "rad_may2024").glob("*.TXT"))[0]
    samples = list(iter_rad_observations(path))
    assert len(samples) == 36
    assert samples[0].utc == datetime(2024, 5, 18, 12, 4, tzinfo=UTC)  # milieu de la pose
    assert len(drop_outliers(samples)) == 35


def test_cli_import_and_show(raw: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "cli.json"
    assert cli(["import", "--raw", str(raw), "--out", str(out)]) == 0
    assert out.stat().st_size < 200_000
    assert cli(["show", "--file", str(out)]) == 0
    text = capsys.readouterr().out
    assert "MEDA : 2 sols" in text and "RAD :" in text
    assert cli(["import", "--raw", str(tmp_path / "vide")]) == 1


# -- critère 1 : historique ------------------------------------------------------------


def test_historical_returns_imported_meda_values(dataset: ConditionsDataset) -> None:
    provider = HistoricalProvider(dataset=dataset)
    assert isinstance(provider, ConditionsProvider)
    # Sol de mission 2 rejoue le sol MEDA 31 (les sols importés tournent en boucle).
    t = utc_at(2, 12.1)
    cond = provider.current(t)
    sol31 = dataset.meda[31]
    idx = bin_index(mars_time(t, 77.58, EPOCH).lmst_hours)
    assert cond.temperature_c == pytest.approx(round(sol31.temperature_c[idx] or 0, 1))
    assert cond.pressure_pa == pytest.approx(741.0)
    assert cond.wind_mps == pytest.approx(4.0)
    assert cond.source is not None and "MEDA" in cond.source and "sol 31" in cond.source
    assert cond.dose_rate_usv_h == pytest.approx(Q_GCR * 5.0, abs=0.01)


def test_historical_fills_gaps_from_climatology(dataset: ConditionsDataset) -> None:
    cond = HistoricalProvider(dataset=dataset).current(utc_at(1, 12.1))  # sol MEDA 30
    assert cond.wind_mps == pytest.approx(4.0)  # vent du sol 31 (climatologie)
    assert cond.source is not None and "vent : climatologie" in cond.source


def test_forecast_uses_meda_climatology(dataset: ConditionsDataset) -> None:
    t = utc_at(1, 12.1)
    items = HistoricalProvider(dataset=dataset).forecast(t, 6)
    assert len(items) == 6
    assert items[0].pressure_pa == pytest.approx(740.5)  # moyenne des sols 30 et 31
    assert all("climatologique" in (c.source or "") for c in items)


def test_historical_without_data_says_model() -> None:
    cond = get_provider("historical").current(datetime(2026, 11, 14, 12, tzinfo=UTC))
    assert cond.source is not None and "modèle" in cond.source
    assert cond.temperature_c is not None and -90 < cond.temperature_c < 0


# -- critère 2 : solar-event -------------------------------------------------------------


def _peak_t() -> float:
    scen = next(s for s in list_scenarios() if s.id == "solar-event")
    return float(next(e.t_s for e in scen.events if e.kind == "peak"))


def _run(provider: ConditionsProvider, start: datetime, ts: list[float]) -> list[float]:
    return [provider.current(start + timedelta(seconds=t)).dose_rate_usv_h or 0.0 for t in ts]


def test_solar_event_from_rad_peaks_on_schedule(dataset: ConditionsDataset) -> None:
    mgr = ScenarioManager()
    start = datetime(2026, 11, 14, 10, tzinfo=UTC)
    mgr.start("solar-event", started_at=start)
    provider = ScenarioProvider(manager=mgr, dataset=dataset)
    assert dataset.rad is not None
    peak_t = 1200.0 + (dataset.rad.peak_utc - dataset.rad.onset_utc).total_seconds() / 54.0

    before, onset, peak, late = _run(provider, start, [600.0, ONSET_AT_S, peak_t, 1800.0])
    assert before == pytest.approx(Q_GCR * 5.0, abs=0.1)
    assert onset > DANGER_USV_H
    assert peak == pytest.approx(Q_GCR * 5.0 + dataset.rad.peak_e_ugy_h - 5.0, rel=0.01)
    assert before < late < peak
    grid = [t * 10.0 for t in range(361)]
    doses = _run(provider, start, grid)
    assert grid[doses.index(max(doses))] == pytest.approx(peak_t, abs=10.0)
    c = provider.current(start + timedelta(seconds=peak_t))
    assert c.space_weather.level == SpaceWeatherLevel.storm
    assert c.source is not None and "RAD Curiosity" in c.source
    # Reproductible : un second rejeu donne exactement la même courbe.
    mgr.start("solar-event", started_at=start + timedelta(days=1))
    assert _run(provider, start + timedelta(days=1), grid) == doses


def test_solar_event_fallback_without_data() -> None:
    assert _peak_t() == pytest.approx(FALLBACK_PEAK_AT_S)
    mgr = get_scenario_manager()
    start = datetime(2026, 11, 14, 10, tzinfo=UTC)
    mgr.start("solar-event", started_at=start)
    provider = get_provider("scenario", "solar-event")
    calm, onset, peak, after = _run(
        provider, start, [0.0, ONSET_AT_S, FALLBACK_PEAK_AT_S, DURATION_S + 100]
    )
    assert calm < 30.0 and onset > DANGER_USV_H and peak > 300.0 and after < 30.0
    assert "repli" in (provider.current(start).source or "")


def test_scenario_anchors_on_first_instant_like_a3() -> None:
    """A3 fait avancer l'horloge sans démarrer le gestionnaire de K1."""
    provider = get_provider("scenario", "solar-event")
    start = datetime(2026, 11, 14, 10, tzinfo=UTC)
    first = _run(provider, start, [0.0, ONSET_AT_S + 30])
    assert first[0] < 30.0 and first[1] > DANGER_USV_H
    # Nouveau départ : l'instant recule, le scénario repart de zéro.
    again = _run(provider, start + timedelta(seconds=5), [0.0])
    assert again[0] < 30.0


# -- critère 3 : hors ligne ------------------------------------------------------------------


class Offline:
    def fetch_current(self) -> SpaceWeather:
        raise ConnectionError("Network unreachable")


class Online:
    def __init__(self, sw: SpaceWeather) -> None:
        self.sw = sw

    def fetch_current(self) -> SpaceWeather:
        return self.sw


def test_live_persists_cache_and_serves_it_offline(tmp_path: Path) -> None:
    cache = tmp_path / "cache" / "donki.json"
    t1 = datetime(2026, 11, 14, 8, 30, tzinfo=UTC)
    sw = SpaceWeather(level=SpaceWeatherLevel.warning, event="FLR 2026-11-14", source="NASA DONKI")
    online = LiveProvider(client=Online(sw), cache_store=JsonFileCacheStore(cache)).current(t1)
    assert online.cached_at == t1 and online.space_weather.level == SpaceWeatherLevel.warning
    assert cache.is_file()

    # Redémarrage sans réseau : nouvelle instance, même fichier.
    t2 = datetime(2026, 11, 14, 12, tzinfo=UTC)
    offline = LiveProvider(client=Offline(), cache_store=JsonFileCacheStore(cache)).current(t2)
    assert offline.cached_at == t1
    assert offline.space_weather.event == "FLR 2026-11-14"
    assert offline.source is not None and "cache" in offline.source
    assert offline.temperature_c is not None  # le reste fonctionne


def test_live_without_cache_says_so() -> None:
    cond = LiveProvider(client=Offline(), cache_store=InMemoryCacheStore()).current(
        datetime(2026, 11, 14, tzinfo=UTC)
    )
    assert cond.cached_at is None
    assert cond.source is not None and "aucun cache" in cond.source


def test_live_forecast_fetches_once() -> None:
    calls = []

    class Counting(Online):
        def fetch_current(self) -> SpaceWeather:
            calls.append(1)
            return super().fetch_current()

    live = LiveProvider(client=Counting(SpaceWeather()), cache_store=InMemoryCacheStore())
    assert len(live.forecast(datetime(2026, 11, 14, tzinfo=UTC), 12)) == 12
    assert len(calls) == 1


def test_offline_everything_but_live_works(dataset: ConditionsDataset) -> None:
    now = datetime(2026, 11, 14, 12, tzinfo=UTC)
    engine = MedaClimatologyEngine(dataset=dataset)
    assert HistoricalProvider(climatology=engine).current(now).temperature_c is not None
    assert ScenarioProvider(climatology=engine).current(now).dose_rate_usv_h is not None


def test_donki_classification() -> None:
    assert classify([]).level == SpaceWeatherLevel.quiet
    notes = [
        {"messageType": "CME", "messageID": "a", "messageIssueTime": "2026-11-13T01:00Z"},
        {"messageType": "SEP", "messageID": "b", "messageIssueTime": "2026-11-14T01:00Z"},
    ]
    sw = classify(notes)
    assert sw.level == SpaceWeatherLevel.storm and sw.event == "SEP b"
