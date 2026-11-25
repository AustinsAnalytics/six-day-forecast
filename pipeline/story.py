"""Fill templates/index.html with numbers from the pipeline's outputs -> site/index.html. Nothing on the page is typed.

    python pipeline/story.py
"""
import json
import re
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
SITE = ROOT / "site"


def pts(x, sign=True):
    """wOBA effect in points (thousandths), one decimal, with a real minus sign."""
    v = 1000 * x
    s = f"{abs(v):.1f}"
    if not sign:
        return s
    return ("+" if v >= 0 else "−") + s


def featured_label(s):
    d = date.fromisoformat(s["monday"])
    return f"{d.strftime('%B')} {d.day}"


def pdf_links():
    """Links to the printed packets tools/pdfs.py made for each team's last series."""
    out = []
    for team, name in (("JAX", "Jacksonville"), ("JUP", "Jupiter")):
        idx = json.loads((SITE / "data" / "packets" / team / "index.json").read_text())
        s = idx["series"][-1]
        where = f"{'vs.' if s['home'] else 'at'} {s['opp']}"
        out.append(f'{name} {where} (<a href="packets/{team}-{s["start"]}-en.pdf">English</a> &middot; '
                   f'<a href="packets/{team}-{s["start"]}-es.pdf">Español</a>)')
    return "; ".join(out)


def starts_phrase(x):
    if x <= 1:
        return "a single start"
    if x <= 2:
        return "one or two starts"
    return f"about {round(x)} starts"


def rnd(x, base=5):
    return int(base * round(float(x) / base))


