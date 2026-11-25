"""Build the Monday packet for every 2026 series of the Jacksonville Jumbo Shrimp (AAA) and Jupiter Hammerheads (FSL),
then check each packet against the series that followed.

    python pipeline/packet.py        -> site/data/packets/{JAX,JUP}/index.json and one file per series

Everything on a packet uses data from before the series' first game, and the opponent's active roster on the Monday
(MLB Stats API), the same way a Fellow would build it. Forecasts come from forecast.predict with the parameters tuned
on 2025 (backtest.py), so the packet prints exactly what was tested.
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import CACHE, MIN_GAMES, load  # noqa: E402
from fetch import roster  # noqa: E402
from forecast import features, predict  # noqa: E402
from metrics import BY_KEY  # noqa: E402
from text import three_things, discussion  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
SITE = ROOT / "site" / "data" / "packets"
SEASON = 2026
TEAMS = {"JAX": {"id": 564, "level": "AAA", "name": "Jacksonville Jumbo Shrimp"},
         "JUP": {"id": 479, "level": "FSL", "name": "Jupiter Hammerheads"}}
CARD = ["chase", "zswing", "fps", "chase2k", "swing", "whiff", "zcontact", "ocontact", "whiff_fb", "whiff_br", "whiff_os",
        "k", "bb", "avg", "obp", "babip", "gb", "pull", "oppo", "pullair", "hardhit", "barrel",
        "k_vl", "k_vr", "avg_vl", "avg_vr", "whiff_up", "whiff_down", "whiff_in", "whiff_away"]
# from the hitter's side: +1 good for him, -1 good for the pitcher, 0 a style, not a quality
POLARITY = {"chase": -1, "chase2k": -1, "whiff": -1, "whiff_fb": -1, "whiff_br": -1, "whiff_os": -1, "k": -1,
            "k_vl": -1, "k_vr": -1, "whiff_up": -1, "whiff_down": -1, "whiff_in": -1, "whiff_away": -1,
            "zcontact": 1, "ocontact": 1, "bb": 1, "avg": 1, "obp": 1, "babip": 1, "hardhit": 1, "barrel": 1,
            "avg_vl": 1, "avg_vr": 1}
PITCH_NAMES = {"FF": ("Four-seam", "Recta de cuatro costuras"), "SI": ("Sinker", "Sinker"),
               "FC": ("Cutter", "Recta cortada"), "SL": ("Slider", "Slider"), "ST": ("Sweeper", "Sweeper"),
               "CU": ("Curveball", "Curva"), "KC": ("Knuckle curve", "Curva de nudillos"),
               "SV": ("Slurve", "Slurve"), "CS": ("Slow curve", "Curva lenta"), "CH": ("Changeup", "Cambio"),
               "FS": ("Splitter", "Splitter"), "FO": ("Forkball", "Tenedor"), "SC": ("Screwball", "Screwball"),
               "KN": ("Knuckleball", "Nudillera"), "EP": ("Eephus", "Eephus"), "FA": ("Fastball", "Recta")}


def r(x, d=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), d)


def age_on(birth, day):
    if not birth:
        return None
    b = pd.Timestamp(birth)
    d = pd.Timestamp(day)
    return int(d.year - b.year - ((d.month, d.day) < (b.month, b.day)))


def forecast_spread(level):
    """Every 2026 Monday forecast for hitters with 100+ plate appearances at the level: what 'typical' looks like."""
    pred = pd.read_parquet(CACHE / f"pred_{level}_{SEASON}.parquet")
    pa = pred[pred["metric"] == "k"][["series_id", "player", "n_s"]].rename(columns={"n_s": "pa"})
    pred = pred.merge(pa, on=["series_id", "player"])
    pred = pred[pred["pa"] >= 100].drop_duplicates(["player", "date", "metric"])
    return {k: np.sort(g["sdf"].dropna().to_numpy()) for k, g in pred.groupby("metric")}


def percentile(v, spread):
    """Share of regulars' forecasts below this one."""
    if v is None or spread is None or len(spread) == 0 or not np.isfinite(v):
        return None
    return float(np.searchsorted(spread, v) / len(spread))


