"""Is it working? Development tracking for the Marlins' Jacksonville and Jupiter affiliates.

    python pipeline/develop.py      -> data/out/develop.json

Three parts, all 2026:
1. How long until you know. After a player changes something, how many weeks of his normal workload does it take
   before the change is clear of noise (90% confidence)? Rates (chase, whiffs, contact) are binomial; pitch traits
   (velocity, shape, arm angle) are game averages whose game-to-game noise is measured from every Triple-A pitcher.
2. Pitcher change receipts. A Bayesian test for a single change in each pitch's velocity, movement, spin, arm angle
   and extension, after removing each park's camera offset (the same pitch reads differently in different parks).
   Changes to several pitches on the same day are one event. New pitches are dated from when they became part of the
   mix, and a "new" label whose speed and movement match a pitch that disappeared the same day is a relabel, not a pitch.
   Each event is graded on results: whiffs per swing and called-plus-swinging strikes, before and after.
3. Hitter tracking. First half against second half for each regular, graded the same way.
False alarms: every test is also run with the player's games shuffled into random order, which keeps the noise and
removes any real change.
"""
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import special, stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import BY_KEY  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
SEASON = 2026
AFFILIATES = {"AAA": [564], "FSL": [479]}          # Jacksonville Jumbo Shrimp, Jupiter Hammerheads
PRIOR_CHANGE = 0.15                               # prior probability that a pitch changed at all this season
MIN_SIDE = 0.2                                    # each side of a change needs 20% of the pitches
REPORT_P = 0.9
Z90 = stats.norm.ppf(0.95)                        # a 90% interval for the change excludes zero
PITCH_SHAPE = {"velo": ("mph", 1.0), "ivb": ("in", 2.0), "hb": ("in", 2.0), "spin": ("rpm", 150.0),
               "arm_angle": ("deg", 4.0), "ext": ("ft", 0.3)}
SHAPE_SQL = {"velo": "velo", "ivb": "pfx_z * 12", "hb": "pfx_x * case when p_throws = 'R' then -12 else 12 end",
             "spin": "spin", "arm_angle": "arm_angle", "ext": "ext"}
HITTER_TRACK = ["chase", "whiff", "zcontact", "hardhit"]
HITTER_POLARITY = {"chase": -1, "whiff": -1, "zcontact": 1, "hardhit": 1}
RNG = np.random.default_rng(7)


def log_beta(a, b):
    return special.gammaln(a) + special.gammaln(b) - special.gammaln(a + b)


def changepoint_binom(k, n, mu, M=None, prior_change=PRIOR_CHANGE, min_side=MIN_SIDE):
    """Posterior probability of a single change in a binomial rate, and where. Each segment gets a Beta prior
    with mean mu and weight M."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    M = M or 10.0
    a0, b0 = mu * M, (1 - mu) * M
    K, N = k.sum(), n.sum()
    l0 = log_beta(a0 + K, b0 + N - K) - log_beta(a0, b0)
    ck, cn = np.cumsum(k), np.cumsum(n)
    ok = (cn >= min_side * N) & (cn <= (1 - min_side) * N)
    ok[-1] = False
    if not ok.any():
        return {"p": 0.0, "at": None}
    k1, n1 = ck[ok], cn[ok]
    l1 = (log_beta(a0 + k1, b0 + n1 - k1) - log_beta(a0, b0)
          + log_beta(a0 + K - k1, b0 + (N - n1) - (K - k1)) - log_beta(a0, b0))
    lw = l1 - np.log(ok.sum())
    lm1 = special.logsumexp(lw)
    post = np.log(prior_change) + lm1 - np.logaddexp(np.log(prior_change) + lm1, np.log(1 - prior_change) + l0)
    idx = np.flatnonzero(ok)[int(np.argmax(lw))]
    return {"p": float(np.exp(post)), "at": int(idx)}


def changepoint_mean(x, w, prior_change=PRIOR_CHANGE, min_side=MIN_SIDE):
    """Single change in the mean of game averages x (weights w = pitches that game); BIC approximation to the
    Bayes factor against no change."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    T = len(x)
    if T < 8:
        return {"p": 0.0, "at": None}
    mean0 = np.average(x, weights=w)
    rss0 = np.sum(w * (x - mean0) ** 2)
    cw = np.cumsum(w)
    best, at = None, None
    for t in range(2, T - 2):
        if cw[t - 1] < min_side * cw[-1] or cw[t - 1] > (1 - min_side) * cw[-1]:
            continue
        m1 = np.average(x[:t], weights=w[:t])
        m2 = np.average(x[t:], weights=w[t:])
        rss = np.sum(w[:t] * (x[:t] - m1) ** 2) + np.sum(w[t:] * (x[t:] - m2) ** 2)
        if best is None or rss < best:
            best, at = rss, t
    if best is None or rss0 <= 0:
        return {"p": 0.0, "at": None}
    bic0 = T * np.log(rss0 / T)
    bic1 = T * np.log(max(best, 1e-12) / T) + 2 * np.log(T)
    lp = np.log(prior_change) + (bic0 - bic1) / 2
    post = np.exp(lp - np.logaddexp(lp, np.log(1 - prior_change)))
    return {"p": float(post), "at": int(at - 1)}


