"""Words on the card, in English and Spanish.

Spanish terms follow MLB's Spanish-language coverage (MLB.com/es): "swings fuera de la zona" for chasing,
"swings en blanco" for whiffs, "macetazos" for barrels, "batazos duros" for hard-hit balls, "boletos" for walks.
A bilingual coach should still read every template before it goes on a clubhouse wall.

Each hitter gets at most three lines, picked from numbers that are both trustworthy (trust >= MIN_TRUST) and far from
typical (forecast in the top or bottom EXTREME of the league's forecasts). One line per family, so a hitter who
whiffs a lot does not get three ways of saying it.
"""

MIN_TRUST = 0.35
EXTREME = 0.15
FAMILY = {"chase": "approach", "chase2k": "approach", "fps": "first", "whiff": "miss", "zcontact": "miss", "k": "miss",
          "whiff_fb": "type", "whiff_br": "type", "whiff_os": "type", "bb": "eye", "gb": "batted", "pullair": "batted",
          "oppo": "batted", "hardhit": "power", "barrel": "power", "whiff_up": "zone", "whiff_down": "zone"}

T = {
    ("chase", "high"): ("Chases {v} of pitches out of the zone (league {mu}). Expand with two strikes.",
                        "Le hace swing al {v} de los pitcheos fuera de la zona (liga {mu}). Con dos strikes, sácalo de la zona."),
    ("chase", "low"): ("Rarely chases: {v} out of the zone (league {mu}). Get ahead in the zone.",
                       "Casi no persigue: {v} de swings fuera de la zona (liga {mu}). Ataca la zona para ponerte adelante."),
    ("chase2k", "high"): ("With two strikes he chases {v} (league {mu}). Finish him off the plate.",
                          "Con dos strikes persigue el {v} (liga {mu}). Termínalo fuera del plato."),
    ("chase2k", "low"): ("Tough with two strikes: chases only {v} (league {mu}).",
                         "Difícil con dos strikes: solo persigue el {v} (liga {mu})."),
    ("fps", "high"): ("Swings at {v} of first pitches (league {mu}). Do not groove strike one.",
                      "Le hace swing al {v} de los primeros pitcheos (liga {mu}). No le regales el primer strike por el medio."),
    ("fps", "low"): ("Takes the first pitch: swings at only {v} (league {mu}). Steal strike one.",
                     "Deja pasar el primer pitcheo: solo le hace swing al {v} (liga {mu}). Gánale el primer strike."),
    ("whiff", "high"): ("Swings and misses: {v} of his swings come up empty (league {mu}).",
                        "Falla mucho: {v} de sus swings son en blanco (liga {mu})."),
    ("whiff", "low"): ("Hard to miss: only {v} of his swings come up empty (league {mu}). Expect the ball in play.",
                       "Difícil de hacer fallar: solo {v} de sus swings son en blanco (liga {mu}). Espera la bola en juego."),
    ("zcontact", "high"): ("Puts the bat on strikes: {v} contact in the zone (league {mu}).",
                           "Hace contacto en la zona: {v} (liga {mu})."),
    ("zcontact", "low"): ("Misses in the zone: {v} contact on strikes (league {mu}). You can challenge him.",
                          "Falla en la zona: solo {v} de contacto en strikes (liga {mu}). Se le puede retar en la zona."),
    ("k", "high"): ("Strikes out in {v} of trips (league {mu}).",
                    "Se poncha en el {v} de sus apariciones (liga {mu})."),
    ("k", "low"): ("Rarely strikes out: {v} of trips (league {mu}).",
                   "Casi no se poncha: {v} de sus apariciones (liga {mu})."),
    ("whiff_fb", "high"): ("Beatable with fastballs: misses on {v} of his swings at them (league {mu}).",
                           "Se le puede ganar con la recta: falla en el {v} de sus swings contra ella (liga {mu})."),
    ("whiff_fb", "low"): ("Handles velocity: misses on only {v} of swings at fastballs (league {mu}).",
                          "Le batea a la recta: solo falla en el {v} de sus swings contra ella (liga {mu})."),
    ("whiff_br", "high"): ("Breaking balls get him: misses on {v} of his swings at them (league {mu}).",
                           "Los rompientes lo dominan: falla en el {v} de sus swings contra ellos (liga {mu})."),
    ("whiff_br", "low"): ("Sees spin well: misses on only {v} of swings at breaking balls (league {mu}).",
                          "Ve bien los rompientes: solo falla en el {v} de sus swings contra ellos (liga {mu})."),
    ("whiff_os", "high"): ("Changeups and splitters get him: misses on {v} of his swings at them (league {mu}).",
                           "El cambio y el splitter lo dominan: falla en el {v} de sus swings contra ellos (liga {mu})."),
    ("whiff_os", "low"): ("Stays back on offspeed: misses on only {v} of swings at changeups and splitters (league {mu}).",
                          "No se deja engañar con el cambio: solo falla en el {v} de sus swings (liga {mu})."),
    ("bb", "high"): ("Walks in {v} of trips (league {mu}). Attack him; do not give free passes.",
                     "Recibe boleto en el {v} de sus apariciones (liga {mu}). Atácalo; no le regales boletos."),
    ("bb", "low"): ("Rarely walks: {v} of trips (league {mu}). He is up there to swing.",
                    "Casi no recibe boletos: {v} de sus apariciones (liga {mu}). Viene a hacer swing."),
    ("gb", "high"): ("Ground-ball hitter: {v} of his balls in play are on the ground (league {mu}).",
                     "Bateador de rodados: {v} de sus bolas en juego van por el suelo (liga {mu})."),
    ("gb", "low"): ("Lifts the ball: only {v} of his balls in play are grounders (league {mu}).",
                    "Levanta la bola: solo {v} de sus bolas en juego son rodados (liga {mu})."),
    ("pullair", "high"): ("His damage is pulled in the air: {v} of balls in play (league {mu}).",
                          "Su daño es halando la bola por el aire: {v} de sus bolas en juego (liga {mu})."),
    ("oppo", "high"): ("Uses the opposite field: {v} of balls in play (league {mu}).",
                       "Batea hacia la banda contraria: {v} de sus bolas en juego (liga {mu})."),
    ("hardhit", "high"): ("Hits it hard: {v} of his balls in play leave at 95+ mph (league {mu}).",
                          "Le pega duro: {v} de sus bolas en juego salen a 95+ mph (liga {mu})."),
    ("hardhit", "low"): ("Soft contact: only {v} of his balls in play leave at 95+ mph (league {mu}).",
                         "Contacto suave: solo {v} de sus bolas en juego salen a 95+ mph (liga {mu})."),
    ("barrel", "high"): ("Power threat: barrels {v} of his balls in play (league {mu}).",
                         "Peligro de poder: {v} de sus bolas en juego son macetazos (liga {mu})."),
    ("whiff_up", "high"): ("Misses up: {v} of his swings in the top half come up empty (league {mu}).",
                           "Falla arriba: {v} de sus swings en la mitad alta son en blanco (liga {mu})."),
    ("whiff_up", "low"): ("Handles the top of the zone: misses on only {v} of swings up (league {mu}).",
                          "Le batea arriba: solo {v} de sus swings en la mitad alta son en blanco (liga {mu})."),
    ("whiff_down", "high"): ("Misses down: {v} of his swings in the bottom half come up empty (league {mu}).",
                             "Falla abajo: {v} de sus swings en la mitad baja son en blanco (liga {mu})."),
    ("whiff_down", "low"): ("Handles the bottom of the zone: misses on only {v} of swings down (league {mu}).",
                            "Le batea abajo: solo {v} de sus swings en la mitad baja son en blanco (liga {mu})."),
}


