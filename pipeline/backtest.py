"""Verify the advance card the way forecasters verify a forecast.

    python pipeline/backtest.py            -> data/out/params_{level}.json, data/out/backtest_{level}.json

Each (hitter, series) is one forecast: on the Monday before a series, predict each card number for the six games ahead.
Tuning (half-life, last-season weight, M) uses 2025 series only. The 2026 series are the test, never seen in tuning.
Methods compared on 2026:
  league   - assume a league-average hitter (what you know with no report at all)
  season   - his raw season-to-date number (what a standard card prints)
  last14   - his raw last-14-days number (the "hot/cold" line on a standard card)
  sdf      - the Six-Day Forecast: shrunk toward league average by how much data he has
Score: mean squared distance from his true in-series rate (coin-flip noise of the small in-series sample removed),
reported as a ratio to the league-average forecast. Below 1 beats knowing nothing; above 1 is worse than knowing nothing.
"""
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import (HALF_LIVES, M_GRID, PRIOR_WEIGHTS, brier, features, fit_betabinom,  # noqa: E402
                      predict, shrink, signal_mse)
from metrics import BY_KEY, METRICS, daily, in_series  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
CACHE = ROOT / "data" / "cache"
TRAIN, TEST = 2025, 2026
MIN_GAMES = 3          # one- and two-game "series" are mostly suspended games finished on another trip
BOOT = 400
RNG = np.random.default_rng(20260915)


def load(con, level):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (("daily", daily), ("series", in_series)):
        path = CACHE / f"{name}_{level}.parquet"
        if not path.exists():
            fn(con, level).to_parquet(path)
        out[name] = pd.read_parquet(path)
    out["series_info"] = con.execute(f"select * from series where level = '{level}' and game_type = 'R'").df()
    return out


def observations(data, season, prior):
    """In-series counts joined to the Monday features of each hitter in each series of a season."""
    s = data["series"][data["series"]["season"] == season].copy()
    s["metric"] = s["metric"].astype(str)
    info = data["series_info"]
    info = info[info["n_games"] >= MIN_GAMES][["series_id", "start_date", "n_games"]]
    s = s.merge(info, on="series_id")
    targets = s[["player", "start_date"]].drop_duplicates().rename(columns={"start_date": "date"})
    d = data["daily"]
    feat = features(d[d["season"] == season], d[d["season"] == prior] if prior else None, targets)
    s["date"] = pd.to_datetime(s["start_date"]).astype("datetime64[ns]")
    obs = s.merge(feat, on=["player", "date", "metric"], how="inner")
    return obs, feat


def fit_params(obs):
    """Grid search per metric for the half-life, last-season weight and M that minimize the 2025 Brier score."""
    params = {}
    done = {}
    order = [x["key"] for x in METRICS if not x["parent"]] + [x["key"] for x in METRICS if x["parent"]]
    for key in order:
        o = obs[obs["metric"] == key]
        if len(o) < 50:
            continue
        k_obs, n_obs = o["k"].to_numpy(float), o["n"].to_numpy(float)
        center = o["mu"].to_numpy(float)
        parent = BY_KEY[key]["parent"]
        if parent and parent in done:
            par = done[parent].drop_duplicates(["player", "date"]).set_index(["player", "date"])
            idx = pd.MultiIndex.from_frame(o[["player", "date"]])
            par_sdf = par["sdf"].reindex(idx).to_numpy(float)
            par_mu = par["mu"].reindex(idx).to_numpy(float)
            center = np.clip(par_sdf * center / par_mu, 1e-4, 1 - 1e-4)
        best = None
        for h in HALF_LIVES:
            kd, nd = o[f"k_d{h}"].to_numpy(float), o[f"n_d{h}"].to_numpy(float)
            for w in PRIOR_WEIGHTS:
                k = kd + w * o["k_p"].to_numpy(float)
                n = nd + w * o["n_p"].to_numpy(float)
                p = (k[:, None] + M_GRID[None, :] * center[:, None]) / (n[:, None] + M_GRID[None, :])
                loss = brier(k_obs[:, None], n_obs[:, None], p).sum(axis=0)
                j = int(np.argmin(loss))
                if best is None or loss[j] < best[0]:
                    best = (loss[j], h, w, float(M_GRID[j]))
        _, h, w, M = best
        params[key] = {"h": h, "w": w, "M": M}
        k = o[f"k_d{h}"].to_numpy(float) + w * o["k_p"].to_numpy(float)
        n = o[f"n_d{h}"].to_numpy(float) + w * o["n_p"].to_numpy(float)
        done[key] = o[["player", "date", "mu"]].assign(sdf=shrink(k, n, center, M))
    return params


def stabilization(data, season):
    """Season-total beta-binomial fit for each metric: (league rate, M)."""
    d = data["daily"][data["daily"]["season"] == season]
    tot = d.groupby(["metric", "player"], observed=True)[["k", "n"]].sum().reset_index()
    tot["metric"] = tot["metric"].astype(str)
    out = {}
    for key, g in tot.groupby("metric"):
        g = g[g["n"] > 0]
        if len(g) < 30 or BY_KEY[key]["parent"]:
            continue
        mu, M = fit_betabinom(g["k"], g["n"])
        out[key] = {"mu": mu, "M": M}
    return out


def score(o, col):
    p = o[col].fillna(o["mu"]).to_numpy(float)
    return signal_mse(o["k"], o["n"], p)


