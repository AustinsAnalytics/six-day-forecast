"""The numbers on an advance card, each defined as a count: k successes out of n chances.

Every metric here is a rate, so its uncertainty is binomial and the same shrinkage math covers all of them.
`daily(con, level)` counts each hitter's chances and successes per game day; `in_series(con, level)` counts
them inside each series. Pitches are regular season, tracked (zone known), and never bunts. Rows come back in a fixed
order, so the seeded bootstrap and calibration draws downstream are identical from run to run.
"""
import pandas as pd

PULL = "(spray * case when stand = 'R' then -1 else 1 end) > 15"
OPPO = "(spray * case when stand = 'R' then -1 else 1 end) < -15"
INSIDE = "(plate_x * case when stand = 'R' then -1 else 1 end) > 0"
UP = "plate_z > (sz_top + sz_bot) / 2"
TRACKED = "is_pitch and not is_bunt and zone is not null"
BIP = "is_bip and not is_bunt"
PA = "events is not null and events not in ('truncated_pa', 'intent_walk', 'catcher_interf')"
K = "events in ('strikeout', 'strikeout_double_play')"
HIT = "events in ('single', 'double', 'triple', 'home_run')"
SF = "events in ('sac_fly', 'sac_fly_double_play')"
SH = "events in ('sac_bunt', 'sac_bunt_double_play')"
AB = f"{PA} and events not in ('walk', 'hit_by_pitch') and not ({SF}) and not ({SH})"


def m(key, en, es, family, base, den, num, parent=None, card=True, fmt="pct"):
    return {"key": key, "en": en, "es": es, "family": family, "base": base, "den": den, "num": num,
            "parent": parent, "card": card, "fmt": fmt}


# family: decisions, contact, results, batted, split, zone.  base: which rows the counts come from.
METRICS = [
    m("swing", "Swing rate", "Tasa de swings", "decisions", "pitch", TRACKED, "is_swing"),
    m("chase", "Chase rate", "Swings fuera de la zona", "decisions", "pitch", f"{TRACKED} and out_zone", "is_swing"),
    m("zswing", "Zone swing rate", "Swings en la zona", "decisions", "pitch", f"{TRACKED} and in_zone", "is_swing"),
    m("fps", "First-pitch swing", "Swing al primer pitcheo", "decisions", "pitch",
      f"{TRACKED} and balls = 0 and strikes = 0", "is_swing"),
    m("chase2k", "Two-strike chase", "Swings fuera con dos strikes", "decisions", "pitch",
      f"{TRACKED} and out_zone and strikes = 2", "is_swing"),
    m("whiff", "Whiff rate", "Swings en blanco", "contact", "pitch", f"{TRACKED} and is_swing", "is_whiff"),
    m("zcontact", "Zone contact", "Contacto en la zona", "contact", "pitch", f"{TRACKED} and in_zone and is_swing",
      "not is_whiff"),
    m("ocontact", "Chase contact", "Contacto fuera de la zona", "contact", "pitch",
      f"{TRACKED} and out_zone and is_swing", "not is_whiff"),
    m("whiff_fb", "Whiff vs fastballs", "En blanco vs. rectas", "contact", "pitch",
      f"{TRACKED} and is_swing and pitch_group = 'FB'", "is_whiff", parent="whiff"),
    m("whiff_br", "Whiff vs breaking", "En blanco vs. rompientes", "contact", "pitch",
      f"{TRACKED} and is_swing and pitch_group = 'BR'", "is_whiff", parent="whiff"),
    m("whiff_os", "Whiff vs offspeed", "En blanco vs. cambios", "contact", "pitch",
      f"{TRACKED} and is_swing and pitch_group = 'OS'", "is_whiff", parent="whiff"),
    m("k", "Strikeout rate", "Tasa de ponches", "results", "pa", PA, K),
    m("bb", "Walk rate", "Tasa de boletos", "results", "pa", PA, "events = 'walk'"),
    m("avg", "Batting average", "Promedio de bateo", "results", "pa", AB, HIT, fmt="avg"),
    m("obp", "On-base percentage", "Porcentaje de embasado", "results", "pa", f"{PA} and not ({SH})",
      "events in ('single', 'double', 'triple', 'home_run', 'walk', 'hit_by_pitch')", fmt="avg"),
    m("babip", "BABIP", "Promedio de bolas en juego", "results", "pa",
      f"{AB} and not ({K}) and events <> 'home_run' or ({SF})",
      "events in ('single', 'double', 'triple')", fmt="avg"),
    m("gb", "Ground-ball rate", "Tasa de rodados", "batted", "bip", BIP, "bb_type = 'ground_ball'"),
    m("pull", "Pull rate", "Bolas haladas", "batted", "bip", f"{BIP} and spray is not null", PULL),
    m("oppo", "Opposite-field rate", "Bolas a la banda contraria", "batted", "bip", f"{BIP} and spray is not null",
      OPPO),
    m("pullair", "Pulled in the air", "Haladas por el aire", "batted", "bip", f"{BIP} and spray is not null",
      f"{PULL} and bb_type in ('line_drive', 'fly_ball')"),
    m("hardhit", "Hard-hit rate", "Tasa de batazos duros", "batted", "bip", f"{BIP} and ev is not null", "ev >= 95"),
    m("barrel", "Barrel rate", "Tasa de macetazos", "batted", "bip", f"{BIP} and lsa is not null", "lsa = 6"),
    # splits a card prints next to the overall line
    m("k_vl", "Strikeout rate vs LHP", "Ponches vs. zurdos", "split", "pa", f"{PA} and p_throws = 'L'", K, parent="k"),
    m("k_vr", "Strikeout rate vs RHP", "Ponches vs. derechos", "split", "pa", f"{PA} and p_throws = 'R'", K,
      parent="k"),
    m("avg_vl", "Average vs LHP", "Promedio vs. zurdos", "split", "pa", f"{AB} and p_throws = 'L'", HIT, parent="avg",
      fmt="avg"),
    m("avg_vr", "Average vs RHP", "Promedio vs. derechos", "split", "pa", f"{AB} and p_throws = 'R'", HIT,
      parent="avg", fmt="avg"),
    # the simplified zone the packet uses: halves of the zone instead of nine boxes
    m("whiff_up", "Whiff, top half", "En blanco, mitad alta", "zone", "pitch", f"{TRACKED} and is_swing and {UP}",
      "is_whiff", parent="whiff"),
    m("whiff_down", "Whiff, bottom half", "En blanco, mitad baja", "zone", "pitch",
      f"{TRACKED} and is_swing and not ({UP})", "is_whiff", parent="whiff"),
    m("whiff_in", "Whiff, inside half", "En blanco, mitad de adentro", "zone", "pitch",
      f"{TRACKED} and is_swing and {INSIDE}", "is_whiff", parent="whiff"),
    m("whiff_away", "Whiff, outside half", "En blanco, mitad de afuera", "zone", "pitch",
      f"{TRACKED} and is_swing and not ({INSIDE})", "is_whiff", parent="whiff"),
]
# the nine-box "hot zone" chart: whiffs per swing and batting average, by Gameday zone 1-9
for z in range(1, 10):
    METRICS.append(m(f"whiff_z{z}", f"Whiff, zone {z}", f"En blanco, zona {z}", "zone", "pitch",
                     f"{TRACKED} and is_swing and zone = {z}", "is_whiff", parent="whiff", card=False))
    METRICS.append(m(f"avg_z{z}", f"Average, zone {z}", f"Promedio, zona {z}", "zone", "pa",
                     f"{AB} and zone = {z}", HIT, parent="avg", card=False, fmt="avg"))

