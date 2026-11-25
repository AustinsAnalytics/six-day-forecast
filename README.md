# Six-Day Forecast

**An advance-scouting packet that says how sure it is, checked against the six games that followed.**
Site: https://austinsanalytics.github.io/six-day-forecast/

Every Monday in the minors, someone builds the packet for the next six games. Most packets print every number the same way, whether it rests on four hundred pitches or four. This project rebuilds the Monday packet for the Miami Marlins' Triple-A (Jacksonville Jumbo Shrimp) and Single-A (Jupiter Hammerheads) affiliates so that every number carries its own confidence, in English and Spanish, and then grades every forecast against the series that followed. It answers three questions a player development staff asks:

| Question | Answer | Evidence (Triple-A, 2026 series, settings tuned on 2025 only) |
|---|---|---|
| How much of a standard advance card can you trust? | **Mostly the swing decisions.** | Printed raw, 24 of 29 card numbers landed further from the hitter's true rate in the next series than plain league average did (20 by more than the uncertainty). Every last-14-days line did worse than league average. Shrinking each number by its own sample beat league average on all 29 and beat the season line on all 29, cutting its error by a median of 65%. Its 80% ranges held 78.4% of outcomes. 389 series, 10,180 hitter-series; the same pattern holds in the Florida State League (22 of 27). |
| Do hitters catch up over a six-game series? | **No.** | Within the same pitcher outing, hitters who already faced him earlier in the series did no damage beyond expectation: +0.5 points of expected wOBA (95% CI −3.8 to +4.7) across 506,896 plate appearances, 2024–2026. The same design finds the third-time-through-the-order effect (+16.8) and the platoon edge (+27.8). |
| How long before a development change is clear? | **Pitch shape: days. Plate discipline: months.** | A one-mph fastball change is clear (90%) after one or two starts. A five-point change in chase rate takes about 6 weeks of a regular's pitches; in hard-hit rate, about 21 weeks. On 2026 Jacksonville and Jupiter pitchers the change detector fired on 7.4% of tests against 0.9% on the same games shuffled, and it calls a renamed pitch a relabel rather than an addition. |

The site has the Monday packet for every 2026 series of both affiliates (opposing hitters and pitchers, a lineup-at-a-glance table, a forecast discussion, and a "what happened" view that puts each forecast next to the series), printable on letter paper in black and white, plus the full verification, the familiarity test, and the development tracker.

## Run it

```bash
pip install -r requirements.txt
make data       # Baseball Savant minor league search + MLB Stats API, 2024-2026 (slow: polite request spacing, ~1.5 GB)
make all        # database, backtest, familiarity, development, packets, page, tests
make serve      # http://localhost:8645
```

`make site` also prints the featured packets to PDF and draws the share card, both with headless Google Chrome. Every number on the page is written by `pipeline/story.py` from the pipeline's outputs, and the renderer refuses to run if a number in the template has no value.

## Pipeline

| Step | File | What it does |
|---|---|---|
| Fetch | `pipeline/fetch.py` | Tracked pitches by game day for Triple-A and the Florida State League, schedules, players, clubs, and each opponent's active roster on the Monday before a series |
| Build | `pipeline/build.py` | DuckDB: 2.6 million pitches with the flags every card number needs; games grouped into series (same two clubs, no gap over three days) |
| Metrics | `pipeline/metrics.py` | Every card number as a count, *k* of *n*: swing decisions, contact, results, batted balls, platoon splits, zone halves, and the nine-box hot zone |
| Forecast | `pipeline/forecast.py` | Beta-binomial shrinkage: (*k* + *M*·*μ*)/(*n* + *M*), recent games weighted more, last season at a discount; splits and zone halves shrink toward the hitter's own overall forecast |
| Backtest | `pipeline/backtest.py` | Grid search on 2025 series for each number's half-life, last-season weight and *M*; scores 2026 against league average, the season line and the last-14-days line, with an in-series noise correction and series-bootstrap intervals; calibration of the 80% ranges |
| Familiarity | `pipeline/familiarity.py` | Two-way fixed effects (pitcher outing, hitter-season) with series-clustered errors |
| Development | `pipeline/develop.py` | Bayesian change tests on pitch traits (park camera offsets removed), usage and hitter rates; relabel check; shuffled-season false-alarm rates; weeks-to-know |
| Packets | `pipeline/packet.py`, `pipeline/text.py` | One JSON file per series per affiliate; three trusted lines per hitter and the forecast discussion, in English and Spanish |
| Site | `pipeline/export.py`, `pipeline/story.py`, `tools/pdfs.py`, `tools/og.py` | Site data, page rendering, printed packets, share card |

## Checks

`tests/` (17 tests): the crossover math (a raw rate's error is *M*/*n* times league average's; shrinkage gives *M*/(*n*+*M*)), the unbiased noise correction, recovering a planted stabilization point, the change tests' false-alarm rates, the fixed-effects design recovering a planted effect, a forecast never seeing the day it forecasts, metric definitions on hand-built pitches (bunts and pitch-clock calls excluded, pull side by handedness), the Spanish templates, and the published packets (every forecast inside its own range, real counts stopping before game one).

## Limits

Public data only: no bat tracking, biomechanics, internal grades, or development plans. Double-A (Pensacola) and High-A (Beloit) have no public pitch tracking. Pitch types are Savant's labels. The Spanish follows the terms MLB's Spanish-language coverage uses and should still be read by a bilingual coach before it goes on a wall.

Built with Claude Code. Data from Baseball Savant and the MLB Stats API; not affiliated with MLB, MiLB, or any club.
