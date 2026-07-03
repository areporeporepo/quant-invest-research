"""Unit tests for the indicator math. Pure, offline, deterministic."""

import math

from app import indicators as ind
from app.analysis import build_snapshot
from app.data_providers import _stub_series


def test_total_return():
    assert math.isclose(ind.total_return([100, 110]), 0.10)
    assert math.isclose(ind.total_return([100, 50]), -0.50)
    assert ind.total_return([100]) is None


def test_daily_returns():
    r = ind.daily_returns([100, 110, 99])
    assert math.isclose(r[0], 0.10)
    assert math.isclose(r[1], 99 / 110 - 1)


def test_sma_and_ema_need_enough_data():
    assert ind.sma([1, 2], 5) is None
    assert ind.sma([2, 4, 6], 3) == 4.0
    assert ind.ema([1, 2], 5) is None
    assert ind.ema([1, 2, 3, 4, 5], 3) is not None


def test_rsi_bounds():
    up = list(range(1, 40))  # strictly rising -> RSI at the ceiling
    assert ind.rsi(up, 14) == 100.0
    assert ind.rsi([1, 2], 14) is None


def test_max_drawdown_is_nonpositive():
    dd = ind.max_drawdown([100, 120, 60, 80])
    assert dd is not None and dd <= 0
    assert math.isclose(dd, 60 / 120 - 1)  # worst peak(120)->trough(60)


def test_sharpe_handles_flat_series():
    assert ind.sharpe_ratio([100, 100, 100]) is None  # zero vol -> undefined


def test_stub_pipeline_is_deterministic():
    # Use the stub directly so tests stay offline regardless of PRICE_PROVIDER.
    a = _stub_series("VHM")
    b = _stub_series("VHM")
    assert a.closes == b.closes
    assert a.is_real is False


def test_build_snapshot_smoke():
    series = _stub_series("VHM")
    snap = build_snapshot(series)
    assert snap.ticker == "VHM"
    assert snap.n_observations == len(series.closes)
    assert snap.trend in {"uptrend", "downtrend", "mixed", "insufficient-data"}
    assert snap.is_real_data is False