def p_better(k1, n1, k2, n2, polarity=1, draws=40000):
    """Probability the 'after' rate is better than the 'before' rate (Jeffreys priors). polarity +1: higher is better."""
    if n1 <= 0 or n2 <= 0:
        return None
    x = RNG.beta(k1 + 0.5, n1 - k1 + 0.5, draws)
    y = RNG.beta(k2 + 0.5, n2 - k2 + 0.5, draws)
    return float(np.mean((y - x) * polarity > 0))


def grade(p):
    if p is None:
        return "wait"
    return "good" if p >= 0.9 else ("bad" if p <= 0.1 else "wait")


def more_needed(k1, n1, k2, n2):
    """Chances still needed after the change, at the current gap, before a 90% interval clears zero."""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    gap = abs(p2 - p1)
    if gap < 0.01:
        return None
    pbar = (k1 + k2) / (n1 + n2)
    var1 = pbar * (1 - pbar) / n1
    need_var2 = (gap / Z90) ** 2 - var1
    if need_var2 <= 0:
        return None
    return max(int(np.ceil(pbar * (1 - pbar) / need_var2 - n2)), 0)


# ---------------------------------------------------------------- 1. how long until you know
def weeks_to_know(con, level):
    keys = ["chase", "whiff", "zcontact", "hardhit", "k"]
    cols = []
    for key in keys:
        m = BY_KEY[key]
        cols.append(f"count(*) filter (where {m['den']}) as \"n_{key}\"")
        cols.append(f"count(*) filter (where ({m['den']}) and ({m['num']})) as \"k_{key}\"")
    h = con.execute(f"""
        select batter, min(game_date) first_day, max(game_date) last_day, {", ".join(cols)}
        from pitches where level = '{level}' and season = {SEASON} and game_type = 'R' group by batter""").df()
    regulars = h[h["n_k"] >= 300].copy()
    weeks = ((pd.to_datetime(regulars["last_day"]) - pd.to_datetime(regulars["first_day"])).dt.days + 1) / 7
    out = {"hitters": {}, "pitchers": {}}
    for key in keys:
        p = h[f"k_{key}"].sum() / h[f"n_{key}"].sum()
        weekly = float(np.median(regulars[f"n_{key}"] / weeks))
        rows = []
        for gap in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10):
            n_after = Z90 ** 2 * p * (1 - p) / gap ** 2
            rows.append({"gap": gap, "chances": round(float(n_after)), "weeks": round(float(n_after / weekly), 1)})
        out["hitters"][key] = {"p": float(p), "weekly": round(weekly, 1), "by_gap": rows,
                               "regulars": int(len(regulars))}
    # pitchers: game-to-game noise of a pitch trait, from every pitcher at the level with 10+ outings of that pitch
    offs = park_offsets(con, level)
    for col, expr, label in (("velo", "velo", "Fastball velocity"), ("ivb", "pfx_z * 12", "Fastball carry (IVB)"),
                             ("arm_angle", "arm_angle", "Arm angle")):
        g = con.execute(f"""
            select p.pitcher, p.pitch_type, p.game_pk, g.venue, avg({expr}) x, count(*) n
            from pitches p join games g using (game_pk)
            where p.level = '{level}' and p.season = {SEASON} and p.game_type = 'R' and p.is_pitch
              and p.pitch_type in ('FF', 'SI') and {expr} is not null
            group by all having count(*) >= 8""").df()
        g["x"] = g["x"] - g["venue"].map(offs[col]).fillna(0.0)
        sd = g.groupby(["pitcher", "pitch_type"])["x"].agg(["std", "size"])
        sigma = float(sd[sd["size"] >= 10]["std"].median())
        starts = con.execute(f"""
            select pitcher, count(distinct game_pk) g, min(game_date) a, max(game_date) b
            from pitches where level = '{level}' and season = {SEASON} and game_type = 'R' and inning = 1
            group by pitcher having count(distinct game_pk) >= 10""").df()
        per_week = float(np.median(starts["g"] / (((pd.to_datetime(starts["b"]) - pd.to_datetime(starts["a"])).dt.days
                                                   + 1) / 7)))
        unit, _ = PITCH_SHAPE[col]
        rows = []
        for gap in ((0.5, 1.0, 1.5, 2.0) if col == "velo" else (1.0, 2.0, 3.0, 4.0)):
            n_games = Z90 ** 2 * sigma ** 2 / gap ** 2
            rows.append({"gap": gap, "outings": round(float(n_games), 1), "weeks": round(float(n_games / per_week), 1)})
        out["pitchers"][col] = {"label": label, "unit": unit, "sigma": round(sigma, 2),
                                "starts_per_week": round(per_week, 2), "by_gap": rows}
    return out