BY_KEY = {x["key"]: x for x in METRICS}
BASE_FILTER = {
    "pitch": "is_pitch",
    "pa": PA,
    "bip": BIP,
}


def _columns():
    cols = []
    for x in METRICS:
        cols.append(f"count(*) filter (where {x['den']}) as \"n__{x['key']}\"")
        cols.append(f"count(*) filter (where ({x['den']}) and ({x['num']})) as \"k__{x['key']}\"")
    return ",\n".join(cols)


def _long(df, ids):
    parts = []
    for x in METRICS:
        part = df[ids + [f"k__{x['key']}", f"n__{x['key']}"]].copy()
        part.columns = ids + ["k", "n"]
        part["metric"] = x["key"]
        parts.append(part[part["n"] > 0])
    out = pd.concat(parts, ignore_index=True)
    out["k"] = out["k"].astype("int32")
    out["n"] = out["n"].astype("int32")
    out["metric"] = out["metric"].astype("category")
    return out


def daily(con, level, who="batter"):
    df = con.execute(f"""
        select season, {who} as player, game_date, {_columns()}
        from pitches where level = '{level}' and game_type = 'R'
        group by season, {who}, game_date
        order by season, player, game_date""").df()
    return _long(df, ["season", "player", "game_date"])


def in_series(con, level, who="batter"):
    team = "bat_team" if who == "batter" else "fld_team"
    df = con.execute(f"""
        select gs.series_id, p.season, p.{team} as team, p.{who} as player, {_columns()}
        from pitches p join game_series gs using (game_pk)
        where p.level = '{level}' and p.game_type = 'R'
        group by gs.series_id, p.season, p.{team}, p.{who}
        order by gs.series_id, team, player""").df()
    return _long(df, ["series_id", "season", "team", "player"])
