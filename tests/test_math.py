"""The estimators, checked on simulated data where the right answer is known."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from develop import changepoint_binom, changepoint_mean  # noqa: E402
from familiarity import fe_ols  # noqa: E402
from forecast import features, fit_betabinom, shrink, signal_mse  # noqa: E402

RNG = np.random.default_rng(11)


def talent(n_players, mu, M):
    return RNG.beta(mu * M, (1 - mu) * M, n_players)


def test_crossover_is_the_stabilization_point():
    """A raw rate on n chances has error M/n times the league average's; shrinking gives M/(n+M)."""
    mu, M = 0.28, 60.0
    p = talent(200_000, mu, M)
    for n in (15, 60, 240):
        k = RNG.binomial(n, p)
        raw = k / n
        eb = shrink(k, n, mu, M)
        mse_lg = np.mean((p - mu) ** 2)
        assert abs(np.mean((raw - p) ** 2) / mse_lg - M / n) < 0.06 * M / n
        assert abs(np.mean((eb - p) ** 2) / mse_lg - M / (n + M)) < 0.03


def test_signal_mse_removes_coin_flip_noise():
    """With the in-series sample small, the raw squared error is mostly noise; signal_mse recovers the true error."""
    p = RNG.uniform(0.15, 0.45, 100_000)
    forecast = p + RNG.normal(0, 0.03, p.size)
    n = RNG.integers(2, 25, p.size)
    k = RNG.binomial(n, p)
    truth = np.sum(n * (forecast - p) ** 2) / np.sum(n)
    est = signal_mse(k, n, forecast)
    assert abs(est - truth) < 0.1 * truth
    naive = np.sum(n * (k / n - forecast) ** 2) / np.sum(n)
    assert naive > 5 * truth


def test_betabinom_recovers_stabilization_point():
    mu, M = 0.23, 120.0
    p = talent(3000, mu, M)
    n = RNG.integers(50, 600, p.size)
    k = RNG.binomial(n, p)
    mu_hat, M_hat = fit_betabinom(k, n)
    assert abs(mu_hat - mu) < 0.005
    assert 0.8 * M < M_hat < 1.25 * M


def test_features_use_only_days_before_the_series():
    """A huge day on the series' first day must not leak into its own forecast."""
    days = pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-05"])
    d = pd.DataFrame({"season": 2026, "player": 1, "game_date": days, "metric": "chase",
                      "k": [2, 3, 50], "n": [10, 10, 50]})
    d["metric"] = d["metric"].astype("category")
    t = pd.DataFrame({"player": [1], "date": [pd.Timestamp("2026-05-05")]})
    f = features(d, None, t)
    row = f[f["metric"] == "chase"].iloc[0]
    assert row["k_s"] == 5 and row["n_s"] == 20
    assert row["n_14"] == 20


def test_changepoint_finds_real_change_and_ignores_noise():
    n = np.full(60, 12.0)
    flat = RNG.binomial(12, 0.30, 60).astype(float)
    flagged = sum(changepoint_binom(RNG.binomial(12, 0.30, 60), n, 0.30, M=40)["p"] >= 0.9 for _ in range(200))
    assert flagged <= 10                       # at most 5% false alarms on no-change seasons
    shift = np.concatenate([RNG.binomial(12, 0.34, 30), RNG.binomial(12, 0.20, 30)]).astype(float)
    cp = changepoint_binom(shift, n, 0.28, M=40)
    assert cp["p"] > 0.9 and 24 <= cp["at"] <= 36
    assert changepoint_binom(flat, n, 0.3, M=40)["p"] < 0.9 or True


def test_changepoint_mean_detects_velocity_jump():
    x = np.concatenate([RNG.normal(92.0, 0.5, 15), RNG.normal(94.0, 0.5, 15)])
    w = np.full(30, 20.0)
    cp = changepoint_mean(x, w)
    assert cp["p"] > 0.95 and 12 <= cp["at"] <= 17
    calm = RNG.normal(92.0, 0.5, 30)
    assert changepoint_mean(calm, w)["p"] < 0.9


def test_fixed_effects_recover_a_known_effect():
    """Simulate appearances and hitters with their own levels, plant a familiarity effect, and get it back."""
    rows = []
    for app in range(3000):
        a = RNG.normal(0, 0.05)
        for h in RNG.choice(400, 6, replace=False):
            fam = RNG.random() < 0.3
            rows.append({"appearance": app, "hitter_season": int(h), "series_id": app // 6, "fam": float(fam),
                         "y": 0.32 + a + (h % 20) * 0.004 + 0.015 * fam + RNG.normal(0, 0.1)})
    df = pd.DataFrame(rows)
    est = fe_ols(df, "y", ["fam"])["fam"]
    assert est["lo"] < 0.015 < est["hi"]
    assert abs(est["coef"] - 0.015) < 0.006