# ---------------------------------------------------------------- 2. pitchers
def park_offsets(con, level):
    """How much each park's cameras read high or low for the same pitcher's same pitch, league-wide."""
    out = {}
    for col, expr in SHAPE_SQL.items():
        rows = con.execute(f"""
            with pt as (
                select p.pitcher, p.pitch_type, g.venue, avg({expr}) m, count(*) n
                from pitches p join games g using (game_pk)
                where p.level = '{level}' and p.season = {SEASON} and p.game_type = 'R' and p.is_pitch
                  and p.pitch_type is not null and {expr} is not null
                group by all),
            base as (select pitcher, pitch_type, sum(m * n) / sum(n) mm, count(distinct venue) parks
                     from pt group by all)
            select venue, sum((m - mm) * n) / sum(n) off, sum(n) n from pt join base using (pitcher, pitch_type)
            where parks >= 3 group by venue""").fetchall()
        out[col] = {v: (o if n >= 2000 else 0.0) for v, o, n in rows}
    return out


def pitcher_games(con, level, teams):
    team_list = ", ".join(str(t) for t in teams)
    g = con.execute(f"""
        select p.pitcher as player, p.game_date, p.game_pk, g.venue, p.pitch_type, p.p_throws, count(*) pitches,
               avg(velo) velo, avg(pfx_z) * 12 ivb, avg(pfx_x * case when p_throws = 'R' then -12 else 12 end) hb,
               avg(spin) spin, avg(arm_angle) arm_angle, avg(ext) ext,
               count(*) filter (where is_swing) swings, count(*) filter (where is_whiff) whiffs,
               count(*) filter (where description = 'called_strike' or is_whiff) csw
        from pitches p join games g using (game_pk)
        where p.level = '{level}' and p.season = {SEASON} and p.game_type = 'R' and p.fld_team in ({team_list})
          and is_pitch and pitch_type is not null and pitch_type not in ('PO', 'IN', 'AB', 'UN')
        group by all order by player, game_date, game_pk""").df()
    offs = park_offsets(con, level)
    for col in SHAPE_SQL:
        g[col] = g[col] - g["venue"].map(offs[col]).fillna(0.0)
    tot = g.groupby(["player", "game_pk"]).agg(game_total=("pitches", "sum"), g_sw=("swings", "sum"),
                                                g_wh=("whiffs", "sum"), g_csw=("csw", "sum")).reset_index()
    return g.merge(tot, on=["player", "game_pk"])


FASTBALLS = ("FF", "SI")