def pct(x, es=False):
    s = f"{round(100 * x)}%"
    return s


def three_things(metrics, polarity=None, extreme=EXTREME, min_trust=MIN_TRUST):
    best = {}
    for key, fam in FAMILY.items():
        m = metrics.get(key)
        if not m or m.get("v") is None or m.get("pct") is None or (m.get("t") or 0) < min_trust:
            continue
        if m["pct"] >= 1 - extreme:
            side = "high"
        elif m["pct"] <= extreme:
            side = "low"
        else:
            continue
        if (key, side) not in T:
            continue
        score = abs(m["pct"] - 0.5) + 0.05 * m["t"]
        if fam not in best or score > best[fam][0]:
            best[fam] = (score, key, side)
    picks = sorted(best.values(), reverse=True)[:3]
    out = []
    for _, key, side in picks:
        m = metrics[key]
        en, es = T[(key, side)]
        out.append({"key": key, "side": side, "pct": m["pct"], "t": m["t"],
                    "en": en.format(v=pct(m["v"]), mu=pct(m["mu"])),
                    "es": es.format(v=pct(m["v"]), mu=pct(m["mu"]))})
    return out


def _names(xs, n=3):
    return [x for x in xs][:n]


def discussion(p):
    """A short forecast discussion for the top of the packet, built only from numbers the card trusts."""
    hitters = [h for h in p["hitters"] if h["pa"] >= 40]
    lines_en, lines_es = [], []

    def lineup(key):
        tot, w = 0.0, 0.0
        for h in hitters:
            m = h["m"].get(key)
            if m and m["v"] is not None:
                tot += m["v"] * h["pa"]
                w += h["pa"]
        mu = next((h["m"][key]["mu"] for h in hitters if key in h["m"]), None)
        return (tot / w if w else None), mu

    chase, chase_mu = lineup("chase")
    whiff, whiff_mu = lineup("whiff")
    if chase is not None and chase_mu:
        lines_en.append(f"Lineup chases {pct(chase)} of pitches out of the zone (league {pct(chase_mu)}) and "
                        f"misses on {pct(whiff)} of swings (league {pct(whiff_mu)}).")
        lines_es.append(f"La alineación le hace swing al {pct(chase)} de los pitcheos fuera de la zona "
                        f"(liga {pct(chase_mu)}) y falla en el {pct(whiff)} de sus swings (liga {pct(whiff_mu)}).")
    attack = [h for h in hitters if any(t["key"] in ("chase", "chase2k", "whiff", "zcontact", "k", "whiff_br",
                                                     "whiff_fb", "whiff_os") and
                                        ((t["side"] == "high") != (t["key"] == "zcontact")) for t in h["three"])]
    danger = [h for h in hitters if any(t["key"] in ("barrel", "hardhit") and t["side"] == "high" for t in h["three"])]
    tough = [h for h in hitters if any((t["key"] in ("chase", "whiff", "k") and t["side"] == "low") for t in h["three"])]
    if attack:
        nm = ", ".join(h["name"] for h in _names(attack))
        lines_en.append(f"Most to work with: {nm}.")
        lines_es.append(f"Los más vulnerables: {nm}.")
    if tough:
        nm = ", ".join(h["name"] for h in _names(tough))
        lines_en.append(f"Toughest outs: {nm}.")
        lines_es.append(f"Los outs más difíciles: {nm}.")
    if danger:
        nm = ", ".join(h["name"] for h in _names(danger))
        lines_en.append(f"Damage to respect: {nm}.")
        lines_es.append(f"Cuidado con el poder de: {nm}.")
    thin = [h for h in p["hitters"] if h["pa"] < 40]
    if thin:
        lines_en.append(f"{len(thin)} hitter{'s' if len(thin) != 1 else ''} with under 40 plate appearances at this level: "
                        "their cards lean on the league average, and say so.")
        lines_es.append(f"{len(thin)} bateador{'es' if len(thin) != 1 else ''} con menos de 40 apariciones en este nivel: "
                        "sus tarjetas se apoyan en el promedio de la liga, y lo indican.")
    busy = []
    first = __import__("datetime").date.fromisoformat(p["start"])
    since = (first - __import__("datetime").timedelta(days=4)).isoformat()
    for x in p["pitchers"]:
        rec = [r for r in (x.get("recent") or []) if r["d"] >= since]
        if x.get("role") == "RP" and (sum(r["p"] for r in rec) >= 35 or len(rec) >= 2):
            busy.append((x["name"], len(rec), sum(r["p"] for r in rec)))
    busy.sort(key=lambda b: -b[2])
    if busy:
        en = ", ".join(f"{n} ({g} games, {pt} pitches)" for n, g, pt in busy[:4])
        es = ", ".join(f"{n} ({g} juegos, {pt} pitcheos)" for n, g, pt in busy[:4])
        lines_en.append(f"Bullpen, last four days before the series: {en}.")
        lines_es.append(f"Bullpen, últimos cuatro días antes de la serie: {es}.")
    return {"en": lines_en, "es": lines_es}