def evaluate(pred, methods):
    """Ratio of each method's error to the league-average forecast, with series-bootstrap 90% intervals."""
    res = {}
    for key, o in pred.groupby("metric"):
        o = o[o["n"] >= 2]
        if len(o) < 100:
            continue
        base = score(o, "mu")
        row = {"n_obs": int(len(o)), "mse_league": base}
        sids = o["series_id"].unique()
        groups = {sid: idx for sid, idx in o.groupby("series_id").indices.items()}
        boots = {m: [] for m in methods}
        for _ in range(BOOT):
            pick = RNG.choice(sids, size=len(sids), replace=True)
            ix = np.concatenate([groups[s] for s in pick])
            ob = o.iloc[ix]
            b0 = score(ob, "mu")
            for m in methods:
                boots[m].append(score(ob, m) / b0)
        for m in methods:
            r = score(o, m) / base
            lo, hi = np.percentile(boots[m], [5, 95])
            row[m] = {"ratio": r, "lo": float(lo), "hi": float(hi)}
        res[key] = row
    return res


def crossover(pred, stab, key, bins=(1, 5, 10, 20, 40, 80, 160, 320, 640, 1280, 5000)):
    """Error of the raw season number vs the league average, by how many chances he had before the series."""
    o = pred[(pred["metric"] == key) & (pred["n"] >= 2) & (pred["n_s"] > 0)]
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        b = o[(o["n_s"] >= lo) & (o["n_s"] < hi)]
        if len(b) < 60:
            continue
        base = score(b, "mu")
        if base <= 0:
            continue
        out.append({"lo": lo, "hi": hi, "n_mid": float(b["n_s"].median()), "obs": int(len(b)),
                    "season": score(b, "season_raw") / base, "sdf": score(b, "sdf") / base})
    M = stab.get(key, {}).get("M")
    return {"bins": out, "M": M}


def calibration(pred):
    """Randomized PIT of the in-series count under the beta-binomial posterior predictive."""
    out = {}
    for key, o in pred.groupby("metric"):
        o = o[(o["n"] >= 1) & o["alpha"].notna()]
        if len(o) < 200:
            continue
        a, b = o["alpha"].clip(lower=1e-6).to_numpy(), o["beta"].clip(lower=1e-6).to_numpy()
        n, k = o["n"].to_numpy(), o["k"].to_numpy()
        lo = stats.betabinom.cdf(k - 1, n, a, b)
        hi = stats.betabinom.cdf(k, n, a, b)
        u = lo + RNG.random(len(o)) * (hi - lo)
        naive_p = o["season_raw"].fillna(o["mu"]).clip(1e-4, 1 - 1e-4).to_numpy()
        nlo = stats.binom.cdf(k - 1, n, naive_p)
        nhi = stats.binom.cdf(k, n, naive_p)
        nu = nlo + RNG.random(len(o)) * (nhi - nlo)
        out[key] = {
            "coverage80": float(np.mean((u > 0.1) & (u < 0.9))),
            "naive_coverage80": float(np.mean((nu > 0.1) & (nu < 0.9))),
            "pit_hist": np.histogram(u, bins=10, range=(0, 1))[0].tolist(),
            "naive_pit_hist": np.histogram(nu, bins=10, range=(0, 1))[0].tolist(),
            "obs": int(len(o)),
        }
    return out


def run(level):
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    data = load(con, level)
    con.close()
    train, _ = observations(data, TRAIN, TRAIN - 1)
    params = fit_params(train)
    test, test_feat = observations(data, TEST, TEST - 1)
    pred_feat = predict(test_feat, params)
    keep = ["player", "date", "metric", "sdf", "season_raw", "last14_raw", "trust", "alpha", "beta", "n_eff", "M",
            "center"]
    pred = test[["series_id", "team", "player", "date", "metric", "k", "n", "n_s", "n_14", "mu"]].merge(
        pred_feat[keep], on=["player", "date", "metric"], how="left")
    pred = pred.sort_values(["series_id", "team", "player", "metric"], kind="mergesort").reset_index(drop=True)
    stab = {s: stabilization(data, s) for s in (TRAIN, TEST)}
    result = {
        "level": level, "train": TRAIN, "test": TEST,
        "n_series_test": int(pred["series_id"].nunique()),
        "n_hitter_series_test": int(pred[["series_id", "player"]].drop_duplicates().shape[0]),
        "methods": evaluate(pred, ["season_raw", "last14_raw", "sdf"]),
        "stabilization": stab,
        "crossover": {k: crossover(pred, stab[TEST], k) for k in ("chase", "whiff", "k", "avg", "babip", "hardhit")},
        "calibration": calibration(pred),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"params_{level}.json").write_text(json.dumps(params, indent=1))
    (OUT / f"backtest_{level}.json").write_text(json.dumps(result, indent=1, default=float))
    pred.to_parquet(CACHE / f"pred_{level}_{TEST}.parquet")
    return params, result


if __name__ == "__main__":
    for lv in sys.argv[1:] or ["AAA"]:
        params, result = run(lv)
        print(lv, "test series:", result["n_series_test"], "hitter-series:", result["n_hitter_series_test"])
        for key, row in result["methods"].items():
            print(f"  {key:10s} M={params[key]['M']:6.0f} h={params[key]['h']} w={params[key]['w']}"
                  f"  season {row['season_raw']['ratio']:.2f}  last14 {row['last14_raw']['ratio']:.2f}"
                  f"  sdf {row['sdf']['ratio']:.2f}")
