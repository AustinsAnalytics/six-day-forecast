# Six-Day Forecast: download, build, test the forecasts, make the packets, render the site.
# Each step reads the previous step's output.
PY ?= python

.PHONY: all data build analysis packets site extras test serve clean-cache

all: build analysis packets site test

data:            ## schedules, players, clubs and every tracked pitch, Triple-A and Florida State League 2024-2026 (slow: polite request spacing)
	for s in 2024 2025 2026; do "$(PY)" pipeline/fetch.py teams $$s; \
	  for lv in AAA FSL; do "$(PY)" pipeline/fetch.py schedule $$lv $$s; "$(PY)" pipeline/fetch.py players $$lv $$s; \
	  "$(PY)" pipeline/fetch.py statcast $$lv $$s; done; done

build:           ## data/sdf.duckdb: games, series, players and pitches with the flags the card uses
	"$(PY)" pipeline/build.py

analysis:        ## the backtest (tune on 2025, score 2026), the series-familiarity test, the development tracker
	"$(PY)" pipeline/backtest.py AAA FSL
	"$(PY)" pipeline/familiarity.py AAA FSL
	"$(PY)" pipeline/develop.py

packets:         ## the Monday packet for every 2026 Jacksonville and Jupiter series (fetches Monday rosters once)
	"$(PY)" pipeline/packet.py

site:            ## site data, the page with every number filled from the outputs, printed packets, share card (needs Google Chrome)
	"$(PY)" pipeline/export.py
	"$(PY)" pipeline/story.py
	"$(PY)" tools/pdfs.py
	"$(PY)" tools/og.py

test:
	"$(PY)" -m pytest -q

serve:
	"$(PY)" -m http.server 8645 --directory site

clean-cache:     ## drop cached counts so the next run recomputes them from the database
	rm -rf data/cache
