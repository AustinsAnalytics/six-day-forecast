"""The social share card, site/og.png (1200 x 630), drawn from the pipeline's numbers. Needs Google Chrome.

    python tools/og.py
"""
import json
import math
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KEYS = ["chase", "whiff", "k", "bb", "gb", "hardhit", "barrel", "avg", "babip"]


def main():
    r = json.loads((SITE / "data" / "research.json").read_text())
    h = r["headline"]["AAA"]
    ms = {m["key"]: m for m in r["levels"]["AAA"]["metrics"]}
    x0, x1, lo, hi = 770, 1140, 0.25, 16
    X = lambda v: x0 + (math.log(max(lo, min(hi, v))) - math.log(lo)) / (math.log(hi) - math.log(lo)) * (x1 - x0)  # noqa: E731
    rows = []
    for i, k in enumerate(KEYS):
        m = ms[k]
        y = 150 + i * 40
        rows.append(f'<text x="752" y="{y + 5}" text-anchor="end" class="lab">{m["en"]}</text>'
                    f'<line x1="{X(m["sdf"]["ratio"])}" x2="{X(m["season"]["ratio"])}" y1="{y}" y2="{y}" stroke="#B9B09A" stroke-width="2"/>'
                    f'<circle cx="{X(m["season"]["ratio"])}" cy="{y}" r="8" fill="#C8451D"/>'
                    f'<circle cx="{X(m["sdf"]["ratio"])}" cy="{y}" r="8" fill="#2267A6"/>')
    ticks = "".join(f'<line x1="{X(v)}" x2="{X(v)}" y1="122" y2="{150 + len(KEYS) * 40 - 18}" stroke="#CFC7B4"/>'
                    f'<text x="{X(v)}" y="112" text-anchor="middle" class="tick">{"1×" if v == 1 else str(v) + "×"}</text>'
                    for v in (0.25, 0.5, 1, 2, 4, 8, 16))
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&family=IBM+Plex+Mono:wght@500&display=block" rel="stylesheet">
<style>
html, body {{ margin: 0; }}
body {{ width: 1200px; height: 630px; background: #F2EEE3; color: #132230; font-family: Archivo, sans-serif; position: relative; overflow: hidden; }}
.mark {{ position: absolute; left: 64px; top: 52px; display: flex; gap: 12px; align-items: center; font-weight: 800;
  font-variation-settings: "wdth" 72; letter-spacing: .08em; font-size: 22px; text-transform: uppercase; }}
.big {{ position: absolute; left: 64px; top: 128px; font-weight: 800; font-variation-settings: "wdth" 70; font-size: 150px; line-height: .9; color: #C8451D; }}
.big small {{ font-size: 52px; color: #132230; }}
.say {{ position: absolute; left: 66px; top: 300px; width: 440px; font-size: 28px; line-height: 1.22; font-weight: 600; letter-spacing: -.01em; }}
.say b {{ color: #2267A6; }}
.foot {{ position: absolute; left: 64px; right: 64px; bottom: 44px; border-top: 2px solid #132230; padding-top: 14px; display: flex;
  justify-content: space-between; font-family: "IBM Plex Mono", monospace; font-size: 17px; letter-spacing: .04em; text-transform: uppercase; color: #3B4957; }}
svg {{ position: absolute; inset: 0; }}
.lab {{ font: 500 19px Archivo, sans-serif; fill: #3B4957; }}
.tick {{ font: 500 15px "IBM Plex Mono", monospace; fill: #66717C; }}
</style></head><body>
<svg width="1200" height="630">{ticks}<line x1="{X(1)}" x2="{X(1)}" y1="122" y2="{150 + len(KEYS) * 40 - 18}" stroke="#132230" stroke-width="2"/>{"".join(rows)}
<circle cx="700" cy="{150 + len(KEYS) * 40 + 4}" r="7" fill="#C8451D"/><text x="714" y="{150 + len(KEYS) * 40 + 10}" class="lab">Season line, as printed</text>
<circle cx="930" cy="{150 + len(KEYS) * 40 + 4}" r="7" fill="#2267A6"/><text x="944" y="{150 + len(KEYS) * 40 + 10}" class="lab">Six-Day Forecast</text></svg>
<div class="mark"><svg width="26" height="26" viewBox="0 0 32 32" style="position:static"><path d="M7 4v25" stroke="#132230" stroke-width="2.6" stroke-linecap="round"/><path d="M8.2 5 27 11 8.2 17Z" fill="#C8451D"/></svg>Six-Day Forecast</div>
<div class="big">{h["n_worse"]}<small> of {h["n_card"]}</small></div>
<div class="say">numbers on a standard advance card did worse than league average over the next series. <b>Shrinking each one by its own sample beat both.</b></div>
<div class="foot"><span>Jacksonville Jumbo Shrimp · Jupiter Hammerheads</span><span>2026, verified</span></div>
</body></html>"""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "og.html"
        page.write_text(html)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--window-size=1200,630", "--virtual-time-budget=8000", f"--user-data-dir={tmp}/prof",
                        f"--screenshot={SITE / 'og.png'}", page.as_uri()], check=True, capture_output=True)
    print("wrote", SITE / "og.png")


if __name__ == "__main__":
    main()