def spray_counts(con, level, player, before):
    rows = con.execute(f"""
        select case when sp > 30 then 0 when sp > 10 then 1 when sp >= -10 then 2 when sp >= -30 then 3 else 4 end
               as sector, bb_type = 'ground_ball' as gb, count(*) n, avg(ev) ev
        from (select spray * case when stand = 'R' then -1 else 1 end as sp, bb_type, ev from pitches
              where level = '{level}' and season = {SEASON} and game_type = 'R' and batter = {player}
                and game_date < '{before}' and is_bip and not is_bunt and spray is not null
                and spray between -50 and 50)
        group by 1, 2""").fetchall()
    out = [{"gb": 0, "air": 0, "ev_air": None} for _ in range(5)]
    for sector, gb, n, ev in rows:
        if gb:
            out[sector]["gb"] = int(n)
        else:
            out[sector]["air"] = int(n)
            out[sector]["ev_air"] = r(ev, 1)
    return out  # sectors 0..4 = pull line, pull gap, middle, opposite gap, opposite line


def pitcher_card(con, level, pid, before, info):
    arsenal = con.execute(f"""
        select pitch_type, count(*) n,
               count(*) filter (where stand = 'L') nl, count(*) filter (where stand = 'R') nr,
               avg(velo) velo, avg(pfx_z) * 12 ivb, avg(pfx_x * case when p_throws = 'R' then -12 else 12 end) hb,
               avg(spin) spin, avg(ext) ext, avg(arm_angle) arm, avg(rel_z) rel_z,
               count(*) filter (where is_swing) sw, count(*) filter (where is_whiff) wh,
               count(*) filter (where in_zone) z, count(*) filter (where balls = 0 and strikes = 0) fp,
               count(*) filter (where strikes = 2) two, count(*) filter (where balls > strikes) behind
        from pitches where level = '{level}' and season = {SEASON} and game_type = 'R' and pitcher = {pid}
          and game_date < '{before}' and is_pitch and pitch_type is not null
          and pitch_type not in ('PO', 'IN', 'AB', 'UN')
        group by 1 order by 2 desc""").df()
    if arsenal.empty:
        return None
    tot = {c: max(int(arsenal[c].sum()), 1) for c in ("n", "nl", "nr", "fp", "two", "behind")}
    pitches = []
    for _, a in arsenal.iterrows():
        if a["n"] / tot["n"] < 0.02:
            continue
        en, es = PITCH_NAMES.get(a["pitch_type"], (a["pitch_type"], a["pitch_type"]))
        pitches.append({"pt": a["pitch_type"], "en": en, "es": es, "n": int(a["n"]),
                        "use": r(a["n"] / tot["n"]), "use_l": r(a["nl"] / tot["nl"]), "use_r": r(a["nr"] / tot["nr"]),
                        "use_fp": r(a["fp"] / tot["fp"]), "use_2k": r(a["two"] / tot["two"]),
                        "use_behind": r(a["behind"] / tot["behind"]),
                        "velo": r(a["velo"], 1), "ivb": r(a["ivb"], 1), "hb": r(a["hb"], 1), "spin": r(a["spin"], 0),
                        "whiff": r(a["wh"] / a["sw"]) if a["sw"] else None, "swings": int(a["sw"]),
                        "zone": r(a["z"] / a["n"])})
    games = con.execute(f"""
        select game_date, game_pk, min(inning) first_inning, count(*) filter (where is_pitch) pitches,
               count(distinct ab) bf
        from pitches where level = '{level}' and season = {SEASON} and game_type = 'R' and pitcher = {pid}
          and game_date < '{before}'
        group by 1, 2 order by 1""").df()
    starts = games[games["first_inning"] == 1]
    last7 = games[pd.to_datetime(games["game_date"]) >= pd.Timestamp(before) - pd.to_timedelta(7, unit="D")]
    a0 = arsenal.iloc[0]
    return {"id": pid, "name": info["name"], "num": info.get("num"), "throws": info.get("throws"),
            "age": info.get("age"), "games": int(len(games)), "starts": int(len(starts)),
            "role": "SP" if len(starts) >= max(3, 0.5 * len(games)) else "RP",
            "pitches_total": int(games["pitches"].sum()),
            "last_start": str(pd.Timestamp(starts["game_date"].iloc[-1]).date()) if len(starts) else None,
            "rest": (int(np.clip(np.median(np.diff(pd.to_datetime(starts["game_date"]).to_numpy()).astype(
                "timedelta64[D]").astype(int)), 5, 8)) if len(starts) >= 3 else 6),
            "arm": r(np.average(arsenal["arm"].fillna(a0["arm"]), weights=arsenal["n"]), 0) if arsenal["arm"].notna().any() else None,
            "ext": r(np.average(arsenal["ext"].fillna(a0["ext"]), weights=arsenal["n"]), 1) if arsenal["ext"].notna().any() else None,
            "arsenal": pitches,
            "recent": [{"d": str(pd.Timestamp(x.game_date).date()), "p": int(x.pitches)} for x in last7.itertuples()]}


