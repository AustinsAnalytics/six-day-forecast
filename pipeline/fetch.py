"""Download what Six-Day Forecast needs from public MLB sources.

    python pipeline/fetch.py schedule AAA 2026   -> data/raw/schedule_AAA_2026.json
    python pipeline/fetch.py statcast AAA 2026   -> data/raw/statcast_AAA_2026/{date}.csv (one file per game day)
    python pipeline/fetch.py players AAA 2026    -> data/raw/players_AAA_2026.json
    python pipeline/fetch.py teams 2026          -> data/raw/teams_2026.json (Triple-A and Single-A clubs)
    python pipeline/fetch.py roster 564 2026-09-15 -> data/raw/rosters/564_2026-09-15.json

Levels: AAA is every Triple-A game (International and Pacific Coast Leagues, sportId 11).
FSL is the Florida State League (Single-A, sportId 14, leagueId 123), home of the Jupiter Hammerheads.
Those are the two levels with public Hawk-Eye pitch tracking on Baseball Savant.
Every step skips files it already has and spaces its requests out.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
UA = {"User-Agent": "six-day-forecast research script (personal, non-commercial)"}
LEVELS = {
    "AAA": {"sport": 11, "league": None, "savant": "AAA"},
    "FSL": {"sport": 14, "league": 123, "savant": "A"},
}
SCHEDULE_FIELDS = ("dates,date,games,gamePk,gameType,officialDate,status,codedGameState,detailedState,teams,away,home,"
                   "team,id,name,score,venue,seriesGameNumber,gamesInSeries,doubleHeader,gameNumber,dayNight,"
                   "scheduledInnings,isTie,resumedFrom,rescheduledFrom")


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i + 1}: {e}", flush=True)
            time.sleep(6 * (i + 1))
    raise RuntimeError(url)


def schedule(level, season):
    lv = LEVELS[level]
    q = {"sportId": lv["sport"], "season": season, "gameType": "R,F,D,L,W", "fields": SCHEDULE_FIELDS}
    if lv["league"]:
        q["leagueId"] = lv["league"]
    out = RAW / f"schedule_{level}_{season}.json"
    out.write_bytes(get("https://statsapi.mlb.com/api/v1/schedule?" + urllib.parse.urlencode(q)))
    d = json.loads(out.read_text())
    games = [g for x in d["dates"] for g in x["games"]]
    print(level, season, sum(g["status"]["codedGameState"] == "F" for g in games), "final games of", len(games))


def game_days(level, season):
    d = json.loads((RAW / f"schedule_{level}_{season}.json").read_text())
    return sorted({g["officialDate"] for x in d["dates"] for g in x["games"] if g["status"]["codedGameState"] == "F"})


def statcast(level, season):
    folder = RAW / f"statcast_{level}_{season}"
    folder.mkdir(parents=True, exist_ok=True)
    days = game_days(level, season)
    for i, day in enumerate(days):
        out = folder / f"{day}.csv"
        if out.exists() and out.stat().st_size > 2000:
            continue
        q = urllib.parse.urlencode({
            "all": "true", "hfGT": "R|F|D|L|W|", "hfSea": f"{season}|", "hfLevel": f"{LEVELS[level]['savant']}|",
            "player_type": "pitcher", "game_date_gt": day, "game_date_lt": day, "min_pitches": 0, "min_results": 0,
            "group_by": "name", "sort_col": "pitches", "sort_order": "desc", "min_abs": 0, "type": "details",
            "minors": "true"})
        body = get("https://baseballsavant.mlb.com/statcast-search-minors/csv?" + q)
        out.write_bytes(body)
        print(f"  {level} {season} [{i + 1}/{len(days)}] {day} {len(body) // 1024} KB", flush=True)
        time.sleep(1.5)
    print(level, season, len(list(folder.glob("*.csv"))), "game days on disk")


def players(level, season):
    lv = LEVELS[level]
    fields = ("people,id,fullName,firstName,lastName,useName,boxscoreName,birthDate,birthCountry,height,weight,"
              "primaryPosition,abbreviation,batSide,pitchHand,code,currentTeam,id,mlbDebutDate")
    out = RAW / f"players_{level}_{season}.json"
    out.write_bytes(get(f"https://statsapi.mlb.com/api/v1/sports/{lv['sport']}/players?season={season}&fields={fields}"))
    print("players", level, season, len(json.loads(out.read_text()).get("people", [])))


def teams(season):
    fields = "teams,id,name,abbreviation,teamName,locationName,league,id,name,sport,id,parentOrgId,parentOrgName"
    out = RAW / f"teams_{season}.json"
    out.write_bytes(get(f"https://statsapi.mlb.com/api/v1/teams?sportIds=11,14&season={season}&fields={fields}"))
    print("teams", season, len(json.loads(out.read_text())["teams"]))


def roster(team_id, day):
    folder = RAW / "rosters"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{team_id}_{day}.json"
    if not out.exists():
        out.write_bytes(get(f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active&date={day}"
                            "&hydrate=person"))
        time.sleep(0.4)
    return json.loads(out.read_text())


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "schedule":
        schedule(sys.argv[2], int(sys.argv[3]))
    elif cmd == "statcast":
        statcast(sys.argv[2], int(sys.argv[3]))
    elif cmd == "players":
        players(sys.argv[2], int(sys.argv[3]))
    elif cmd == "teams":
        teams(int(sys.argv[2]))
    elif cmd == "roster":
        roster(int(sys.argv[2]), sys.argv[3])
    else:
        raise SystemExit(__doc__)