def build():
    research = json.loads((SITE / "data" / "research.json").read_text())
    dev = json.loads((OUT / "develop.json").read_text())
    h, hf = research["headline"]["AAA"], research["headline"]["FSL"]
    aaa = {m["key"]: m for m in research["levels"]["AAA"]["metrics"]}
    fam, famf = research["familiarity"]["AAA"], research["familiarity"]["FSL"]
    con = duckdb.connect(str(ROOT / "data" / "sdf.duckdb"), read_only=True)
    n_pitches = con.execute("select count(*) from pitches").fetchone()[0]
    con.close()
    jax = json.loads((SITE / "data" / "packets" / "JAX" / "index.json").read_text())
    daily = pd.read_parquet(ROOT / "data" / "cache" / "daily_AAA.parquet")
    tot = daily[daily["season"] == 2026].groupby("metric", observed=True)["n"].sum()
    half_box = tot[["whiff_up", "whiff_down", "whiff_in", "whiff_away"]].median() / \
        tot[[f"whiff_z{z}" for z in range(1, 10)]].median()
    weeks = dev["weeks"]
    by_gap = lambda rows, g: next(r for r in rows if abs(r["gap"] - g) < 1e-9)  # noqa: E731
    checks = dev["checks"]
    p_tests = sum(c["pitchers"]["tested"] for c in checks.values())
    p_false = sum(c["pitchers"]["shuffled_alarms"] for c in checks.values())
    p_real = sum(c["pitchers"]["alarms"] for c in checks.values())
    hit_tests = sum(c["hitters"]["tested"] for c in checks.values())
    hit_real = sum(c["hitters"]["alarms"] for c in checks.values())
    hit_shuf = sum(c["hitters"]["shuffled_alarms"] for c in checks.values())
    if hit_real == 0 and hit_shuf == 0:
        hit_phrase = "the change test fired on none of them, and on none of the shuffled versions either"
    else:
        hit_phrase = f"the change test fired {hit_real} times on the real seasons and {hit_shuf} times on shuffled ones"

    def m_range(key):
        a, b = sorted(int(round(aaa[key]["M_stab"][s])) for s in ("2025", "2026"))
        a, b = rnd(a, 10), rnd(b, 10)
        return f"{a}" if a == b else f"{a} to {b}"

    nine = h["nine_whiff_season"]
    v = {
        "n_worse": h["n_worse"], "n_card": h["n_card"], "n_l14_worse": h["n_l14_worse"],
        "n_worse_sure": h["n_worse_sure"], "cut_vs_season": round(100 * h["cut_vs_season"]),
        "n_series": research["levels"]["AAA"]["n_series"],
        "n_hitter_series": f"{research['levels']['AAA']['n_hitter_series']:,}",
        "fsl_n_worse": hf["n_worse"], "fsl_n_card": hf["n_card"],
        "M_chase": rnd(aaa["chase"]["M_stab"]["2026"]), "M_fps": rnd(aaa["fps"]["M_stab"]["2026"]),
        "M_k": rnd(aaa["k"]["M_stab"]["2026"]), "M_avg": m_range("avg"), "M_babip": m_range("babip"),
        "cov80": round(100 * h["cov80"]), "naive80": round(100 * h["naive80"]),
        "nine_whiff_lo": f"{min(nine):.1f}", "nine_whiff_hi": f"{max(nine):.1f}",
        "nine_avg_dead": 9 - h["nine_avg_measurable"],
        "fam_pas": f"{fam['pas']:,}", "fam_familiar": f"{fam['familiar_pas']:,}",
        "fam_xw": pts(fam["main"]["xw"]["fam"]["coef"]), "fam_lo": pts(fam["main"]["xw"]["fam"]["lo"]),
        "fam_hi": pts(fam["main"]["xw"]["fam"]["hi"]),
        "fam_k": f"{abs(100 * fam['main']['k']['fam']['coef']):.1f}",
        "tto3": pts(fam["main"]["xw"]["tto3"]["coef"]), "platoon": pts(fam["main"]["xw"]["platoon"]["coef"]),
        "fsl_fam_xw": pts(famf["main"]["xw"]["fam"]["coef"]), "fsl_fam_lo": pts(famf["main"]["xw"]["fam"]["lo"]),
        "fsl_fam_hi": pts(famf["main"]["xw"]["fam"]["hi"]),
        "velo_phrase": starts_phrase(by_gap(weeks["pitchers"]["velo"]["by_gap"], 1.0)["outings"]),
        "arm_phrase": starts_phrase(by_gap(weeks["pitchers"]["arm_angle"]["by_gap"], 3.0)["outings"]),
        "chase_weeks": f"{by_gap(weeks['hitters']['chase']['by_gap'], 0.05)['weeks']:.0f}",
        "hh_weeks": f"{by_gap(weeks['hitters']['hardhit']['by_gap'], 0.05)['weeks']:.0f}",
        "starts_week": f"{weeks['pitchers']['velo']['starts_per_week']:.2f}",
        "dev_false": f"{100 * p_false / p_tests:.1f}", "dev_real": f"{100 * p_real / p_tests:.1f}",
        "hit_tests": hit_tests, "hit_alarm_phrase": hit_phrase,
        "n_pitches": f"{n_pitches / 1e6:.1f} million",
        "featured_start": jax["series"][-1]["start"],
        "half_box": f"{half_box:.0f}",
        "featured_label": featured_label(jax["series"][-1]),
        "pdf_links": pdf_links(),
        "built": date.today().strftime("%B %-d, %Y"),
    }
    v["og_description"] = (f"Printed raw, {v['n_worse']} of {v['n_card']} numbers on a standard advance card did worse than "
                           f"league average over the next series. A packet that knows how sure it is, for the Jacksonville "
                           f"Jumbo Shrimp and Jupiter Hammerheads.")
    html = (ROOT / "templates" / "index.html").read_text()
    missing = set(re.findall(r"{{(\w+)}}", html)) - set(v)
    if missing:
        raise SystemExit(f"no value for: {sorted(missing)}")
    for k, val in v.items():
        html = html.replace("{{" + k + "}}", str(val))
    (SITE / "index.html").write_text(html)
    (OUT / "story_values.json").write_text(json.dumps(v, indent=1))
    return v


if __name__ == "__main__":
    for k, val in build().items():
        print(f"{k:16s} {val}")
