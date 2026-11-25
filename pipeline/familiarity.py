"""Does the book go stale by Sunday? Do hitters catch up to a pitcher they already saw earlier in the series?

    python pipeline/familiarity.py AAA       -> data/out/familiarity_AAA.json

Design: within the same pitcher appearance, compare hitters who already faced him in an earlier game of the series
with hitters seeing him for the first time that week. Two sets of fixed effects do the controlling:
  appearance (game x pitcher): his stuff, fatigue and command that day, the park, the weather, the umpire
  hitter x season: how good the hitter is
plus platoon side and the within-game times-through-the-order count. Outcomes per plate appearance: strikeout,
walk, and expected wOBA (xwOBA on contact, actual value for walks and strikeouts). Standard errors are clustered by series.
The within-game times-through-the-order penalty is a known effect, so it doubles as a check that the design can see one.
"""
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"

PA_SQL = """
with pa as (
  select p.season, gs.series_id, gs.game_in_series, p.game_pk, p.game_date, p.batter, p.pitcher, p.ab,
         p.stand, p.p_throws, p.tto, p.inning, p.events, p.woba_value, p.woba_denom, p.xwoba, p.is_bip,
         p.bat_team, p.fld_team
  from pitches p join game_series gs using (game_pk) join series s using (series_id)
  where p.level = '{level}' and p.game_type = 'R' and s.n_games >= 3
    and p.events is not null and p.events not in ('truncated_pa', 'intent_walk', 'catcher_interf')
    and p.woba_denom = 1
), seen as (
  select *,
    -- plate appearances against this pitcher in earlier games of this series
    count(*) over (partition by series_id, batter, pitcher order by game_in_series
                   range between unbounded preceding and 1 preceding) as prior_series_pa
  from pa
)
select * from seen order by game_pk, ab
"""


def load(level):
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    df = con.execute(PA_SQL.format(level=level)).df()
    # earlier-in-season meetings that happened before this series began
    before = con.execute(f"""
      with pa as (
        select p.season, gs.series_id, p.game_date, p.batter, p.pitcher
        from pitches p join game_series gs using (game_pk)
        where p.level = '{level}' and p.game_type = 'R' and p.events is not null
      ), starts as (select series_id, min(game_date) d0 from pa group by 1)
      select a.series_id, a.batter, a.pitcher, count(b.batter) as prior_season_pa
      from (select distinct series_id, season, batter, pitcher from pa) a
      join starts s on s.series_id = a.series_id
      left join pa b on b.season = a.season and b.batter = a.batter and b.pitcher = a.pitcher and b.game_date < s.d0
      group by 1, 2, 3""").df()
    con.close()
    df = df.merge(before, on=["series_id", "batter", "pitcher"], how="left")
    df["prior_season_pa"] = df["prior_season_pa"].fillna(0)
    df["k"] = df["events"].isin(["strikeout", "strikeout_double_play"]).astype(float)
    df["bb"] = (df["events"] == "walk").astype(float)
    df["xw"] = np.where(df["k"] == 1, 0.0,
                        np.where(df["is_bip"] & df["xwoba"].notna(), df["xwoba"], df["woba_value"].fillna(0)))
    df["platoon"] = (df["stand"] != df["p_throws"]).astype(float)
    df["fam"] = (df["prior_series_pa"] > 0).astype(float)
    df["fam1"] = (df["prior_series_pa"] == 1).astype(float)
    df["fam2"] = (df["prior_series_pa"] >= 2).astype(float)
    df["seen_season"] = (df["prior_season_pa"] > 0).astype(float)
    df["tto2"] = (df["tto"] == 2).astype(float)
    df["tto3"] = (df["tto"] >= 3).astype(float)
    df["appearance"] = df["game_pk"].astype(str) + "-" + df["pitcher"].astype(str)
    df["hitter_season"] = df["batter"].astype(str) + "-" + df["season"].astype(str)
    return df


