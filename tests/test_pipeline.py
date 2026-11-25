"""Metric definitions, the bilingual text, and the published files, checked on small cases and on the real outputs."""
import json
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from build import IS_BUNT  # noqa: E402
from metrics import BY_KEY, daily  # noqa: E402
from text import T, three_things  # noqa: E402


def pitch(**kw):
    base = dict(level="AAA", season=2026, game_type="R", batter=1, pitcher=9, game_date="2026-05-01", is_pitch=True,
                is_bunt=False, zone=5, in_zone=True, out_zone=False, is_swing=False, is_whiff=False, balls=1, strikes=1,
                pitch_group="FB", events=None, is_bip=False, bb_type=None, spray=None, stand="R", p_throws="R",
                ev=None, lsa=None, plate_z=2.5, sz_top=3.4, sz_bot=1.6, plate_x=0.0)
    base.update(kw)
    return base


def counts(rows):
    con = duckdb.connect()
    df = pd.DataFrame(rows)  # noqa: F841 (read by duckdb)
    con.execute("create table pitches as select * from df")
    d = daily(con, "AAA")
    return {m: (int(k), int(n)) for m, k, n in d.groupby("metric", observed=True)[["k", "n"]].sum().itertuples()}


def test_is_bunt_is_never_null():
    con = duckdb.connect()
    con.execute("create table t (description varchar, events varchar)")
    con.execute("insert into t values ('ball', null), ('foul_bunt', null), ('hit_into_play', 'sac_bunt'), ('foul', null)")
    got = [r[0] for r in con.execute(f"select {IS_BUNT} from t t").fetchall()]
    assert got == [False, True, True, False]


def test_chase_counts_skip_bunts_and_rule_calls():
    rows = [pitch(zone=12, in_zone=False, out_zone=True, is_swing=True),          # a chase
            pitch(zone=13, in_zone=False, out_zone=True),                          # a take
            pitch(zone=14, in_zone=False, out_zone=True, is_swing=True, is_bunt=True),  # bunt attempt: not a chase
            pitch(zone=None, in_zone=None, out_zone=None, is_pitch=False),         # automatic ball: not a pitch
            pitch(zone=5, is_swing=True, is_whiff=True)]                           # zone swing and miss
    c = counts(rows)
    assert c["chase"] == (1, 2)
    assert c["zswing"] == (1, 1)
    assert c["whiff"] == (1, 2)
    assert c["zcontact"] == (0, 1)


def test_plate_appearance_outcomes():
    rows = [pitch(events="strikeout", is_swing=True, is_whiff=True), pitch(events="walk"),
            pitch(events="single", is_bip=True, bb_type="ground_ball", spray=-25.0, ev=101.0, lsa=4),
            pitch(events="truncated_pa"), pitch(events="intent_walk", is_pitch=False, zone=None),
            pitch(events="sac_fly", is_bip=True, bb_type="fly_ball", spray=5.0, ev=93.0, lsa=3)]
    c = counts(rows)
    assert c["k"] == (1, 4)            # strikeout, walk, single, sac fly; truncated and intentional walks excluded
    assert c["bb"] == (1, 4)
    assert c["avg"] == (1, 2)          # at-bats: strikeout and single
    assert c["babip"] == (1, 2)        # single and the sac fly
    assert c["hardhit"] == (1, 2)


def test_pull_side_follows_the_hitter():
    rows = [pitch(events="single", is_bip=True, bb_type="line_drive", spray=-30.0, stand="R"),   # RHH to left: pull
            pitch(events="single", is_bip=True, bb_type="line_drive", spray=-30.0, stand="L", batter=2),  # LHH to left: oppo
            pitch(events="field_out", is_bip=True, bb_type="ground_ball", spray=2.0, stand="L", batter=2)]
    con = duckdb.connect()
    df = pd.DataFrame(rows)  # noqa: F841
    con.execute("create table pitches as select * from df")
    d = daily(con, "AAA")
    by = d.groupby(["player", "metric"], observed=True)[["k", "n"]].sum()
    assert tuple(by.loc[(1, "pull")]) == (1, 1)
    assert tuple(by.loc[(2, "pull")]) == (0, 2) and tuple(by.loc[(2, "oppo")]) == (1, 2)
    assert tuple(by.loc[(1, "pullair")]) == (1, 1)


def test_every_metric_has_spanish_and_english():
    for key, m in BY_KEY.items():
        assert m["en"] and m["es"], key


def test_three_things_rules():
    m = {"chase": {"v": 0.36, "mu": 0.28, "pct": 0.95, "t": 0.8}, "chase2k": {"v": 0.5, "mu": 0.38, "pct": 0.97, "t": 0.7},
         "whiff": {"v": 0.33, "mu": 0.24, "pct": 0.9, "t": 0.2},            # extreme but not trusted: left out
         "barrel": {"v": 0.12, "mu": 0.06, "pct": 0.93, "t": 0.6}, "gb": {"v": 0.55, "mu": 0.43, "pct": 0.9, "t": 0.6},
         "fps": {"v": 0.2, "mu": 0.32, "pct": 0.05, "t": 0.9}}
    out = three_things(m)
    keys = [x["key"] for x in out]
    assert len(out) == 3
    assert "whiff" not in keys
    assert not ({"chase", "chase2k"} <= set(keys))      # one line per family
    for x in out:
        assert "{" not in x["en"] and "{" not in x["es"]
        assert x["en"] != x["es"]


def test_templates_fill_cleanly():
    for (key, side), (en, es) in T.items():
        assert en.count("{v}") == es.count("{v}") == 1, key
        assert en.count("{mu}") == es.count("{mu}") == 1, key


SITE = ROOT / "site"


@pytest.mark.skipif(not (SITE / "index.html").exists(), reason="site not built")
def test_page_has_no_unfilled_numbers():
    html = (SITE / "index.html").read_text()
    assert "{{" not in html and "}}" not in html
    assert re.search(r"of \d+</small>", html)


@pytest.mark.skipif(not (SITE / "data" / "packets" / "JAX" / "index.json").exists(), reason="packets not built")
def test_packets_are_well_formed():
    for team in ("JAX", "JUP"):
        idx = json.loads((SITE / "data" / "packets" / team / "index.json").read_text())
        assert len(idx["series"]) >= 20
        for s in idx["series"]:
            p = json.loads((SITE / "data" / "packets" / team / f"{s['start']}.json").read_text())
            assert p["monday"] < p["start"] <= p["end"]
            assert p["discussion"]["en"] and len(p["discussion"]["en"]) == len(p["discussion"]["es"])
            for h in p["hitters"]:
                assert len(h["three"]) <= 3
                for key, m in h["m"].items():
                    assert m["lo"] - 1e-9 <= m["v"] <= m["hi"] + 1e-9, (team, s["start"], h["name"], key)
                    assert 0 <= m["t"] <= 1


@pytest.mark.skipif(not (ROOT / "data" / "sdf.duckdb").exists(), reason="database not built")
def test_packet_counts_stop_before_the_series():
    """On real data: a hitter's season-to-date chances on the card equal what the database holds before game one."""
    p = json.loads((SITE / "data" / "packets" / "JAX" / "2026-09-15.json").read_text())
    h = max(p["hitters"], key=lambda x: x["pa"])
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    m = BY_KEY["chase"]
    n = con.execute(f"""select count(*) filter (where {m['den']}) from pitches
        where level = 'AAA' and season = 2026 and game_type = 'R' and batter = {h['id']} and game_date < '{p['start']}'""").fetchone()[0]
    con.close()
    assert h["m"]["chase"]["n"] == n