def _test(d, col, min_gap, key):
    """One change test on game averages of column col; returns (candidate or None, shuffled alarm)."""
    ok = np.isfinite(d[col].to_numpy(float))
    if ok.sum() < 8:
        return None, None
    dd = d[ok]
    x, w = dd[col].to_numpy(float), dd["w"].to_numpy(float)
    cp = changepoint_mean(x, w)
    perm = RNG.permutation(len(x))
    shuffled = changepoint_mean(x[perm], w[perm])["p"] >= REPORT_P
    if cp["at"] is None or cp["p"] < REPORT_P:
        return None, shuffled
    t = cp["at"]
    before = np.average(x[: t + 1], weights=w[: t + 1])
    after = np.average(x[t + 1:], weights=w[t + 1:])
    if abs(after - before) < min_gap:
        return None, shuffled
    return {**key, "date": pd.Timestamp(dd["game_date"].iloc[t + 1]), "p_change": cp["p"],
            "before": float(before), "after": float(after),
            "games": [{"d": str(pd.Timestamp(a).date()), "x": round(float(b), 3), "n": int(c)}
                      for a, b, c in zip(dd["game_date"], x, w)]}, shuffled


def pitcher_candidates(g):
    """Changes that survive pitch-label noise: fastball traits, whole-delivery traits, usage, and breaking-ball
    shape only when that pitch's usage held steady across the change (otherwise it is likely a label shift)."""
    found, tested, shuffled = [], 0, 0
    games = g.groupby(["player", "game_pk"]).agg(game_date=("game_date", "first"), tot=("game_total", "first"))
    # whole delivery: arm angle and extension pooled over every pitch that game
    pooled = g.assign(aw=g["arm_angle"] * g["pitches"], ew=g["ext"] * g["pitches"])
    pooled = pooled.groupby(["player", "game_pk"]).agg(game_date=("game_date", "first"), aw=("aw", "sum"),
                                                        ew=("ew", "sum"), w=("pitches", "sum")).reset_index()
    pooled["arm_angle"], pooled["ext"] = pooled["aw"] / pooled["w"], pooled["ew"] / pooled["w"]
    for pid, d in pooled.groupby("player"):
        if d["w"].sum() < 300 or len(d) < 8:
            continue
        for col in ("arm_angle", "ext"):
            tested += 1
            c, sh = _test(d.sort_values("game_date"), col, PITCH_SHAPE[col][1],
                          {"player": int(pid), "pitch_type": "ALL", "metric": col, "unit": PITCH_SHAPE[col][0]})
            shuffled += bool(sh)
            if c:
                found.append(c)
    for (pid, pt), d in g.groupby(["player", "pitch_type"]):
        d = d.sort_values("game_date").assign(w=d["pitches"])
        if d["pitches"].sum() < 120 or len(d) < 8:
            continue
        cols = ("velo", "ivb", "hb", "spin") if pt in FASTBALLS else ("velo", "ivb", "hb", "spin")
        for col in cols:
            tested += 1
            c, sh = _test(d, col, PITCH_SHAPE[col][1], {"player": int(pid), "pitch_type": pt, "metric": col,
                                                       "unit": PITCH_SHAPE[col][0]})
            shuffled += bool(sh)
            if not c:
                continue
            if pt not in FASTBALLS:
                tot = games.loc[pid]
                share = (d.set_index("game_pk")["pitches"] / tot["tot"]).reindex(tot.index).fillna(0.0)
                when = tot["game_date"] < c["date"]
                if abs(share[when].mean() - share[~when].mean()) >= 0.08:
                    continue                 # the label's usage moved with the "shape": treat as a label shift
            found.append(c)
    # usage: share of the game's pitches, for every pitch he threw 40+ times
    for pid, tot in games.groupby(level=0):
        tot = tot.droplevel(0).sort_values("game_date")
        if len(tot) < 10:
            continue
        mine = g[g["player"] == pid]
        for pt, dp in mine.groupby("pitch_type"):
            if dp["pitches"].sum() < 40:
                continue
            share = (dp.set_index("game_pk")["pitches"] / tot["tot"]).reindex(tot.index).fillna(0.0)
            d = pd.DataFrame({"game_date": tot["game_date"], "use": share.to_numpy(), "w": tot["tot"].to_numpy()})
            tested += 1
            c, sh = _test(d, "use", 0.10, {"player": int(pid), "pitch_type": pt, "metric": "use", "unit": "share"})
            shuffled += bool(sh)
            if c:
                found.append(c)
    return found, tested, shuffled


