"""Build data/sdf.duckdb: games, series, teams, players and every tracked pitch, with the flags the cards use.

    python pipeline/build.py

Series: minor league teams play the same opponent for most of a week (Tuesday to Sunday, Monday off).
A series is a run of games between the same home and away team with no gap longer than three days.
The packet for a series is built from data strictly before its first game, the way a Fellow builds it on Monday.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "sdf.duckdb"
LEVELS = ("AAA", "FSL")
SEASONS = (2024, 2025, 2026)

SWINGS = ("swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play")
WHIFFS = ("swinging_strike", "swinging_strike_blocked")
BUNTS = ("foul_bunt", "missed_bunt", "bunt_foul_tip")
NOT_PITCHES = ("automatic_ball", "automatic_strike")          # pitch-clock and other rule calls: no pitch thrown
FASTBALLS = ("FF", "SI", "FC", "FA")
BREAKING = ("SL", "ST", "CU", "KC", "SV", "CS")
OFFSPEED = ("CH", "FS", "FO", "SC")


def sql_list(xs):
    return "(" + ", ".join(f"'{x}'" for x in xs) + ")"


# events is empty on every pitch that does not end a plate appearance, so the bunt test must not turn into NULL there
# (a NULL here once dropped every non-final pitch from the swing counts).
IS_BUNT = f"(t.description in {sql_list(BUNTS)} or coalesce(t.events in ('sac_bunt', 'bunt_groundout'), false))"


def load_schedules(con):
    rows = []
    for level in LEVELS:
        for season in SEASONS:
            path = RAW / f"schedule_{level}_{season}.json"
            d = json.loads(path.read_text())
            for x in d["dates"]:
                for g in x["games"]:
                    h, a = g["teams"]["home"], g["teams"]["away"]
                    rows.append((g["gamePk"], level, season, g["officialDate"], g["gameType"],
                                 h["team"]["id"], h["team"]["name"], a["team"]["id"], a["team"]["name"],
                                 h.get("score"), a.get("score"), g["status"]["codedGameState"],
                                 g.get("seriesGameNumber"), g.get("gamesInSeries"), g.get("doubleHeader"),
                                 g.get("gameNumber"), g.get("scheduledInnings"), g.get("venue", {}).get("name")))
    cols = ["game_pk", "level", "season", "game_date", "game_type", "home_id", "home_name", "away_id", "away_name",
            "home_score", "away_score", "state", "series_game_number", "games_in_series", "double_header",
            "game_number", "scheduled_innings", "venue"]
    df = pd.DataFrame(rows, columns=cols)
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    for c in ("home_score", "away_score", "series_game_number", "games_in_series", "game_number", "scheduled_innings"):
        df[c] = df[c].astype("Int64")
    con.execute("create or replace table games as select * from df")
    # a game can appear twice in a schedule (postponed, then made up); keep the final one
    con.execute("""create or replace table games as select * from games
        qualify row_number() over (partition by game_pk order by (state = 'F') desc, game_date desc) = 1""")


def build_series(con):
    games = con.execute("""select game_pk, level, season, game_date, game_type, home_id, away_id from games
        where state = 'F' order by level, season, home_id, away_id, game_date, game_number""").fetchall()
    out, last = [], {}
    sid = 0
    for pk, level, season, day, gtype, home, away in games:
        key = (level, season, home, away, gtype == "R")
        prev = last.get(key)
        if prev is None or (day - prev[1]).days > 3:
            sid += 1
            prev = (sid, day)
        last[key] = (prev[0], day)
        out.append((pk, prev[0]))
    gs = pd.DataFrame(out, columns=["game_pk", "series_id"])  # noqa: F841 (read by duckdb below)
    con.execute("create or replace table game_series as select * from gs")
    con.execute("""create or replace table series as
        select s.series_id, any_value(g.level) level, any_value(g.season) season, any_value(g.game_type) game_type,
               any_value(g.home_id) home_id, any_value(g.home_name) home_name,
               any_value(g.away_id) away_id, any_value(g.away_name) away_name,
               min(g.game_date) start_date, max(g.game_date) end_date, count(*) n_games
        from game_series s join games g using (game_pk) group by s.series_id""")
    con.execute("""create or replace table game_series as
        select gs.*, row_number() over (partition by gs.series_id order by g.game_date, g.game_number) as game_in_series
        from game_series gs join games g using (game_pk)""")


def load_teams_players(con):
    teams, players = [], {}
    for level in LEVELS:
        for season in SEASONS:
            for p in json.loads((RAW / f"players_{level}_{season}.json").read_text()).get("people", []):
                players[p["id"]] = (p["id"], p.get("fullName"), p.get("useName") or p.get("firstName"),
                                    p.get("lastName"), p.get("boxscoreName"), p.get("birthDate"),
                                    p.get("birthCountry"), p.get("height"), p.get("weight"),
                                    (p.get("primaryPosition") or {}).get("abbreviation"),
                                    (p.get("batSide") or {}).get("code"), (p.get("pitchHand") or {}).get("code"),
                                    p.get("mlbDebutDate"))
    for season in SEASONS:
        for t in json.loads((RAW / f"teams_{season}.json").read_text())["teams"]:
            teams.append((season, t["id"], t.get("abbreviation"), t.get("name"), t.get("teamName"),
                          t.get("locationName"), t["league"]["name"], t.get("parentOrgName")))
    pl = pd.DataFrame(list(players.values()), columns=[  # noqa: F841
        "id", "full_name", "use_name", "last_name", "boxscore_name", "birth_date", "birth_country", "height",
        "weight", "position", "bats", "throws", "mlb_debut"])
    tm = pd.DataFrame(teams, columns=["season", "id", "abbrev", "name", "team_name", "location", "league",  # noqa: F841
                                      "parent_org"])
    con.execute("create or replace table players as select * from pl")
    con.execute("create or replace table teams as select * from tm")


def load_pitches(con):
    globs = [str(RAW / f"statcast_{lv}_{s}" / "*.csv") for lv in LEVELS for s in SEASONS
             if any((RAW / f"statcast_{lv}_{s}").glob("*.csv"))]
    files = ", ".join(f"'{g}'" for g in globs)
    num = lambda c: f"try_cast(nullif({c}, '') as double)"  # noqa: E731
    i = lambda c: f"try_cast(nullif({c}, '') as integer)"  # noqa: E731
    con.execute(f"""create or replace table pitches as
    with raw as (
        select * from read_csv([{files}], header=true, all_varchar=true, union_by_name=true, filename=true)
    ), typed as (
        select
            case when filename like '%statcast_AAA_%' then 'AAA' else 'FSL' end as level,
            {i('game_year')} season, try_cast(game_pk as bigint) game_pk, cast(game_date as date) game_date,
            {i('at_bat_number')} ab, {i('pitch_number')} pn, {i('inning')} inning, inning_topbot,
            try_cast(batter as integer) batter, try_cast(pitcher as integer) pitcher, player_name pitcher_name,
            stand, p_throws, {i('balls')} balls, {i('strikes')} strikes, {i('outs_when_up')} outs,
            on_1b is not null and on_1b <> '' as r1, on_2b is not null and on_2b <> '' as r2,
            on_3b is not null and on_3b <> '' as r3,
            nullif(pitch_type, '') pitch_type, pitch_name, description, nullif(events, '') events, type,
            nullif(bb_type, '') bb_type, {i('zone')} zone,
            {num('release_speed')} velo, {num('release_spin_rate')} spin, {num('spin_axis')} spin_axis,
            {num('pfx_x')} pfx_x, {num('pfx_z')} pfx_z, {num('plate_x')} plate_x, {num('plate_z')} plate_z,
            {num('sz_top')} sz_top, {num('sz_bot')} sz_bot,
            {num('release_pos_x')} rel_x, {num('release_pos_z')} rel_z, {num('release_extension')} ext,
            {num('arm_angle')} arm_angle, {num('api_break_z_with_gravity')} break_z_grav,
            {num('api_break_x_arm')} break_x_arm, {num('api_break_x_batter_in')} break_x_batter_in,
            {num('launch_speed')} ev, {num('launch_angle')} la, {i('launch_speed_angle')} lsa,
            {num('hc_x')} hc_x, {num('hc_y')} hc_y, {num('hit_distance_sc')} dist,
            {num('estimated_woba_using_speedangle')} xwoba, {num('estimated_ba_using_speedangle')} xba,
            {num('woba_value')} woba_value, {num('woba_denom')} woba_denom, {num('babip_value')} babip_value,
            {num('delta_run_exp')} delta_run_exp, {i('n_thruorder_pitcher')} tto,
            {i('pitcher_days_since_prev_game')} pitcher_rest, {i('age_bat')} age_bat, {i('age_pit')} age_pit,
            {i('home_score')} home_score, {i('away_score')} away_score, {i('bat_score')} bat_score,
            {i('fld_score')} fld_score, try_cast(fielder_2 as integer) catcher, des, home_team, away_team,
            {i('n_priorpa_thisgame_player_at_bat')} prior_pa_game
        from raw
    )
    select t.*,
        case when t.inning_topbot = 'Top' then g.away_id else g.home_id end as bat_team,
        case when t.inning_topbot = 'Top' then g.home_id else g.away_id end as fld_team,
        g.game_type,
        t.description not in {sql_list(NOT_PITCHES)} as is_pitch,
        t.description in {sql_list(SWINGS)} as is_swing,
        t.description in {sql_list(WHIFFS)} as is_whiff,
        {IS_BUNT} as is_bunt,
        t.zone between 1 and 9 as in_zone, t.zone between 11 and 14 as out_zone,
        t.type = 'X' and t.bb_type is not null as is_bip,
        case when t.pitch_type in {sql_list(FASTBALLS)} then 'FB' when t.pitch_type in {sql_list(BREAKING)} then 'BR'
             when t.pitch_type in {sql_list(OFFSPEED)} then 'OS' else 'XX' end as pitch_group,
        degrees(atan2(t.hc_x - 125.42, 198.27 - t.hc_y)) as spray
    from typed t join games g using (game_pk)
    qualify row_number() over (partition by t.game_pk, t.ab, t.pn order by t.game_date) = 1
    """)
    con.execute("create or replace table pitches as select * from pitches order by level, season, game_date, game_pk, ab, pn")


def main():
    con = duckdb.connect(str(DB))
    load_schedules(con)
    build_series(con)
    load_teams_players(con)
    load_pitches(con)
    for t in ("games", "series", "players", "teams", "pitches"):
        print(t, con.execute(f"select count(*) from {t}").fetchone()[0])
    print(con.execute("""select level, season, count(*) pitches, count(distinct game_pk) games,
        avg((pitch_type is not null)::int) tracked from pitches group by 1, 2 order by 1, 2""").fetchall())
    con.close()


if __name__ == "__main__":
    main()
