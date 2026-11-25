"""Everything the site shows, in one place: site/data/research.json and data/out/story.json (numbers for the text).

    python pipeline/export.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import signal_mse  # noqa: E402
from metrics import BY_KEY  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "out"
CACHE = ROOT / "data" / "cache"
SITE = ROOT / "site" / "data"
RNG = np.random.default_rng(20261125)
FAMILIES = [
    ("decisions", "Swing decisions", "Decisiones de swing", ["swing", "chase", "zswing", "fps", "chase2k"]),
    ("contact", "Contact", "Contacto", ["whiff", "zcontact", "ocontact", "whiff_fb", "whiff_br", "whiff_os"]),
    ("zone", "Zone halves", "Mitades de la zona", ["whiff_up", "whiff_down", "whiff_in", "whiff_away"]),
    ("results", "Results", "Resultados", ["k", "bb", "avg", "obp", "babip"]),
    ("batted", "Batted ball", "Bola en juego", ["gb", "pull", "oppo", "pullair", "hardhit", "barrel"]),
    ("split", "Platoon splits", "Splits por mano", ["k_vl", "k_vr", "avg_vl", "avg_vr"]),
]
CARD = [k for _, _, _, keys in FAMILIES for k in keys]
NINE = [f"whiff_z{z}" for z in range(1, 10)] + [f"avg_z{z}" for z in range(1, 10)]


def ratios(o):
    o = o[o["n"] >= 2]
    base = signal_mse(o["k"], o["n"], o["mu"])
    out = {"base": base, "obs": int(len(o))}
    for m in ("season_raw", "last14_raw", "sdf"):
        out[m] = signal_mse(o["k"], o["n"], o[m].fillna(o["mu"])) / base if base > 0 else None
    return out


def measurable(o, reps=300):
    """Is there any detectable hitter-to-hitter spread inside a series? Series-bootstrap 5th percentile of the
    league-average forecast's error must be above zero."""
    o = o[o["n"] >= 2]
    groups = list(o.groupby("series_id").indices.values())
    vals = []
    k, n, mu = o["k"].to_numpy(float), o["n"].to_numpy(float), o["mu"].to_numpy(float)
    for _ in range(reps):
        ix = np.concatenate([groups[i] for i in RNG.integers(0, len(groups), len(groups))])
        vals.append(signal_mse(k[ix], n[ix], mu[ix]))
    return float(np.percentile(vals, 5)) > 0


def level_block(level):
    bt = json.loads((OUT / f"backtest_{level}.json").read_text())
    params = json.loads((OUT / f"params_{level}.json").read_text())
    pred = pd.read_parquet(CACHE / f"pred_{level}_{bt['test']}.parquet")
    pa = pred[pred["metric"] == "k"][["series_id", "player", "n_s"]].rename(columns={"n_s": "pa"})
    pred = pred.merge(pa, on=["series_id", "player"], how="left")
    stab = bt["stabilization"]
    rows = []
    for key in CARD + NINE:
        if key not in bt["methods"]:
            continue
        o = pred[pred["metric"] == key]
        meas = measurable(o)
        r = bt["methods"][key]
        reg = ratios(o[o["pa"] >= 150])
        x = BY_KEY[key]
        rows.append({
            "key": key, "en": x["en"], "es": x["es"], "family": x["family"], "fmt": x["fmt"],
            "card": key in CARD, "measurable": meas, "obs": r["n_obs"],
            "season": r["season_raw"], "last14": r["last14_raw"], "sdf": r["sdf"],
            "reg": {"season": reg["season_raw"], "last14": reg["last14_raw"], "sdf": reg["sdf"], "obs": reg["obs"]},
            "M": params[key]["M"], "h": params[key]["h"], "w": params[key]["w"],
            "M_stab": {s: stab[s].get(key, {}).get("M") for s in stab},
            "mu": stab[str(bt["test"])].get(key, {}).get("mu"),
            "cov80": bt["calibration"].get(key, {}).get("coverage80"),
            "naive80": bt["calibration"].get(key, {}).get("naive_coverage80"),
        })
    return {"level": level, "train": bt["train"], "test": bt["test"], "n_series": bt["n_series_test"],
            "n_hitter_series": bt["n_hitter_series_test"], "metrics": rows, "crossover": bt["crossover"]}