def mark_relabels(cands, g):
    """A pitch that appears as another disappears, with the same speed and movement, is one pitch renamed."""
    shape = g.groupby(["player", "pitch_type"]).apply(
        lambda d: pd.Series({"velo": np.average(d["velo"].fillna(d["velo"].mean()), weights=d["pitches"]),
                             "ivb": np.average(d["ivb"].fillna(d["ivb"].mean()), weights=d["pitches"]),
                             "hb": np.average(d["hb"].fillna(d["hb"].mean()), weights=d["pitches"])}),
        include_groups=False)
    use = [c for c in cands if c["metric"] == "use"]
    for a in use:
        for b in use:
            if a is b or a["player"] != b["player"] or abs((a["date"] - b["date"]).days) > 3:
                continue
            if a["before"] < 0.03 <= a["after"] and b["after"] < 0.03 <= b["before"]:
                sa, sb = shape.loc[(a["player"], a["pitch_type"])], shape.loc[(b["player"], b["pitch_type"])]
                if abs(sa["velo"] - sb["velo"]) < 2.5 and abs(sa["ivb"] - sb["ivb"]) < 4 and abs(sa["hb"] - sb["hb"]) < 5:
                    a["relabel_of"], b["relabel_to"] = b["pitch_type"], a["pitch_type"]
    return cands


def track_pitchers(con, level, teams, names):
    g = pitcher_games(con, level, teams)
    cands, tested, shuffled = pitcher_candidates(g)
    cands = mark_relabels(cands, g)
    out = []
    for c in cands:
        if c.get("relabel_of") or c.get("relabel_to"):
            out.append({"player": c["player"], "name": names.get(c["player"]), "level": level, "kind": "relabel",
                        "pitch_type": c["pitch_type"], "date": str(c["date"].date()),
                        "of": c.get("relabel_of"), "to": c.get("relabel_to")})
            continue
        mine = g[g["player"] == c["player"]]
        if c["pitch_type"] == "ALL" or c["metric"] == "use":
            d = mine.drop_duplicates("game_pk")
            sw, wh, csw, tot = "g_sw", "g_wh", "g_csw", "game_total"
            scope = "all"
        else:
            d = mine[mine["pitch_type"] == c["pitch_type"]]
            sw, wh, csw, tot = "swings", "whiffs", "csw", "pitches"
            scope = c["pitch_type"]
        b, a = d[d["game_date"] < c["date"]], d[d["game_date"] >= c["date"]]
        k1, n1, k2, n2 = b[wh].sum(), b[sw].sum(), a[wh].sum(), a[sw].sum()
        c1, t1, c2, t2 = b[csw].sum(), b[tot].sum(), a[csw].sum(), a[tot].sum()
        kind = c["metric"]
        if kind == "use":
            kind = "new" if c["before"] < 0.03 else ("dropped" if c["after"] < 0.03 else "use")
        pw = p_better(k1, n1, k2, n2)
        pc = p_better(c1, t1, c2, t2)
        out.append({"player": c["player"], "name": names.get(c["player"]), "level": level, "kind": kind,
                    "metric": c["metric"], "unit": c["unit"], "pitch_type": c["pitch_type"], "scope": scope,
                    "date": str(c["date"].date()), "p_change": round(c["p_change"], 3),
                    "before": round(c["before"], 3), "after": round(c["after"], 3),
                    "whiff_before": [int(k1), int(n1)], "whiff_after": [int(k2), int(n2)],
                    "csw_before": [int(c1), int(t1)], "csw_after": [int(c2), int(t2)],
                    "p_whiff_better": pw, "p_csw_better": pc, "grade": grade(pc if scope == "all" else pw),
                    "more_swings": more_needed(k1, n1, k2, n2), "games": c["games"]})
    throws = g.groupby("player")["p_throws"].first().to_dict()
    for x in out:
        x["throws"] = throws.get(x["player"])
    out.sort(key=lambda x: (x["player"], x["date"]))
    return out, {"tested": tested, "shuffled_alarms": int(shuffled),
                 "alarms": int(sum(1 for x in out if x["kind"] != "relabel")),
                 "relabels": int(sum(1 for x in out if x["kind"] == "relabel"))}