def recent_starters(con, level, team, before, n=8):
    """The team's starting pitchers in its last n games before a date, oldest first."""
    return con.execute(f"""
        with g as (
            select game_pk, min(game_date) d from pitches
            where level = '{level}' and season = {SEASON} and game_type = 'R' and fld_team = {team}
              and game_date < '{before}' group by game_pk order by d desc, game_pk desc limit {n}),
        first_pa as (
            select p.game_pk, p.pitcher, row_number() over (partition by p.game_pk order by p.ab, p.pn) r
            from pitches p join g using (game_pk) where p.fld_team = {team})
        select g.d, f.pitcher from g join first_pa f using (game_pk) where f.r = 1 order by g.d, g.game_pk""").fetchall()


def build_team(code, cfg, params, data, con):
    level = cfg["level"]
    sinfo = data["series_info"]
    sinfo = sinfo[(sinfo["season"] == SEASON) & (sinfo["n_games"] >= MIN_GAMES) &
                  ((sinfo["home_id"] == cfg["id"]) | (sinfo["away_id"] == cfg["id"]))].sort_values("start_date")
    players = con.execute("select * from players").df().set_index("id")
    spread = forecast_spread(level)
    d = data["daily"]
    cur, prev = d[d["season"] == SEASON], d[d["season"] == SEASON - 1]
    rosters, targets = {}, []
    for s in sinfo.itertuples():
        opp = s.away_id if s.home_id == cfg["id"] else s.home_id
        monday = (pd.Timestamp(s.start_date) - pd.Timedelta(days=1)).date().isoformat()
        ros = roster(int(opp), monday).get("roster", [])
        rosters[s.series_id] = (opp, monday, ros)
        for x in ros:
            if x["position"]["type"] != "Pitcher":
                targets.append({"player": x["person"]["id"], "date": pd.Timestamp(s.start_date)})
    targets = pd.DataFrame(targets).drop_duplicates()
    feat = features(cur, prev if len(prev) else None, targets)
    pred = predict(feat, params)
    pred["metric"] = pred["metric"].astype(str)
    pred = pred.set_index(["player", "date", "metric"]).sort_index()
    ins = data["series"]
    ins = ins[ins["season"] == SEASON]
    ins = ins.assign(metric=ins["metric"].astype(str)).set_index(["series_id", "player", "metric"])[["k", "n"]]
    index = []
    SITE.joinpath(code).mkdir(parents=True, exist_ok=True)
    for s in sinfo.itertuples():
        opp, monday, ros = rosters[s.series_id]
        home = s.home_id == cfg["id"]
        opp_name = s.away_name if home else s.home_name
        start = pd.Timestamp(s.start_date)
        games = con.execute(f"""select g.game_date, g.home_score, g.away_score, g.home_id, gs.game_in_series
            from games g join game_series gs using (game_pk) where gs.series_id = {s.series_id}
            order by gs.game_in_series""").fetchall()
        wins = sum(1 for g in games if g[1] is not None and ((g[1] > g[2]) == (g[3] == cfg["id"])))
        hitters, pitchers = [], []
        for x in ros:
            p = x["person"]
            pid = p["id"]
            info = {"name": p["fullName"], "num": x.get("jerseyNumber"), "throws": (p.get("pitchHand") or {}).get("code"),
                    "bats": (p.get("batSide") or {}).get("code"), "age": age_on(p.get("birthDate"), monday),
                    "pos": x["position"]["abbreviation"]}
            if x["position"]["type"] == "Pitcher":
                card = pitcher_card(con, level, pid, start.date().isoformat(), info)
                if card is None:
                    pitchers.append({"id": pid, "name": info["name"], "num": info["num"], "throws": info["throws"],
                                     "age": info["age"], "games": 0, "no_data": True})
                    continue
                played = con.execute(f"""select count(*) filter (where is_pitch), count(distinct game_pk)
                    from pitches p join game_series gs using (game_pk)
                    where gs.series_id = {s.series_id} and pitcher = {pid}""").fetchone()
                card["verify"] = {"pitches": int(played[0]), "games": int(played[1])}
                pitchers.append(card)
                continue
            metrics = {}
            n_pa = 0
            for key in CARD:
                try:
                    row = pred.loc[(pid, start, key)]
                except KeyError:
                    continue
                v = row["sdf"]
                metrics[key] = {"v": r(v), "lo": r(row["lo80"]), "hi": r(row["hi80"]), "t": r(row["trust"], 2),
                                "mu": r(row["mu"]), "raw": r(row["season_raw"]), "n": int(row["n_s"]),
                                "n14": int(row["n_14"]), "raw14": r(row["last14_raw"]),
                                "pct": r(percentile(v, spread.get(key)), 2)}
                try:
                    k_in, n_in = ins.loc[(s.series_id, pid, key)]
                    metrics[key]["k_in"], metrics[key]["n_in"] = int(k_in), int(n_in)
                    if n_in > 0:
                        a, b = row["alpha"], row["beta"]
                        lo_p = stats.betabinom.ppf(0.1, n_in, a, b)
                        hi_p = stats.betabinom.ppf(0.9, n_in, a, b)
                        metrics[key]["in80"] = bool(lo_p <= k_in <= hi_p)
                        metrics[key]["plo"], metrics[key]["phi"] = r(lo_p / n_in), r(hi_p / n_in)
                except KeyError:
                    pass
            if "k" in metrics:
                n_pa = metrics["k"]["n"]
            pl = players.loc[pid] if pid in players.index else None
            hitters.append({"id": pid, "name": info["name"], "num": info["num"], "pos": info["pos"],
                            "bats": info["bats"], "age": info["age"], "pa": n_pa,
                            "mlb": bool(pl is not None and isinstance(pl["mlb_debut"], str)),
                            "m": metrics,
                            "spray": spray_counts(con, level, pid, start.date().isoformat()) if n_pa else None,
                            "played": bool((s.series_id, pid, "k") in ins.index),
                            "three": three_things(metrics, POLARITY)})
        hitters.sort(key=lambda h: -h["pa"])
        pitchers.sort(key=lambda p: (p.get("role") != "SP", -(p.get("pitches_total") or 0)))
        starters = con.execute(f"""select gs.game_in_series, p.pitcher from pitches p join game_series gs using (game_pk)
            where gs.series_id = {s.series_id} and p.fld_team = {opp} and p.inning = 1 and p.ab = (
                select min(ab) from pitches q where q.game_pk = p.game_pk and q.fld_team = {opp})
            group by 1, 2 order by 1""").fetchall()
        packet = {"team": code, "team_name": cfg["name"], "level": level, "series_id": int(s.series_id),
                  "monday": monday, "start": start.date().isoformat(),
                  "end": pd.Timestamp(s.end_date).date().isoformat(), "n_games": int(s.n_games), "home": bool(home),
                  "opp_id": int(opp), "opp": opp_name, "wins": int(wins), "losses": int(len(games) - wins),
                  "hitters": hitters, "pitchers": pitchers,
                  "recent_starts": [{"d": str(pd.Timestamp(d).date()), "id": int(pid),
                                     "name": players.loc[pid]["full_name"] if pid in players.index else None,
                                     "on_roster": bool(any(x["id"] == pid for x in pitchers))}
                                    for d, pid in recent_starters(con, level, int(opp), start.date().isoformat())],
                  "actual_starters": [{"game": int(g), "id": int(pid),
                                       "name": players.loc[pid]["full_name"] if pid in players.index else None,
                                       "on_roster": bool(any(x["id"] == pid for x in pitchers))}
                                      for g, pid in starters]}
        packet["discussion"] = discussion(packet)
        (SITE / code / f"{packet['start']}.json").write_text(json.dumps(packet, separators=(",", ":")))
        index.append({k: packet[k] for k in ("start", "end", "monday", "opp", "opp_id", "home", "n_games", "wins",
                                             "losses")} | {"hitters": len(hitters), "pitchers": len(pitchers)})
    (SITE / code / "index.json").write_text(json.dumps({"team": code, "name": cfg["name"], "level": level,
                                                         "series": index}, indent=1))
    return index


def run():
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    out = {}
    for code, cfg in TEAMS.items():
        params = json.loads((OUT / f"params_{cfg['level']}.json").read_text())
        data = load(con, cfg["level"])
        out[code] = build_team(code, cfg, params, data, con)
        print(code, len(out[code]), "series")
    con.close()
    return out


if __name__ == "__main__":
    run()
