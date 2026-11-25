"""The forecast behind every number on the card.

For a player on a given Monday, each metric's forecast is a beta-binomial posterior mean:

    p_hat = (k_eff + M * mu) / (n_eff + M)

mu is the league rate (season to date, steadied with last season's), and k_eff / n_eff are his successes and chances,
with recent games weighted more (half-life h days) and last season counted at weight w.
M is the metric's stabilization point: the number of chances at which his own data and the league average get equal say.
Splits and zone halves shrink toward the player's own overall forecast (times the league split factor) instead.
The same functions build the backtest and the packet, so the packet prints exactly what was tested.
"""
import numpy as np
import pandas as pd
from scipy import stats

from metrics import BY_KEY, METRICS

HALF_LIVES = [7, 14, 28, 56, 112, None]        # None: every game this season counts the same
PRIOR_WEIGHTS = [0.0, 0.25, 0.5, 0.75, 1.0]
M_GRID = np.unique(np.round(np.geomspace(4, 4000, 70)))
LEAGUE_PSEUDO = 20000                           # chances of last season's league rate blended into the season-to-date rate
Z80 = stats.norm.ppf(0.9)


def season_start(season):
    return pd.Timestamp(f"{season}-03-01")


def _cum(daily_df):
    """Cumulative sums per player and metric, by date, with decayed versions for each half-life."""
    d = daily_df.sort_values(["metric", "player", "game_date"]).copy()
    d["player"] = d["player"].astype("int64")
    d["game_date"] = pd.to_datetime(d["game_date"]).astype("datetime64[ns]")
    t = (d["game_date"] - season_start(int(d["season"].iloc[0]))).dt.days.to_numpy(float)
    g = d.groupby(["metric", "player"], observed=True)
    d["ck"] = g["k"].cumsum()
    d["cn"] = g["n"].cumsum()
    for h in HALF_LIVES:
        if h is None:
            continue
        w = np.exp2(t / h)
        d[f"wk{h}"] = d["k"] * w
        d[f"wn{h}"] = d["n"] * w
        g = d.groupby(["metric", "player"], observed=True)
        d[f"ck{h}"] = g[f"wk{h}"].cumsum()
        d[f"cn{h}"] = g[f"wn{h}"].cumsum()
        d = d.drop(columns=[f"wk{h}", f"wn{h}"])
    return d


def _asof(cum, targets, on_col, cols, prefix):
    """For each target row, the cumulative values on the last game day strictly before targets[on_col]."""
    left = targets[["row", "player", "metric", on_col]].rename(columns={on_col: "game_date"})
    left = left.sort_values("game_date")
    right = cum[["player", "metric", "game_date"] + cols].sort_values("game_date")
    left["metric"] = left["metric"].astype(str)
    right = right.assign(metric=right["metric"].astype(str))
    out = pd.merge_asof(left, right, on="game_date", by=["player", "metric"], allow_exact_matches=False)
    out = out.set_index("row")[cols].fillna(0.0)
    out.columns = [f"{prefix}{c}" for c in cols]
    return out


def features(daily_df, prior_daily_df, targets):
    """targets: DataFrame with player, date (the series' first game). Returns one row per target x metric with
    season-to-date, last-14-day, decayed and last-season counts, plus the league rates."""
    season = int(daily_df["season"].iloc[0])
    metrics = [x["key"] for x in METRICS]
    t = targets[["player", "date"]].drop_duplicates().reset_index(drop=True)
    t["player"] = t["player"].astype("int64")
    t = t.merge(pd.DataFrame({"metric": metrics}), how="cross")
    t["date"] = pd.to_datetime(t["date"]).astype("datetime64[ns]")
    t["date14"] = t["date"] - pd.to_timedelta(14, unit="D")
    t["row"] = np.arange(len(t))
    cum = _cum(daily_df)
    cols = ["ck", "cn"] + [f"c{a}{h}" for h in HALF_LIVES if h for a in ("k", "n")]
    now = _asof(cum, t, "date", cols, "")
    before14 = _asof(cum, t, "date14", ["ck", "cn"], "b14_")
    t = t.set_index("row").join(now).join(before14)
    t["k_s"], t["n_s"] = t["ck"], t["cn"]
    t["k_14"], t["n_14"] = t["ck"] - t["b14_ck"], t["cn"] - t["b14_cn"]
    days = (t["date"] - season_start(season)).dt.days.to_numpy(float)
    for h in HALF_LIVES:
        if h is None:
            t["k_dNone"], t["n_dNone"] = t["k_s"], t["n_s"]
        else:
            scale = np.exp2(-days / h)
            t[f"k_d{h}"], t[f"n_d{h}"] = t[f"ck{h}"] * scale, t[f"cn{h}"] * scale
    t = t.drop(columns=[c for c in t.columns if c.startswith(("ck", "cn", "b14_"))])
    # last season, whole
    if prior_daily_df is not None and len(prior_daily_df):
        prev = prior_daily_df.groupby(["player", "metric"], observed=True)[["k", "n"]].sum().reset_index()
        prev["metric"] = prev["metric"].astype(str)
        prev["player"] = prev["player"].astype("int64")
        t = t.merge(prev.rename(columns={"k": "k_p", "n": "n_p"}), on=["player", "metric"], how="left")
    else:
        t["k_p"], t["n_p"] = 0.0, 0.0
    t[["k_p", "n_p"]] = t[["k_p", "n_p"]].fillna(0.0)
    # league rate on that date: season to date, steadied by last season's league rate
    lg_prev = league_rates(prior_daily_df) if prior_daily_df is not None and len(prior_daily_df) else league_rates(daily_df)
    lg = daily_df.groupby(["metric", "game_date"], observed=True)[["k", "n"]].sum().reset_index()
    lg["metric"] = lg["metric"].astype(str)
    lg["game_date"] = pd.to_datetime(lg["game_date"]).astype("datetime64[ns]")
    lg = lg.sort_values(["metric", "game_date"])
    lg["K"] = lg.groupby("metric")["k"].cumsum()
    lg["N"] = lg.groupby("metric")["n"].cumsum()
    t = t.reset_index(drop=True)
    left = t[["metric", "date"]].rename(columns={"date": "game_date"})
    left["_i"] = np.arange(len(left))
    left = left.sort_values("game_date")
    m = pd.merge_asof(left, lg[["metric", "game_date", "K", "N"]].sort_values("game_date"), on="game_date",
                      by="metric", allow_exact_matches=False).set_index("_i")[["K", "N"]].fillna(0.0)
    t = t.join(m)
    prev_mu = t["metric"].map(lg_prev).fillna(0.0)
    t["mu"] = (t["K"] + prev_mu * LEAGUE_PSEUDO) / (t["N"] + LEAGUE_PSEUDO)
    return t.drop(columns=["K", "N", "date14"])