def demean(df, cols, groups, tol=1e-9, max_iter=200):
    """Alternating projections: remove both sets of fixed effects from each column."""
    X = df[cols].to_numpy(float).copy()
    codes = [pd.factorize(df[g])[0] for g in groups]
    counts = [np.bincount(c) for c in codes]
    for _ in range(max_iter):
        delta = 0.0
        for c, n in zip(codes, counts):
            means = np.vstack([np.bincount(c, weights=X[:, j]) for j in range(X.shape[1])]).T / n[:, None]
            step = means[c]
            X -= step
            delta = max(delta, float(np.abs(step).max()))
        if delta < tol:
            break
    return X


def fe_ols(df, y, xs, groups=("appearance", "hitter_season"), cluster="series_id"):
    # singletons in either fixed effect carry no information; drop them repeatedly
    d = df.copy()
    while True:
        keep = np.ones(len(d), bool)
        for g in groups:
            keep &= d.groupby(g)[g].transform("size").to_numpy() > 1
        if keep.all():
            break
        d = d[keep]
    Z = demean(d, [y] + xs, list(groups))
    yv, X = Z[:, 0], Z[:, 1:]
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ yv
    e = yv - X @ beta
    cl = pd.factorize(d[cluster])[0]
    G = cl.max() + 1
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, cl, X * e[:, None])
    meat = S.T @ S
    n, k = X.shape
    adj = G / (G - 1) * (n - 1) / (n - k)
    V = adj * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return {x: {"coef": float(b), "se": float(s), "lo": float(b - 1.96 * s), "hi": float(b + 1.96 * s)}
            for x, b, s in zip(xs, beta, se)} | {"_n": int(n), "_clusters": int(G)}


def run(level):
    df = load(level)
    res = {"level": level, "seasons": sorted(df["season"].unique().tolist()), "pas": int(len(df)),
           "familiar_pas": int(df["fam"].sum()), "mean": {y: float(df[y].mean()) for y in ("k", "bb", "xw")}}
    xs = ["fam", "seen_season", "platoon", "tto2", "tto3"]
    res["main"] = {y: fe_ols(df, y, xs) for y in ("xw", "k", "bb")}
    res["dose"] = {y: fe_ols(df, y, ["fam1", "fam2", "seen_season", "platoon", "tto2", "tto3"]) for y in ("xw", "k")}
    # relievers only: the pitchers hitters actually see twice in a week
    first_inning = df.groupby("appearance")["inning"].transform("min")
    rel = df[first_inning > 1]
    res["relievers"] = {y: fe_ols(rel, y, xs) for y in ("xw", "k")}
    res["relievers"]["_pas"] = int(len(rel))
    res["relievers"]["_familiar_pas"] = int(rel["fam"].sum())
    # by game of the series (does a lineup get better as the week goes on?) with hitter-season and pitcher FE
    df["g"] = df["game_in_series"].clip(upper=6)
    for g in range(2, 7):
        df[f"g{g}"] = (df["g"] == g).astype(float)
    df["pitcher_season"] = df["pitcher"].astype(str) + "-" + df["season"].astype(str)
    res["by_game"] = fe_ols(df, "xw", [f"g{g}" for g in range(2, 7)] + ["platoon", "tto2", "tto3"],
                            groups=("pitcher_season", "hitter_season"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"familiarity_{level}.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    for lv in sys.argv[1:] or ["AAA"]:
        r = run(lv)
        print(lv, r["pas"], "PA,", r["familiar_pas"], "familiar")
        for y, row in r["main"].items():
            print(" ", y, {k: (round(v["coef"], 4), round(v["se"], 4)) for k, v in row.items() if not k.startswith("_")})
        print("  relievers xw", {k: (round(v["coef"], 4), round(v["se"], 4))
                                 for k, v in r["relievers"]["xw"].items() if not k.startswith("_")})
        print("  by game xw", {k: (round(v["coef"], 4), round(v["se"], 4))
                               for k, v in r["by_game"].items() if not k.startswith("_")})