def headline(block):
    card = [m for m in block["metrics"] if m["card"] and m["measurable"]]
    worse = [m for m in card if m["season"]["ratio"] > 1]
    worse_sure = [m for m in card if m["season"]["lo"] > 1]
    l14 = [m for m in card if m["last14"]["ratio"] > 1]
    sdf_better = [m for m in card if m["sdf"]["ratio"] < 1]
    sdf_sure = [m for m in card if m["sdf"]["hi"] < 1]
    cut_vs_season = float(np.median([1 - m["sdf"]["ratio"] / m["season"]["ratio"] for m in card]))
    cut_vs_league = float(np.median([1 - m["sdf"]["ratio"] for m in card]))
    reg_worse = [m["key"] for m in card if m["reg"]["season"] and m["reg"]["season"] > 1]
    reg_l14 = [m for m in card if m["reg"]["last14"] and m["reg"]["last14"] > 1]
    reg_sdf_beats_season = [m for m in card if m["reg"]["sdf"] < m["reg"]["season"]]
    unmeasurable = [m["key"] for m in block["metrics"] if m["card"] and not m["measurable"]]
    nine = [m for m in block["metrics"] if not m["card"]]
    return {"n_card": len(card), "n_worse": len(worse), "n_worse_sure": len(worse_sure), "n_l14_worse": len(l14),
            "n_sdf_better": len(sdf_better), "n_sdf_sure": len(sdf_sure), "cut_vs_season": cut_vs_season,
            "cut_vs_league": cut_vs_league, "reg_worse": reg_worse, "n_reg_l14_worse": len(reg_l14),
            "n_reg_sdf_beats_season": len(reg_sdf_beats_season), "unmeasurable": unmeasurable,
            "beats_league": [m["key"] for m in card if m["season"]["ratio"] <= 1],
            "nine_whiff_season": [m["season"]["ratio"] for m in nine if m["key"].startswith("whiff")],
            "nine_whiff_sdf": [m["sdf"]["ratio"] for m in nine if m["key"].startswith("whiff")],
            "nine_avg_measurable": sum(1 for m in nine if m["key"].startswith("avg") and m["measurable"]),
            "cov80": float(np.mean([m["cov80"] for m in card if m["cov80"]])),
            "naive80": float(np.mean([m["naive80"] for m in card if m["naive80"]]))}


def main():
    SITE.mkdir(parents=True, exist_ok=True)
    blocks = {lv: level_block(lv) for lv in ("AAA", "FSL")}
    fam = {lv: json.loads((OUT / f"familiarity_{lv}.json").read_text()) for lv in ("AAA", "FSL")}
    dev = json.loads((OUT / "develop.json").read_text())
    heads = {lv: headline(b) for lv, b in blocks.items()}
    research = {"levels": blocks, "families": [{"key": k, "en": en, "es": es, "metrics": ms} for k, en, es, ms in FAMILIES],
                "familiarity": fam, "headline": heads}
    (SITE / "research.json").write_text(json.dumps(research, separators=(",", ":"), default=float))
    (SITE / "develop.json").write_text(json.dumps(dev, separators=(",", ":"), default=float))
    (OUT / "story.json").write_text(json.dumps({"headline": heads}, indent=1, default=float))
    for lv, h in heads.items():
        print(lv, json.dumps({k: v for k, v in h.items() if not isinstance(v, list)}, default=float))
        print("   regulars worse than league:", h["reg_worse"], "| unmeasurable:", h["unmeasurable"])
        print("   beats league as printed:", h["beats_league"])


if __name__ == "__main__":
    main()