def league_rates(daily_df):
    s = daily_df.groupby("metric", observed=True)[["k", "n"]].sum()
    s.index = s.index.astype(str)
    return (s["k"] / s["n"]).to_dict()


def shrink(k, n, center, M):
    return (k + M * center) / (n + M)


def predict(feat, params):
    """Add forecasts to a features table. params: {metric: {"h":..., "w":..., "M":...}}.
    Parents (overall rates) are computed first; splits and zone halves shrink toward them."""
    f = feat.copy()
    f["center"] = f["mu"]
    f["k_eff"] = 0.0
    f["n_eff"] = 0.0
    f["M"] = np.nan
    order = [x["key"] for x in METRICS if not x["parent"]] + [x["key"] for x in METRICS if x["parent"]]
    est = {}
    for key in order:
        rows = f.index[f["metric"] == key]
        if len(rows) == 0 or key not in params:
            continue
        p = params[key]
        h = p["h"]
        k = f.loc[rows, f"k_d{h}"] + p["w"] * f.loc[rows, "k_p"]
        n = f.loc[rows, f"n_d{h}"] + p["w"] * f.loc[rows, "n_p"]
        center = f.loc[rows, "mu"]
        parent = BY_KEY[key]["parent"]
        if parent and parent in est:
            par = est[parent]
            lg_parent = f.loc[rows, ["player", "date"]].merge(
                par[["player", "date", "sdf", "mu"]], on=["player", "date"], how="left")
            factor = (f.loc[rows, "mu"].to_numpy() / lg_parent["mu"].to_numpy())
            center = pd.Series(np.clip(lg_parent["sdf"].to_numpy() * factor, 1e-4, 1 - 1e-4), index=rows)
        f.loc[rows, "k_eff"] = k
        f.loc[rows, "n_eff"] = n
        f.loc[rows, "center"] = center
        f.loc[rows, "M"] = p["M"]
        f.loc[rows, "sdf"] = shrink(k, n, center, p["M"])
        est[key] = f.loc[rows, ["player", "date", "sdf", "mu"]]
    f["season_raw"] = np.where(f["n_s"] > 0, f["k_s"] / f["n_s"].where(f["n_s"] > 0, 1), np.nan)
    f["last14_raw"] = np.where(f["n_14"] > 0, f["k_14"] / f["n_14"].where(f["n_14"] > 0, 1), np.nan)
    f["trust"] = f["n_eff"] / (f["n_eff"] + f["M"])
    a = f["k_eff"] + f["M"] * f["center"]
    b = (f["n_eff"] - f["k_eff"]) + f["M"] * (1 - f["center"])
    f["alpha"], f["beta"] = a, b
    f["lo80"] = stats.beta.ppf(0.1, a.clip(lower=1e-6), b.clip(lower=1e-6))
    f["hi80"] = stats.beta.ppf(0.9, a.clip(lower=1e-6), b.clip(lower=1e-6))
    return f


def brier(k, n, p):
    """Sum over chances of the squared error of forecast p: k chances were 1, n - k were 0."""
    return k * (1 - p) ** 2 + (n - k) * p ** 2


def signal_mse(k, n, p):
    """Unbiased estimate, per series, of (true in-series rate - forecast)^2, removing the coin-flip noise
    of a small in-series sample. Needs n >= 2. Returns the n-weighted mean."""
    k, n, p = np.asarray(k, float), np.asarray(n, float), np.asarray(p, float)
    ok = n >= 2
    k, n, p = k[ok], n[ok], p[ok]
    e = (k / n - p) ** 2 - k * (n - k) / (n ** 2 * (n - 1))
    return float(np.sum(n * e) / np.sum(n))


def fit_betabinom(k, n):
    """Maximum-likelihood beta-binomial across players: returns (mu, M). M is the stabilization point."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    mu0 = k.sum() / n.sum()

    def nll(x):
        mu, M = 1 / (1 + np.exp(-x[0])), np.exp(x[1])
        a, b = mu * M, (1 - mu) * M
        return -np.sum(stats.betabinom.logpmf(k, n, a, b))

    from scipy.optimize import minimize
    best = None
    for logM in (np.log(30), np.log(150), np.log(800)):
        r = minimize(nll, [np.log(mu0 / (1 - mu0)), logM], method="Nelder-Mead",
                     options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": 4000})
        if best is None or r.fun < best.fun:
            best = r
    return 1 / (1 + np.exp(-best.x[0])), float(np.exp(best.x[1]))