# ---------------------------------------------------------------- 3. hitters
def track_hitters(con, level, teams, names, mus):
    team_list = ", ".join(str(t) for t in teams)
    cols = []
    for key in HITTER_TRACK + ["k"]:
        m = BY_KEY[key]
        cols.append(f"count(*) filter (where {m['den']}) as \"n_{key}\"")
        cols.append(f"count(*) filter (where ({m['den']}) and ({m['num']})) as \"k_{key}\"")
    g = con.execute(f"""
        select batter as player, game_date, game_pk, {", ".join(cols)}
        from pitches where level = '{level}' and season = {SEASON} and game_type = 'R' and bat_team in ({team_list})
        group by all order by player, game_date""").df()
    out, tested, shuffled_hits, real_hits = [], 0, 0, 0
    for pid, d in g.groupby("player"):
        if d["n_k"].sum() < 150:
            continue
        cut = int(np.searchsorted(d["n_k"].cumsum().to_numpy(), d["n_k"].sum() / 2))
        row = {"player": int(pid), "name": names.get(int(pid)), "level": level, "pa": int(d["n_k"].sum()),
               "split_date": str(pd.Timestamp(d["game_date"].iloc[min(cut + 1, len(d) - 1)]).date()), "m": {}}
        for key in HITTER_TRACK:
            k, n = d[f"k_{key}"].to_numpy(float), d[f"n_{key}"].to_numpy(float)
            k1, n1, k2, n2 = k[: cut + 1].sum(), n[: cut + 1].sum(), k[cut + 1:].sum(), n[cut + 1:].sum()
            pb = p_better(k1, n1, k2, n2, HITTER_POLARITY[key])
            tested += 1
            cp = changepoint_binom(k, n, mus[key], M=30)
            perm = RNG.permutation(len(k))
            shuffled_hits += changepoint_binom(k[perm], n[perm], mus[key], M=30)["p"] >= REPORT_P
            real_hits += cp["p"] >= REPORT_P
            row["m"][key] = {"first": [int(k1), int(n1)], "second": [int(k2), int(n2)], "p_better": pb,
                             "grade": grade(pb), "more": more_needed(k1, n1, k2, n2), "p_change": round(cp["p"], 3)}
        out.append(row)
    out.sort(key=lambda r: -r["pa"])
    return out, {"tested": tested, "alarms": int(real_hits), "shuffled_alarms": int(shuffled_hits)}


def league_mu(con, level, keys):
    cols = []
    for key in keys:
        m = BY_KEY[key]
        cols.append(f"count(*) filter (where ({m['den']}) and ({m['num']}))::double / "
                    f"nullif(count(*) filter (where {m['den']}), 0) as \"{key}\"")
    return con.execute(f"select {', '.join(cols)} from pitches where level = '{level}' and season = {SEASON} "
                       "and game_type = 'R'").df().iloc[0].to_dict()


def run():
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    names = dict(con.execute("select id, full_name from players").fetchall())
    out = {"season": SEASON, "weeks": weeks_to_know(con, "AAA"), "pitchers": [], "hitters": [], "checks": {}}
    for level, teams in AFFILIATES.items():
        mus = league_mu(con, level, HITTER_TRACK)
        p, pc = track_pitchers(con, level, teams, names)
        h, hc = track_hitters(con, level, teams, names, mus)
        out["pitchers"] += p
        out["hitters"] += h
        out["checks"][level] = {"pitchers": pc, "hitters": hc}
    con.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "develop.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["checks"], indent=1))
    for key, v in r["weeks"]["hitters"].items():
        print(" ", key, "weekly", v["weekly"], [(x["gap"], x["weeks"]) for x in v["by_gap"]])
    for key, v in r["weeks"]["pitchers"].items():
        print(" ", key, "sigma", v["sigma"], "starts/wk", v["starts_per_week"], [(x["gap"], x["outings"]) for x in v["by_gap"]])
    for x in r["pitchers"]:
        if x["kind"] == "relabel":
            print("REL", x["level"], x["name"], x["pitch_type"], x["date"], x.get("of"), x.get("to"))
        else:
            print(x["kind"].upper()[:5], x["level"], x["name"], x["pitch_type"], x["metric"], x["date"], x["before"], "->",
                  x["after"], "p", x["p_change"], "csw", x["csw_before"], x["csw_after"], "whiff", x["whiff_before"],
                  x["whiff_after"], x["grade"])
    for h in r["hitters"][:40]:
        print("HIT", h["level"], h["name"], h["pa"], {k: (v["grade"], round(v["p_better"] or 0, 2)) for k, v in h["m"].items()})
