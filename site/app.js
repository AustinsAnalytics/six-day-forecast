/* Six-Day Forecast: the packet viewer and every chart. Plain JavaScript, no libraries. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const PAGE = document.body.dataset.page || "index";
  const state = { team: "JAX", start: null, lang: "en", view: "fc", ratioWho: "all", cross: "chase" };
  let RESEARCH = null, DEVELOP = null;
  const INDEX = {}, PACKETS = {};

  // ------------------------------------------------------------------ words
  const W = {
    en: { approach: "Approach", contact: "Contact", outcomes: "Outcomes", batted: "Batted ball", range: "forecast · 80% range",
      zone: "Whiffs per swing, by half", spray: "Where it goes", std: "Standard line, raw", trustLow: "mostly league average",
      trustMed: "partly his own data", trustHigh: "mostly his own data", pa: "PA at", none: "No tendencies strong enough to trust yet. Pitch him like a league-average hitter.",
      didnt: "Did not play", inSeries: "In the series", inside: "inside their range", hitters: "Their hitters", pitchers: "Their pitchers",
      starts: "Rotation order, their last eight starts", actual: "Who actually started", disc: "Scouting forecast discussion", issued: "Issued",
      series: "Series", games: "games", at: "at", vs: "vs.", result: "Result", sp: "SP", rp: "RP", pitch: "Pitch", use: "Use",
      vl: "vs L", vr: "vs R", whiff: "Whiff", first: "1st", twok: "2K", last7: "Pitches, last 7 days", noData: "No tracked pitches at this level yet.",
      pitched: "Pitched", pitches: "pitches", notOnRoster: "not on Monday's roster", trust: "Trust", pull: "Pull", oppo: "Oppo",
      up: "Up", down: "Down", in_: "In", away: "Away", gp: "G", gs: "GS", arm: "arm", ext: "ext.", level: { AAA: "Triple-A", FSL: "Single-A" },
      verified: "of forecasts with a result landed inside their 80% range.", printTitle: "Monday packet", lg: "league" },
    es: { approach: "Enfoque", contact: "Contacto", outcomes: "Resultados", batted: "Bola en juego", range: "pronóstico · rango 80%",
      zone: "Swings en blanco, por mitad", spray: "Hacia dónde batea", std: "Línea estándar, sin ajustar", trustLow: "casi todo promedio de la liga",
      trustMed: "en parte sus propios datos", trustHigh: "casi todo sus propios datos", pa: "apariciones en", none: "Todavía no hay tendencias que los datos respalden. Lánzale como a un bateador promedio.",
      didnt: "No jugó", inSeries: "En la serie", inside: "dentro de su rango", hitters: "Sus bateadores", pitchers: "Sus lanzadores",
      starts: "Orden de rotación, sus últimas ocho aperturas", actual: "Quién abrió en realidad", disc: "Discusión del pronóstico de scouting",
      issued: "Emitido el", series: "Serie", games: "juegos", at: "en", vs: "vs.", result: "Resultado", sp: "Abridor", rp: "Relevista",
      pitch: "Pitcheo", use: "Uso", vl: "vs. Z", vr: "vs. D", whiff: "En blanco", first: "1.º", twok: "2 str.", last7: "Pitcheos, últimos 7 días",
      noData: "Todavía no hay pitcheos registrados en este nivel.", pitched: "Lanzó", pitches: "pitcheos", notOnRoster: "no estaba en el roster del lunes",
      trust: "Confianza", pull: "Halar", oppo: "Contraria", up: "Arriba", down: "Abajo", in_: "Adentro", away: "Afuera", gp: "J", gs: "JI",
      arm: "brazo", ext: "ext.", level: { AAA: "Triple-A", FSL: "Clase A" },
      verified: "de los pronósticos con resultado cayeron dentro de su rango de 80%.", printTitle: "Paquete del lunes", lg: "liga" },
  };
  const BATS = { en: { R: "R", L: "L", S: "S" }, es: { R: "D", L: "Z", S: "A" } };
  const MET = {
    chase: ["Chase", "Fuera de la zona", [0.12, 0.48], -1], zswing: ["Zone swing", "Swing en la zona", [0.45, 0.9], 0],
    fps: ["First-pitch swing", "Swing 1.er pitcheo", [0.1, 0.6], 0], chase2k: ["2-strike chase", "Fuera, 2 strikes", [0.15, 0.65], -1],
    swing: ["Swing rate", "Swings", [0.3, 0.65], 0], whiff: ["Whiffs per swing", "Swings en blanco", [0.08, 0.45], -1],
    zcontact: ["Zone contact", "Contacto en zona", [0.65, 0.98], 1], ocontact: ["Chase contact", "Contacto fuera", [0.3, 0.85], 1],
    whiff_fb: ["vs fastballs", "vs. rectas", [0.05, 0.42], -1], whiff_br: ["vs breaking", "vs. rompientes", [0.1, 0.6], -1],
    whiff_os: ["vs offspeed", "vs. cambios", [0.1, 0.6], -1], k: ["Strikeout rate", "Tasa de ponches", [0.08, 0.4], -1],
    k_vl: ["vs LHP", "vs. zurdos", [0.08, 0.4], -1], k_vr: ["vs RHP", "vs. derechos", [0.08, 0.4], -1],
    bb: ["Walk rate", "Tasa de boletos", [0.03, 0.2], 1], gb: ["Ground balls", "Rodados", [0.25, 0.65], 0],
    pullair: ["Pulled in the air", "Haladas al aire", [0.05, 0.32], 0], oppo: ["Opposite field", "Banda contraria", [0.1, 0.42], 0],
    hardhit: ["Hard-hit, 95+", "Batazos duros", [0.2, 0.6], 1], barrel: ["Barrels", "Macetazos", [0, 0.2], 1],
    avg: ["AVG", "Promedio", [0.15, 0.35], 1, "avg"], obp: ["OBP", "OBP", [0.25, 0.45], 1, "avg"], babip: ["BABIP", "BABIP", [0.2, 0.4], 1, "avg"],
    avg_vl: ["AVG vs LHP", "Promedio vs. zurdos", [0.15, 0.35], 1, "avg"], avg_vr: ["AVG vs RHP", "Promedio vs. derechos", [0.15, 0.35], 1, "avg"],
    whiff_up: ["Whiffs, top half", "En blanco, arriba", [0.08, 0.45], -1], whiff_down: ["Whiffs, bottom half", "En blanco, abajo", [0.08, 0.45], -1],
    whiff_in: ["Whiffs, inside half", "En blanco, adentro", [0.08, 0.45], -1], whiff_away: ["Whiffs, outside half", "En blanco, afuera", [0.08, 0.45], -1],
  };
  const GROUPS = [["approach", ["chase", "zswing", "fps", "chase2k"]], ["contact", ["whiff", "zcontact", "whiff_fb", "whiff_br", "whiff_os"]],
    ["outcomes", ["k", "k_vl", "k_vr", "bb"]], ["batted", ["gb", "pullair", "oppo", "hardhit", "barrel"]]];
  const w = () => W[state.lang];
  const label = key => (MET[key] ? MET[key][state.lang === "es" ? 1 : 0] : key);
  const isAvg = key => MET[key] && MET[key][4] === "avg";
  const fmt = (key, v) => (v == null ? "–" : isAvg(key) ? v.toFixed(3).replace(/^0/, "") : Math.round(100 * v) + "%");
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const tier = t => (t >= 0.6 ? "high" : t >= 0.35 ? "med" : "low");
  const MONTHS = { en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    es: ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sep.", "oct.", "nov.", "dic."] };
  const d0 = s => { const [y, m, d] = s.split("-").map(Number); return { y, m, d }; };
  const day = s => { const x = d0(s); return state.lang === "es" ? `${x.d} ${MONTHS.es[x.m - 1]}` : `${MONTHS.en[x.m - 1]} ${x.d}`; };
  const range = (a, b) => (a.slice(0, 7) === b.slice(0, 7)
    ? (state.lang === "es" ? `${d0(a).d}–${day(b)}` : `${day(a)}–${d0(b).d}`) : `${day(a)}–${day(b)}`);
  const longDay = s => {
    const x = d0(s), dt = new Date(Date.UTC(x.y, x.m - 1, x.d));
    return dt.toLocaleDateString(state.lang === "es" ? "es-US" : "en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  };

  // ------------------------------------------------------------------ tooltip
  const tip = $("#tip");
  function showTip(html, ev) {
    if (!tip) return;
    tip.innerHTML = html; tip.style.opacity = 1;
    const r = tip.getBoundingClientRect();
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => { if (tip) tip.style.opacity = 0; };

  function svg(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function text(parent, x, y, s, attrs = {}) { const t = svg("text", { x, y, ...attrs }, parent); t.textContent = s; return t; }
  const logScale = (lo, hi, a, b) => v => a + (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * (b - a);
  const linScale = (lo, hi, a, b) => v => a + (v - lo) / (hi - lo) * (b - a);

  // ------------------------------------------------------------------ theme + decoration
  function initTheme() {
    const b = $("#theme");
    if (!b) return;
    b.addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("sdf-theme", next); } catch (e) { /* storage blocked */ }
      redrawCharts();
    });
  }
  function isobaths() {
    const s = $("#isobaths");
    if (!s) return;
    const W0 = 1200, H0 = 520;
    s.setAttribute("viewBox", `0 0 ${W0} ${H0}`);
    for (let i = 0; i < 9; i++) {
      const base = 60 + i * 52, amp = 18 + 6 * Math.sin(i * 1.7), ph = i * 0.9;
      let d = "";
      for (let x = 0; x <= W0; x += 20) {
        const y = base + amp * Math.sin(x / 170 + ph) + 9 * Math.sin(x / 61 + ph * 2.3);
        d += (x ? " L " : "M ") + x + " " + y.toFixed(1);
      }
      svg("path", { d, fill: "none", stroke: "var(--shoal-2)", "stroke-width": i % 3 === 0 ? 1.4 : 0.8,
        "stroke-dasharray": i % 3 === 0 ? "none" : "3 6", opacity: 0.55 }, s);
    }
  }

  // ------------------------------------------------------------------ data
  async function getJSON(url) { const r = await fetch(url, { cache: "no-cache" }); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }
  async function index(team) { return INDEX[team] || (INDEX[team] = await getJSON(`data/packets/${team}/index.json`)); }
  async function packet(team, start) {
    const k = team + start;
    return PACKETS[k] || (PACKETS[k] = await getJSON(`data/packets/${team}/${start}.json`));
  }

  // ------------------------------------------------------------------ hitter card
  const pos = (v, dom) => Math.max(0, Math.min(100, 100 * (v - dom[0]) / (dom[1] - dom[0])));
  function row(key, m, verify) {
    if (!m || m.v == null) return "";
    const dom = MET[key][2], pol = MET[key][3];
    const t = tier(m.t);
    const dir = m.v - m.mu;
    const cls = pol === 0 || Math.abs(dir) < 0.004 ? "neu" : (pol * dir < 0 ? "opp" : "dan");
    let inner = `<i class="band" style="left:${pos(m.lo, dom)}%;width:${Math.max(1.5, pos(m.hi, dom) - pos(m.lo, dom))}%"></i>`;
    if (verify && m.n_in > 0 && m.plo != null) {
      inner += `<i class="band pred" style="left:${pos(m.plo, dom)}%;width:${Math.max(1.5, pos(m.phi, dom) - pos(m.plo, dom))}%"></i>`;
    }
    inner += `<i class="lg" style="left:${pos(m.mu, dom)}%"></i><i class="dot ${cls}" style="left:${pos(m.v, dom)}%"></i>`;
    if (verify && m.n_in > 0) inner += `<i class="act ${m.in80 ? "in" : ""}" style="left:${pos(m.k_in / m.n_in, dom)}%"></i>`;
    const full = { whiff_fb: ["Whiffs per swing, fastballs", "Swings en blanco, rectas"], whiff_br: ["Whiffs per swing, breaking balls", "Swings en blanco, rompientes"],
      whiff_os: ["Whiffs per swing, offspeed", "Swings en blanco, cambios"], k_vl: ["Strikeout rate vs LHP", "Ponches vs. zurdos"],
      k_vr: ["Strikeout rate vs RHP", "Ponches vs. derechos"] }[key];
    const tipTxt = [`<b>${esc(full ? full[state.lang === "es" ? 1 : 0] : label(key))}</b>`, `${state.lang === "es" ? "Pronóstico" : "Forecast"} ${fmt(key, m.v)} (${fmt(key, m.lo)}–${fmt(key, m.hi)})`,
      `${w().lg} ${fmt(key, m.mu)}`, `${state.lang === "es" ? "Sin ajustar" : "Raw season"} ${fmt(key, m.raw)} (n=${m.n})`,
      `${w().trust} ${Math.round(100 * m.t)}%`];
    if (verify && m.n_in > 0) tipTxt.push(`${w().inSeries}: ${m.k_in}/${m.n_in} = ${fmt(key, m.k_in / m.n_in)} ${m.in80 ? "✓" : "✗"}`);
    const sub = ["whiff_fb", "whiff_br", "whiff_os", "k_vl", "k_vr"].includes(key) ? " sub" : "";
    return `<div class="row t-${t}${sub}" data-tip="${esc(tipTxt.join("<br>"))}"><span class="lab">${esc(label(key))}</span>` +
      `<span class="val">${fmt(key, m.v)}</span><span class="trk">${inner}</span></div>`;
  }
  const PENNANT = `<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M1.5 1v10.5" stroke="var(--ink-2)" stroke-width="1.4"/><path d="M2.2 1.4 11 4.6 2.2 7.8Z" fill="var(--pennant)"/></svg>`;
  const BUOY = `<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.2" fill="none" stroke="var(--sea)" stroke-width="2"/></svg>`;
  function zoneSvg(h) {
    const m = h.m, lr = h.bats === "L";
    const cell = (key, x, y, wd, ht, tx, ty) => {
      const v = m[key];
      if (!v) return "";
      const dev = v.v - v.mu;
      const a = Math.min(0.85, Math.abs(dev) / 0.12) * (v.t >= 0.35 ? 1 : 0.45);
      const col = dev > 0 ? "var(--sea)" : "var(--pennant)";
      return `<rect x="${x}" y="${y}" width="${wd}" height="${ht}" fill="${col}" fill-opacity="${a.toFixed(2)}"></rect>` +
        `<text x="${tx}" y="${ty}" text-anchor="middle" style="opacity:${v.t >= 0.35 ? 1 : 0.55}">${fmt(key, v.v)}</text>`;
    };
    const inX = lr ? 80 : 8, awayX = lr ? 8 : 80;
    return `<svg class="zone-svg" viewBox="0 0 112 92" width="100%" aria-hidden="true">
      <rect x="8" y="6" width="96" height="80" fill="none" stroke="var(--rule-2)"></rect>
      ${cell("whiff_up", 8, 6, 96, 22, 56, 21)}${cell("whiff_down", 8, 64, 96, 22, 56, 79)}
      ${cell("whiff_in", inX, 28, 24, 36, inX + 12, 50)}${cell("whiff_away", awayX, 28, 24, 36, awayX + 12, 50)}
      <text x="56" y="49" text-anchor="middle" style="fill:var(--ink-3);font-size:8px">${h.bats === "S" ? esc(w().in_) + " ↔" : esc(w().in_) + " " + (lr ? "→" : "←")}</text>
    </svg>`;
  }
  function spraySvg(h) {
    if (!h.spray) return "";
    const tot = h.spray.reduce((a, s) => a + s.gb + s.air, 0);
    if (!tot) return "";
    const lr = h.bats === "L";
    const cx = 66, cy = 86, R = 52;
    let out = `<svg viewBox="0 0 132 96" width="100%" aria-hidden="true">`;
    for (let i = 0; i < 5; i++) {
      const s = h.spray[lr ? 4 - i : i];
      const a0 = (-135 + i * 18) * Math.PI / 180, a1 = (-135 + (i + 1) * 18) * Math.PI / 180;
      const share = (s.gb + s.air) / tot, rr = 14 + R * Math.min(1, Math.sqrt(share / 0.4));
      const air = (s.air) / Math.max(1, s.gb + s.air);
      const pt = (a, r) => `${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * Math.sin(a)).toFixed(1)}`;
      out += `<path d="M ${cx} ${cy} L ${pt(a0, rr)} A ${rr} ${rr} 0 0 1 ${pt(a1, rr)} Z" fill="var(--shoal-2)" stroke="var(--card)" stroke-width="1.5"></path>`;
      const ra = 14 + (rr - 14) * air;
      out += `<path d="M ${cx} ${cy} L ${pt(a0, ra)} A ${ra} ${ra} 0 0 1 ${pt(a1, ra)} Z" fill="var(--ink-2)" fill-opacity="0.55"></path>`;
      const am = (a0 + a1) / 2;
      out += `<text x="${(cx + (rr + 7) * Math.cos(am)).toFixed(1)}" y="${(cy + (rr + 7) * Math.sin(am) + 3).toFixed(1)}" text-anchor="middle">${Math.round(100 * share)}</text>`;
    }
    out += `<text x="${lr ? 128 : 4}" y="94" text-anchor="${lr ? "end" : "start"}" style="fill:var(--ink-3);font-size:8px">${esc(w().pull)}</text>`;
    out += `<text x="${lr ? 4 : 128}" y="94" text-anchor="${lr ? "start" : "end"}" style="fill:var(--ink-3);font-size:8px">${esc(w().oppo)}</text></svg>`;
    return out;
  }
  function hitterCard(h, p) {
    const L = w(), verify = state.view === "wh";
    const lvl = L.level[p.level];
    const trustAll = h.m.k ? h.m.k.t : 0;
    const bars = [0.2, 0.4, 0.6, 0.8].map(x => `<i class="${trustAll >= x ? "on" : ""}"></i>`).join("");
    const three = h.three.length ? h.three.map(t => {
      const pol = MET[t.key] ? MET[t.key][3] : 0;
      const good4p = (pol === -1 && t.side === "high") || (pol === 1 && t.side === "low") || t.key === "zcontact" && t.side === "low";
      return `<li>${good4p ? BUOY : PENNANT}<span>${esc(t[state.lang])}</span></li>`;
    }).join("") : `<li class="none">${esc(L.none)}</li>`;
    let body = "";
    for (const [g, keys] of GROUPS) {
      body += `<div class="grp"><span>${esc(L[g])}</span>${g === "approach" ? `<span>${esc(L.range)}</span>` : "<span></span>"}</div>`;
      body += keys.map(k => row(k, h.m[k], verify)).join("");
    }
    const std = ["avg", "obp", "babip"].filter(k => h.m[k]);
    const stdT = std.length ? Math.max(...std.map(k => h.m[k].t)) : 0;
    const stdLine = std.length ? `<div class="std"><b>${esc(L.std)}:</b> ${std.map(k => `${esc(label(k))} ${fmt(k, h.m[k].raw)}`).join(" · ")}` +
      ` — ${esc(L.trust).toLowerCase()} ${Math.round(100 * stdT)}%, ${esc(stdT >= 0.6 ? L.trustHigh : stdT >= 0.35 ? L.trustMed : L.trustLow)}.</div>` : "";
    let ver = "";
    if (verify) {
      const ms = Object.entries(h.m).filter(([k, m]) => m.n_in > 0 && MET[k] && MET[k][4] !== "avg");
      const inside = ms.filter(([, m]) => m.in80).length;
      ver = h.played ? `<div class="verify-line"><span>${esc(L.inSeries)}: ${h.m.k ? h.m.k.n_in : 0} ${state.lang === "es" ? "AP" : "PA"}</span><span><b>${inside}/${ms.length}</b> ${esc(L.inside)}</span></div>`
        : `<div class="verify-line"><span>${esc(L.didnt)}</span></div>`;
    }
    return `<article class="hcard">
      ${verify && !h.played ? `<span class="played-no">${esc(L.didnt)}</span>` : ""}
      <div class="hd"><span class="num">${h.num ? "#" + esc(h.num) : ""}</span><span class="nm">${esc(h.name)}</span>
        <span class="meta">${esc(h.pos)} · ${esc(BATS[state.lang][h.bats] || h.bats || "")} · ${h.age || ""}</span>
        <span class="sub-meta"><span>${h.pa} ${esc(L.pa)} ${esc(lvl)}</span><span class="conf" title="${esc(L.trust)}">${bars}</span></span></div>
      <ul class="three">${three}</ul>
      ${h.pa ? body : ""}
      ${h.pa ? `<div class="mini"><div><div class="cap">${esc(L.zone)}</div>${zoneSvg(h)}</div><div><div class="cap">${esc(L.spray)}</div>${spraySvg(h)}</div></div>` : ""}
      ${h.pa ? stdLine : ""}${ver}
    </article>`;
  }

  // ------------------------------------------------------------------ lineup at a glance
  const GLANCE = ["chase", "fps", "whiff", "zcontact", "k", "bb", "gb", "pullair", "hardhit", "barrel"];
  const GLANCE_HEAD = { en: ["Chase", "1st sw.", "Whiff", "Z-con", "K%", "BB%", "GB%", "Pull-air", "Hard", "Barrel"],
    es: ["Fuera", "1.er sw.", "Blanco", "Con. z.", "K%", "BB%", "Rod.", "Hal. aire", "Duros", "Mac."] };
  function glanceTable(p) {
    const L = w();
    const rows = p.hitters.filter(h => h.pa > 0).map(h => {
      const cells = GLANCE.map(k => {
        const m = h.m[k];
        if (!m || m.v == null) return "<td>–</td>";
        const pol = MET[k][3], t = tier(m.t);
        let cls = `t-${t}`;
        if (pol !== 0 && m.pct != null && m.t >= 0.35 && (m.pct >= 0.8 || m.pct <= 0.2)) {
          const high = m.pct >= 0.8;
          cls += (pol === -1) === high ? " opp" : " dan";
        }
        return `<td class="${cls}">${fmt(k, m.v)}</td>`;
      }).join("");
      return `<tr><td class="gn">${h.num ? "#" + esc(h.num) : ""}</td><td class="gname">${esc(h.name)}</td><td>${esc(BATS[state.lang][h.bats] || "")}</td><td>${h.pa}</td>${cells}</tr>`;
    }).join("");
    const cap = state.lang === "es"
      ? "Pronósticos para la serie. Azul: ventaja para nuestro lanzador. Rojo: ventaja para el bateador (solo números confiables en el 20% superior o inferior). Tinta tenue: casi todo promedio de la liga."
      : "Forecasts for the series. Blue: an edge for our pitcher. Red: an edge for the hitter (only trustworthy numbers in the top or bottom fifth). Faint ink: mostly league average.";
    return `<div class="glance-wrap"><div class="grp" style="margin:0 0 4px"><span>${state.lang === "es" ? "La alineación de un vistazo" : "Lineup at a glance"}</span><span></span></div>
      <div class="scroll"><table class="glance"><thead><tr><th></th><th>${state.lang === "es" ? "Bateador" : "Hitter"}</th><th>B</th><th>${state.lang === "es" ? "AP" : "PA"}</th>
      ${GLANCE_HEAD[state.lang].map(x => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>
      <div class="hint" style="margin-top:4px">${esc(cap)}</div></div>`;
  }

  // ------------------------------------------------------------------ pitcher card
  function pitcherCard(x, p) {
    const L = w(), verify = state.view === "wh";
    const hand = x.throws === "L" ? (state.lang === "es" ? "Zurdo" : "LHP") : (state.lang === "es" ? "Derecho" : "RHP");
    if (x.no_data) {
      return `<article class="pcard"><div class="hd"><span class="num">${x.num ? "#" + esc(x.num) : ""}</span><span class="nm">${esc(x.name)}</span>
        <span class="meta">${hand}${x.age ? " · " + x.age : ""}</span></div><p class="hint">${esc(L.noData)}</p></article>`;
    }
    const rows = x.arsenal.map(a => `<tr><td>${esc(a[state.lang] || a.pt)}</td>
      <td>${Math.round(100 * a.use)}%<span class="usebar" style="width:${Math.round(40 * a.use)}px"></span></td>
      <td>${Math.round(100 * a.use_l)}%</td><td>${Math.round(100 * a.use_r)}%</td><td>${a.velo ?? "–"}</td>
      <td>${a.ivb ?? "–"}</td><td>${a.hb ?? "–"}</td><td>${a.whiff == null ? "–" : Math.round(100 * a.whiff) + "%"}</td>
      <td>${Math.round(100 * a.use_fp)}%</td><td>${Math.round(100 * a.use_2k)}%</td></tr>`).join("");
    const start = new Date(p.start + "T12:00:00Z");
    const days = [];
    for (let i = 7; i >= 1; i--) {
      const d = new Date(start.getTime() - i * 864e5).toISOString().slice(0, 10);
      const r = (x.recent || []).find(r => r.d === d);
      days.push(r ? r.p : 0);
    }
    const rec = days.map(v => `<span class="${v ? "" : "zero"}" style="height:${Math.min(22, 2 + v / 5)}px" title="${v}"></span>`).join("");
    const ver = verify ? `<div class="verify-line"><span>${esc(L.inSeries)}: ${x.verify && x.verify.games ? `${x.verify.games} ${esc(L.games)}, ${x.verify.pitches} ${esc(L.pitches)}` : esc(L.didnt)}</span></div>` : "";
    return `<article class="pcard">
      <div class="hd"><span class="num">${x.num ? "#" + esc(x.num) : ""}</span><span class="nm">${esc(x.name)}</span>
        <span class="meta">${hand} · ${x.age || ""}<span class="role">${esc(x.role === "SP" ? L.sp : L.rp)}</span></span>
        <span class="sub-meta"><span>${x.games} ${L.gp} · ${x.starts} ${L.gs} · ${x.pitches_total} ${esc(L.pitches)}${x.arm != null ? ` · ${esc(L.arm)} ${x.arm}°` : ""}${x.ext != null ? ` · ${esc(L.ext)} ${x.ext} ft` : ""}</span></span></div>
      <div class="scroll"><table><thead><tr><th>${esc(L.pitch)}</th><th>${esc(L.use)}</th><th>${esc(L.vl)}</th><th>${esc(L.vr)}</th><th>mph</th>
        <th>IVB</th><th>HB</th><th>${esc(L.whiff)}</th><th>${esc(L.first)}</th><th>${esc(L.twok)}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="grp" style="margin-top:8px"><span>${esc(L.last7)}</span><span>${days.reduce((a, b) => a + b, 0)}</span></div>
      <div class="recent">${rec}</div>${ver}
    </article>`;
  }

  // ------------------------------------------------------------------ packet view
  function discussion(p) {
    const L = w();
    const where = p.home ? `${p.opp} ${L.at} ${p.team_name}` : `${p.team_name} ${L.at} ${p.opp}`;
    const lines = (p.discussion[state.lang] || []).map(s => `<li>${esc(s)}</li>`).join("");
    let ver = "";
    if (state.view === "wh") {
      let n = 0, inside = 0;
      for (const h of p.hitters) for (const [k, m] of Object.entries(h.m)) {
        if (m.n_in > 0 && MET[k] && MET[k][4] !== "avg") { n++; if (m.in80) inside++; }
      }
      ver = `<div class="verify-sum"><span>${esc(L.result)}: <b style="color:var(--ink)">${p.wins}–${p.losses}</b> (${esc(p.team_name)})</span>
        <span><b>${n ? Math.round(100 * inside / n) : 0}%</b> ${esc(L.verified)}</span></div>`;
    }
    return `<div class="discussion"><div class="hd"><b>${esc(L.disc)}</b> · ${esc(where)}<br>${esc(L.issued)} ${esc(longDay(p.monday))} ·
      ${esc(L.series)} ${esc(range(p.start, p.end))} · ${p.n_games} ${esc(L.games)}</div><ul>${lines}</ul>${ver}</div>`;
  }
  function startsStrip(p) {
    const L = w();
    const verify = state.view === "wh";
    const list = verify ? p.actual_starters.map(a => ({ name: a.name, d: `G${a.game}`, note: a.on_roster ? "" : L.notOnRoster }))
      : (p.recent_starts || []).map(s => ({ name: s.name, d: day(s.d), note: s.on_roster ? "" : L.notOnRoster }));
    const items = list.slice(-8).map(s => `<div><div class="d">${esc(s.d)}</div><div class="p">${esc(s.name || "–")}</div>${s.note ? `<div class="a">${esc(s.note)}</div>` : ""}</div>`).join("");
    return `<div class="grp" style="margin:0 0 6px"><span>${esc(verify ? L.actual : L.starts)}</span><span></span></div>
      <div class="rotation" style="grid-template-columns:repeat(${Math.max(1, Math.min(8, list.length))}, minmax(0,1fr))">${items}</div>`;
  }
  async function renderPacket() {
    const box = $("#hitters");
    if (!box) return;
    const idx = await index(state.team);
    if (!state.start || !idx.series.some(s => s.start === state.start)) state.start = idx.series[idx.series.length - 1].start;
    const sel = $("#series");
    sel.innerHTML = idx.series.map(s => `<option value="${s.start}" ${s.start === state.start ? "selected" : ""}>` +
      `${esc(range(s.start, s.end))} · ${s.home ? (state.lang === "es" ? "vs." : "vs.") : (state.lang === "es" ? "en" : "at")} ${esc(s.opp)} (${s.wins}–${s.losses})</option>`).join("");
    const p = await packet(state.team, state.start);
    const L = w();
    $("#disc").innerHTML = discussion(p) + glanceTable(p);
    $("#hitters-h").textContent = L.hitters;
    $("#pitchers-h").textContent = L.pitchers;
    $("#hitters-n").textContent = `${p.hitters.length} · ${state.lang === "es" ? "roster activo del lunes" : "Monday's active roster"}`;
    $("#pitchers-n").textContent = `${p.pitchers.length}`;
    const allH = state.allHitters || p.hitters.length <= 6;
    box.innerHTML = p.hitters.slice(0, allH ? 99 : 6).map(h => hitterCard(h, p)).join("") +
      (allH ? "" : `<button class="btn more" type="button" data-more="hitters">${state.lang === "es" ? "Ver los" : "Show all"} ${p.hitters.length} ${state.lang === "es" ? "bateadores" : "hitters"}</button>`);
    $("#starts").innerHTML = startsStrip(p);
    const ps = p.pitchers.filter(x => !x.no_data);
    const keyP = ps.filter(x => x.role === "SP").concat(ps.filter(x => x.role !== "SP").slice(0, 4));
    const allP = state.allPitchers || p.pitchers.length <= keyP.length;
    const shown = allP ? p.pitchers : keyP;
    $("#pitchers").innerHTML = shown.map(x => pitcherCard(x, p)).join("") +
      (allP ? "" : `<button class="btn more" type="button" data-more="pitchers">${state.lang === "es" ? "Ver los" : "Show all"} ${p.pitchers.length} ${state.lang === "es" ? "lanzadores" : "pitchers"}</button>`);
    $("#print").href = `packet.html?team=${state.team}&start=${state.start}&lang=${state.lang}${state.view === "wh" ? "&view=wh" : ""}`;
  }
  function bindRowTips(root) {
    root.addEventListener("mousemove", ev => {
      const r = ev.target.closest("[data-tip]");
      if (r) showTip(r.dataset.tip, ev); else hideTip();
    });
    root.addEventListener("mouseleave", hideTip);
  }
  function seg(id, key, after) {
    const el = $("#" + id);
    if (!el) return;
    el.addEventListener("click", ev => {
      const b = ev.target.closest("button");
      if (!b) return;
      state[key] = b.dataset.v;
      for (const x of el.querySelectorAll("button")) x.setAttribute("aria-pressed", x === b ? "true" : "false");
      after();
    });
  }

  // ------------------------------------------------------------------ charts
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  function sized(el, h) {
    const wd = Math.max(300, el.parentElement.clientWidth - 2);
    el.setAttribute("viewBox", `0 0 ${wd} ${h}`);
    el.innerHTML = "";
    return wd;
  }
  function ratioChart() {
    const el = $("#ratio");
    if (!el || !RESEARCH) return;
    const lv = state.ratioWho === "fsl" ? "FSL" : "AAA";
    const rows = [];
    const ms = Object.fromEntries(RESEARCH.levels[lv].metrics.map(m => [m.key, m]));
    for (const f of RESEARCH.families) {
      rows.push({ head: f.en });
      for (const k of f.metrics) if (ms[k]) rows.push({ m: ms[k] });
    }
    const rh = 21, top = 26, H = top + rows.length * rh + 10;
    const Wd = sized(el, H);
    const left = Math.min(190, Wd * 0.36), right = Wd - 16;
    const lo = 0.2, hi = 24, X = logScale(lo, hi, left, right);
    const g = svg("g", { class: "grid" }, el);
    for (const v of [0.25, 0.5, 1, 2, 4, 8, 16]) {
      svg("line", { x1: X(v), x2: X(v), y1: top - 6, y2: H - 6 }, g);
      text(el, X(v), top - 12, v === 1 ? "1× league avg" : v + "×", { "text-anchor": "middle", class: "axis", style: `font-weight:${v === 1 ? 700 : 400}` });
    }
    svg("line", { class: "ref", x1: X(1), x2: X(1), y1: top - 6, y2: H - 6 }, el);
    const cols = { season: css("--pennant"), last14: css("--violet"), sdf: css("--sea") };
    rows.forEach((r, i) => {
      const y = top + i * rh + rh / 2;
      if (r.head) { text(el, 4, y + 4, r.head.toUpperCase(), { style: "font-family:var(--mono);font-size:10px;letter-spacing:.08em;fill:var(--ink-3)" }); return; }
      const m = r.m;
      text(el, 14, y + 4, m.en, { style: "font-size:12px" });
      if (!m.measurable) { text(el, X(1) + 8, y + 4, "no measurable spread between hitters in a series", { style: "font-size:11px;fill:var(--ink-3);font-style:italic" }); return; }
      const vals = state.ratioWho === "reg" ? { season: { ratio: m.reg.season }, last14: { ratio: m.reg.last14 }, sdf: { ratio: m.reg.sdf } }
        : { season: m.season, last14: m.last14, sdf: m.sdf };
      const offs = { season: -5, last14: 0, sdf: 5 };
      for (const k of ["last14", "season", "sdf"]) {
        const v = vals[k];
        if (!v || v.ratio == null) continue;
        const yy = y + offs[k];
        if (v.lo != null && v.hi != null && state.ratioWho !== "reg") {
          svg("line", { x1: X(Math.max(lo, v.lo)), x2: X(Math.min(hi, v.hi)), y1: yy, y2: yy, stroke: cols[k], "stroke-width": 2, opacity: 0.55 }, el);
        }
        const cx = X(Math.max(lo, Math.min(hi, v.ratio)));
        svg("circle", { cx, cy: yy, r: 4.5, fill: cols[k], stroke: css("--card"), "stroke-width": 1.5 }, el);
        if (v.ratio > hi) text(el, cx - 6, yy - 6, "→" + v.ratio.toFixed(0) + "×", { "text-anchor": "end", style: "font-size:10px" });
      }
      const hit = svg("rect", { x: 0, y: y - rh / 2, width: Wd, height: rh, class: "hit" }, el);
      const f = v => (v == null ? "–" : v.toFixed(2) + "×");
      hit.addEventListener("mousemove", ev => showTip(`<b>${esc(m.en)}</b>` +
        `<div class="r"><span><i style="background:${cols.season}"></i>Season line</span><span>${f(vals.season.ratio)}</span></div>` +
        `<div class="r"><span><i style="background:${cols.last14}"></i>Last 14 days</span><span>${f(vals.last14.ratio)}</span></div>` +
        `<div class="r"><span><i style="background:${cols.sdf}"></i>Six-Day Forecast</span><span>${f(vals.sdf.ratio)}</span></div>` +
        (state.ratioWho === "reg" ? "" : `<div class="r"><span>Hitter-series</span><span>${m.obs.toLocaleString()}</span></div>`) +
        `<div class="r"><span>Stabilization M</span><span>${m.M_stab[String(RESEARCH.levels[lv].test)] ? Math.round(m.M_stab[String(RESEARCH.levels[lv].test)]) : "–"}</span></div>`, ev));
      hit.addEventListener("mouseleave", hideTip);
    });
    const t = $("#ratio-table");
    if (t) {
      t.innerHTML = `<table class="data"><thead><tr><th>Number</th><th>Season line</th><th>Last 14</th><th>Six-Day Forecast</th><th>Hitter-series</th></tr></thead><tbody>` +
        rows.filter(r => r.m).map(({ m }) => {
          const v = state.ratioWho === "reg" ? [m.reg.season, m.reg.last14, m.reg.sdf] : [m.season.ratio, m.last14.ratio, m.sdf.ratio];
          return `<tr><td>${esc(m.en)}</td>${m.measurable ? v.map(x => `<td>${x == null ? "–" : x.toFixed(2) + "×"}</td>`).join("") : `<td colspan="3">not measurable</td>`}<td>${(state.ratioWho === "reg" ? m.reg.obs : m.obs).toLocaleString()}</td></tr>`;
        }).join("") + `</tbody></table>`;
    }
  }
  function crossChart() {
    const el = $("#cross");
    if (!el || !RESEARCH) return;
    const c = RESEARCH.levels.AAA.crossover[state.cross];
    const H = 270, Wd = sized(el, H);
    const L = 44, R = Wd - 12, T = 12, B = H - 34;
    const X = logScale(4, 1500, L, R), Y = logScale(0.2, 14, B, T);
    const g = svg("g", { class: "grid" }, el);
    for (const v of [5, 10, 20, 50, 100, 200, 500, 1000]) { svg("line", { x1: X(v), x2: X(v), y1: T, y2: B }, g); text(el, X(v), B + 16, v, { "text-anchor": "middle", class: "axis" }); }
    for (const v of [0.25, 0.5, 1, 2, 4, 8]) { svg("line", { x1: L, x2: R, y1: Y(v), y2: Y(v) }, g); text(el, L - 6, Y(v) + 4, v + "×", { "text-anchor": "end", class: "axis" }); }
    svg("line", { class: "ref", x1: L, x2: R, y1: Y(1), y2: Y(1) }, el);
    text(el, R, Y(1) - 6, "league average", { "text-anchor": "end", class: "axis" });
    text(el, (L + R) / 2, H - 4, "chances before the series (log scale)", { "text-anchor": "middle", class: "axis" });
    if (c.M) {
      let d = "";
      for (let n = 4; n <= 1500; n *= 1.08) { const y = c.M / n; if (y > 14 || y < 0.2) continue; d += (d ? " L " : "M ") + X(n).toFixed(1) + " " + Y(y).toFixed(1); }
      svg("path", { d, fill: "none", stroke: css("--ink-3"), "stroke-width": 1.5, "stroke-dasharray": "5 5" }, el);
      svg("line", { x1: X(c.M), x2: X(c.M), y1: Y(1) - 6, y2: Y(1) + 6, stroke: css("--ink"), "stroke-width": 2 }, el);
      text(el, X(c.M) - 6, Y(1) - 8, `crossover ≈ ${Math.round(c.M)}`, { "text-anchor": "end", class: "axis", style: "font-weight:700" });
    }
    for (const [k, col] of [["season", css("--pennant")], ["sdf", css("--sea")]]) {
      const pts = c.bins.filter(b => b[k] > 0);
      svg("path", { d: pts.map((b, i) => (i ? "L" : "M") + X(b.n_mid).toFixed(1) + " " + Y(Math.min(14, Math.max(0.2, b[k]))).toFixed(1)).join(" "),
        fill: "none", stroke: col, "stroke-width": 2 }, el);
      for (const b of pts) {
        const cc = svg("circle", { cx: X(b.n_mid), cy: Y(Math.min(14, Math.max(0.2, b[k]))), r: 4.5, fill: col, stroke: css("--card"), "stroke-width": 1.5 }, el);
        cc.addEventListener("mousemove", ev => showTip(`<b>${b.lo}–${b.hi} chances before</b><br>${k === "sdf" ? "Six-Day Forecast" : "Season line"}: ${b[k].toFixed(2)}× league<br>${b.obs.toLocaleString()} hitter-series`, ev));
        cc.addEventListener("mouseleave", hideTip);
      }
    }
  }
  function calibChart() {
    const el = $("#calib");
    if (!el || !RESEARCH) return;
    const keys = ["chase", "fps", "whiff", "zcontact", "k", "bb", "gb", "hardhit", "barrel", "avg", "babip"];
    const ms = Object.fromEntries(RESEARCH.levels.AAA.metrics.map(m => [m.key, m]));
    const rh = 20, T = 22, H = T + keys.length * rh + 26, Wd = sized(el, H);
    const L = 130, R = Wd - 16, X = linScale(0.6, 0.9, L, R);
    const g = svg("g", { class: "grid" }, el);
    for (const v of [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]) { svg("line", { x1: X(v), x2: X(v), y1: T - 6, y2: H - 22 }, g); text(el, X(v), H - 8, Math.round(100 * v) + "%", { "text-anchor": "middle", class: "axis" }); }
    svg("line", { class: "ref", x1: X(0.8), x2: X(0.8), y1: T - 10, y2: H - 22 }, el);
    text(el, X(0.8), T - 12, "80% promised", { "text-anchor": "middle", class: "axis", style: "font-weight:700" });
    keys.forEach((k, i) => {
      const m = ms[k]; if (!m) return;
      const y = T + i * rh + rh / 2;
      text(el, 4, y + 4, m.en, {});
      svg("line", { x1: X(m.naive80), x2: X(m.cov80), y1: y, y2: y, stroke: css("--rule-2"), "stroke-width": 2 }, el);
      svg("circle", { cx: X(m.naive80), cy: y, r: 4.5, fill: css("--pennant") }, el);
      svg("circle", { cx: X(m.cov80), cy: y, r: 4.5, fill: css("--sea") }, el);
      const hit = svg("rect", { x: 0, y: y - rh / 2, width: Wd, height: rh, class: "hit" }, el);
      hit.addEventListener("mousemove", ev => showTip(`<b>${esc(m.en)}</b><br>Six-Day Forecast range: ${(100 * m.cov80).toFixed(1)}%<br>Season number taken as exact: ${(100 * m.naive80).toFixed(1)}%`, ev));
      hit.addEventListener("mouseleave", hideTip);
    });
  }
  function famChart() {
    const el = $("#fam");
    if (!el || !RESEARCH) return;
    const f = RESEARCH.familiarity.AAA.main.xw, rel = RESEARCH.familiarity.AAA.relievers.xw;
    const rows = [["Third time through the order, same game", f.tto3, 0], ["Second time through, same game", f.tto2, 0],
      ["Platoon advantage", f.platoon, 0], ["Faced him earlier this season", f.seen_season, 0],
      ["Faced him earlier this series", f.fam, 1], ["… relievers only", rel.fam, 1]];
    const rh = 30, T = 14, H = T + rows.length * rh + 30, Wd = sized(el, H);
    const L = Math.min(270, Wd * 0.45), R = Wd - 14, X = linScale(-10, 35, L, R);
    const g = svg("g", { class: "grid" }, el);
    for (const v of [-10, 0, 10, 20, 30]) { svg("line", { x1: X(v), x2: X(v), y1: T - 4, y2: H - 26 }, g); text(el, X(v), H - 10, (v > 0 ? "+" : "") + v, { "text-anchor": "middle", class: "axis" }); }
    svg("line", { class: "ref", x1: X(0), x2: X(0), y1: T - 4, y2: H - 26 }, el);
    rows.forEach(([name, e, q], i) => {
      const y = T + i * rh + rh / 2;
      const col = q ? css("--sea") : css("--ink-2");
      text(el, 4, y + 4, name, { style: q ? "font-weight:700" : "" });
      svg("line", { x1: X(1000 * e.lo), x2: X(1000 * e.hi), y1: y, y2: y, stroke: col, "stroke-width": 2.5, "stroke-linecap": "round" }, el);
      svg("circle", { cx: X(1000 * e.coef), cy: y, r: 5, fill: col, stroke: css("--card"), "stroke-width": 1.5 }, el);
      text(el, X(1000 * e.hi) + 8, y + 4, (e.coef >= 0 ? "+" : "−") + Math.abs(1000 * e.coef).toFixed(1), { class: "axis", style: "font-weight:600" });
      const hit = svg("rect", { x: 0, y: y - rh / 2, width: Wd, height: rh, class: "hit" }, el);
      hit.addEventListener("mousemove", ev => showTip(`<b>${esc(name)}</b><br>${(1000 * e.coef).toFixed(1)} points (95%: ${(1000 * e.lo).toFixed(1)} to ${(1000 * e.hi).toFixed(1)})`, ev));
      hit.addEventListener("mouseleave", hideTip);
    });
    text(el, (L + R) / 2, H - 0, "", {});
  }
  function weeksChart() {
    const el = $("#weeks");
    if (!el || !DEVELOP) return;
    const wk = DEVELOP.weeks, gp = (rows, g) => rows.find(r => Math.abs(r.gap - g) < 1e-9);
    const P = wk.pitchers, Hh = wk.hitters, spw = P.velo.starts_per_week;
    const rows = [
      ["Fastball velocity, 1 mph", gp(P.velo.by_gap, 1).weeks, 0], ["Fastball velocity, 0.5 mph", gp(P.velo.by_gap, 0.5).weeks, 0],
      ["Fastball carry, 2 in", gp(P.ivb.by_gap, 2).weeks, 0], ["Arm angle, 3°", gp(P.arm_angle.by_gap, 3).weeks, 0],
      ["Chase rate, 5 points", gp(Hh.chase.by_gap, 0.05).weeks, 1], ["Whiffs per swing, 5 points", gp(Hh.whiff.by_gap, 0.05).weeks, 1],
      ["Zone contact, 5 points", gp(Hh.zcontact.by_gap, 0.05).weeks, 1], ["Strikeout rate, 5 points", gp(Hh.k.by_gap, 0.05).weeks, 1],
      ["Chase rate, 3 points", gp(Hh.chase.by_gap, 0.03).weeks, 1], ["Hard-hit rate, 5 points", gp(Hh.hardhit.by_gap, 0.05).weeks, 1],
    ].sort((a, b) => a[1] - b[1]);
    const rh = 24, T = 18, H = T + rows.length * rh + 28, Wd = sized(el, H);
    const L = Math.min(220, Wd * 0.4), R = Wd - 40, X = linScale(0, 26, L, R);
    const g = svg("g", { class: "grid" }, el);
    for (const v of [0, 4, 8, 12, 16, 20, 24]) { svg("line", { x1: X(v), x2: X(v), y1: T - 6, y2: H - 24 }, g); text(el, X(v), H - 8, v, { "text-anchor": "middle", class: "axis" }); }
    svg("line", { x1: X(25), x2: X(25), y1: T - 10, y2: H - 24, stroke: css("--ink"), "stroke-width": 1.25, "stroke-dasharray": "4 4" }, el);
    text(el, X(25), T - 10, "a Triple-A season", { "text-anchor": "end", class: "axis", style: "font-weight:700" });
    rows.forEach(([name, weeks, hit], i) => {
      const y = T + i * rh + rh / 2;
      const col = hit ? css("--pennant") : css("--sea");
      text(el, 4, y + 4, name, {});
      const x1 = X(Math.min(26, weeks));
      svg("rect", { x: L, y: y - 6, width: Math.max(2, x1 - L), height: 12, rx: 2, fill: col }, el);
      text(el, x1 + 6, y + 4, weeks < 1 ? "<1 wk" : weeks.toFixed(weeks < 10 ? 1 : 0) + " wk", { class: "axis", style: "font-weight:600" });
    });
    void spw;
  }
  function stabTable() {
    const t = $("#stab-table");
    if (!t || !RESEARCH) return;
    const ms = RESEARCH.levels.AAA.metrics.filter(m => m.card && !["k_vl", "k_vr", "avg_vl", "avg_vr", "whiff_up", "whiff_down", "whiff_in", "whiff_away", "whiff_fb", "whiff_br", "whiff_os"].includes(m.key));
    const unit = { swing: "pitches", chase: "pitches out of zone", zswing: "pitches in zone", fps: "first pitches", chase2k: "2-strike pitches out of zone",
      whiff: "swings", zcontact: "swings in zone", ocontact: "swings out of zone", k: "PA", bb: "PA", avg: "AB", obp: "PA", babip: "balls in play",
      gb: "balls in play", pull: "balls in play", oppo: "balls in play", pullair: "balls in play", hardhit: "balls in play", barrel: "balls in play" };
    t.innerHTML = `<thead><tr><th>Number (Triple-A)</th><th>League rate</th><th>M, 2025</th><th>M, 2026</th><th>Counted in</th></tr></thead><tbody>` +
      ms.map(m => `<tr><td>${esc(m.en)}</td><td>${fmt(m.key, m.mu)}</td><td>${m.M_stab["2025"] ? Math.round(m.M_stab["2025"]) : "–"}</td>` +
        `<td>${m.M_stab["2026"] ? Math.round(m.M_stab["2026"]) : "–"}</td><td>${unit[m.key] || ""}</td></tr>`).join("") + `</tbody>`;
  }

  // ------------------------------------------------------------------ development
  const NICE = { velo: "velocity", ivb: "carry (induced vertical break)", hb: "horizontal movement", spin: "spin", arm_angle: "arm angle",
    ext: "extension", use: "usage", new: "new pitch", dropped: "dropped pitch" };
  const PT = { FF: "four-seamer", SI: "sinker", FC: "cutter", SL: "slider", ST: "sweeper", CU: "curveball", KC: "knuckle curve", CH: "changeup",
    FS: "splitter", SV: "slurve", ALL: "every pitch" };
  const TEAM = { AAA: "Jacksonville", FSL: "Jupiter" };
  function devWhat(x) {
    const u = x.unit === "share" ? "%" : x.unit === "deg" ? "°" : " " + x.unit;
    const f = v => x.unit === "share" ? Math.round(100 * v) : x.unit === "rpm" ? Math.round(v) : (+v).toFixed(1);
    if (x.kind === "new") return `Added a ${PT[x.pitch_type] || x.pitch_type}: ${f(x.after)}% of his pitches from ${day(x.date)}`;
    if (x.kind === "dropped") return `Shelved his ${PT[x.pitch_type] || x.pitch_type}: ${f(x.before)}% of pitches to ${f(x.after)}% from ${day(x.date)}`;
    if (x.kind === "use") { const n = PT[x.pitch_type] || x.pitch_type; return `${n[0].toUpperCase() + n.slice(1)} usage ${f(x.before)}% → ${f(x.after)}% from ${day(x.date)}`; }
    const dir = x.after > x.before ? "up" : "down";
    const what = x.pitch_type === "ALL" ? NICE[x.metric] : `${PT[x.pitch_type] || x.pitch_type} ${NICE[x.metric]}`;
    return `${what[0].toUpperCase() + what.slice(1)} ${dir}: ${f(x.before)}${u} → ${f(x.after)}${u} from ${day(x.date)}`;
  }
  function devChart(x) {
    const g = x.games || [];
    if (!g.length) return "";
    const Wd = 300, H = 92, L = 6, R = Wd - 6, T = 8, B = H - 14;
    const xs = g.map((_, i) => L + i / Math.max(1, g.length - 1) * (R - L));
    const vals = g.map(p => (x.unit === "share" ? 100 * p.x : p.x));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.15 || 1; lo -= pad; hi += pad;
    const Y = v => B - (v - lo) / (hi - lo) * (B - T);
    const cut = g.findIndex(p => p.d >= x.date);
    const b = x.unit === "share" ? 100 * x.before : x.before, a = x.unit === "share" ? 100 * x.after : x.after;
    let s = `<svg viewBox="0 0 ${Wd} ${H}" width="100%" aria-hidden="true">`;
    s += g.map((p, i) => `<circle cx="${xs[i].toFixed(1)}" cy="${Y(vals[i]).toFixed(1)}" r="2.4" fill="var(--ink-3)"></circle>`).join("");
    if (cut > 0) {
      const xc = (xs[cut - 1] + xs[cut]) / 2;
      s += `<line x1="${xc}" x2="${xc}" y1="${T - 4}" y2="${B + 2}" stroke="var(--ink)" stroke-dasharray="3 3"></line>`;
      s += `<line x1="${L}" x2="${xc}" y1="${Y(b)}" y2="${Y(b)}" stroke="var(--ink-2)" stroke-width="2.5"></line>`;
      s += `<line x1="${xc}" x2="${R}" y1="${Y(a)}" y2="${Y(a)}" stroke="var(--sea)" stroke-width="2.5"></line>`;
    }
    s += `<text x="${L}" y="${H - 2}" style="font-size:9px;fill:var(--ink-3)">${esc(day(g[0].d))}</text><text x="${R}" y="${H - 2}" text-anchor="end" style="font-size:9px;fill:var(--ink-3)">${esc(day(g[g.length - 1].d))}</text></svg>`;
    return s;
  }
  const probTxt = p => (p == null ? "–" : p > 0.999 ? ">99.9%" : p < 0.01 ? "<1%" : Math.round(100 * p) + "%");
  function devGrade(x) {
    if (x.grade === "good") return `<span class="grade good">Better since</span>`;
    if (x.grade === "bad") return `<span class="grade bad">Worse since</span>`;
    return `<span class="grade wait">Too early to tell</span>`;
  }
  function devResults(x) {
    const r = (k, n) => (n ? (100 * k / n).toFixed(1) + "%" : "–");
    const all = x.scope === "all";
    const [k1, n1] = all ? x.csw_before : x.whiff_before, [k2, n2] = all ? x.csw_after : x.whiff_after;
    const lab = all ? "Called + swinging strikes" : "Whiffs per swing";
    const p = all ? x.p_csw_better : x.p_whiff_better;
    let more = "";
    if (x.grade === "wait" && !all && x.more_swings) more = ` · about ${x.more_swings} more swings to know`;
    return `${lab}: ${r(k1, n1)} → ${r(k2, n2)} (${probTxt(p)} chance it is better${more})`;
  }
  function renderDevelop() {
    const box = $("#dev-cards");
    if (!box || !DEVELOP) return;
    const ev = DEVELOP.pitchers.filter(x => x.kind !== "relabel");
    const strong = ev.filter(x => ["arm_angle", "ext"].includes(x.metric) || (x.metric === "velo" && ["FF", "SI"].includes(x.pitch_type)) || ["new", "use"].includes(x.kind));
    const pick = [];
    for (const x of strong.filter(x => x.grade !== "wait").sort((a, b) => b.p_change - a.p_change)) { if (pick.length < 4 && !pick.some(p => p.player === x.player)) pick.push(x); }
    for (const x of strong.filter(x => x.grade === "wait").sort((a, b) => b.p_change - a.p_change)) { if (pick.length < 5 && !pick.some(p => p.player === x.player)) pick.push(x); }
    const cards = pick.map(x => `<article class="dcard panel"><div class="who"><b>${esc(x.name)}</b><span class="mono small muted">${TEAM[x.level]} · ${x.throws === "L" ? "LHP" : "RHP"}</span></div>
      <div class="what">${esc(devWhat(x))}</div>${devChart(x)}
      <div class="facts"><span>Chance the change is real: ${probTxt(x.p_change)}</span></div>
      <div class="facts"><span>${esc(devResults(x))}</span></div><div style="margin-top:8px">${devGrade(x)}</div></article>`);
    const rel = DEVELOP.pitchers.filter(x => x.kind === "relabel");
    if (rel.length) {
      const byP = {};
      for (const r of rel) (byP[r.name] = byP[r.name] || []).push(r);
      const [name, rs] = Object.entries(byP)[0];
      const pairs = rs.filter(r => r.of).map(r => `${PT[r.of] || r.of} → ${PT[r.pitch_type] || r.pitch_type}`).join(", ");
      cards.push(`<article class="dcard panel"><div class="who"><b>${esc(name)}</b><span class="mono small muted">${TEAM[rs[0].level]}</span></div>
        <div class="what">Two "new pitches" on ${esc(day(rs[0].date))} that were not new. Renamed: ${esc(pairs)}.</div>
        <p class="small" style="margin:6px 0 0">The new labels arrived the same day the old ones disappeared, at the same speed and movement. A naive tracker would have graded two pitch additions. This one calls it a relabel and grades nothing.</p>
        <div style="margin-top:8px"><span class="grade wait">Relabel, not a change</span></div></article>`);
    }
    box.innerHTML = cards.join("");
    const t = $("#dev-table");
    if (t) {
      t.innerHTML = `<table class="data"><thead><tr><th>Pitcher</th><th>Team</th><th>What changed</th><th>Chance real</th><th>Result</th><th>Grade</th></tr></thead><tbody>` +
        ev.sort((a, b) => (a.level + a.name).localeCompare(b.level + b.name)).map(x => `<tr><td>${esc(x.name)}</td><td>${TEAM[x.level]}</td><td>${esc(devWhat(x))}</td>` +
          `<td>${probTxt(x.p_change)}</td><td>${esc(devResults(x))}</td><td>${devGrade(x)}</td></tr>`).join("") + `</tbody></table>`;
    }
  }

  // ------------------------------------------------------------------ boot
  function redrawCharts() { ratioChart(); crossChart(); calibChart(); famChart(); weeksChart(); }
  async function specimen() {
    const box = $("#specimen");
    if (!box) return;
    const idx = await index("JAX");
    const p = await packet("JAX", idx.series[idx.series.length - 1].start);
    const h = p.hitters.filter(x => x.pa >= 150).sort((a, b) => b.three.length - a.three.length || b.pa - a.pa)[0];
    const keep = state.view; state.view = "fc";
    box.innerHTML = hitterCard(h, p);
    state.view = keep;
  }
  async function bootIndex() {
    initTheme(); isobaths();
    const team = $("#team");
    team.addEventListener("change", () => { state.team = team.value; state.start = null; state.allHitters = state.allPitchers = false; renderPacket(); });
    $("#series").addEventListener("change", ev => { state.start = ev.target.value; state.allHitters = state.allPitchers = false; renderPacket(); });
    seg("lang", "lang", renderPacket); seg("view", "view", renderPacket);
    seg("ratio-who", "ratioWho", ratioChart);
    $("#cross-metric").addEventListener("change", ev => { state.cross = ev.target.value; crossChart(); });
    bindRowTips($("#hitters"));
    document.addEventListener("click", ev => {
      const b = ev.target.closest("[data-more]");
      if (!b) return;
      if (b.dataset.more === "hitters") state.allHitters = true; else state.allPitchers = true;
      renderPacket();
    });
    renderPacket().catch(e => { $("#hitters").innerHTML = `<p class="loading">Could not load the packet (${esc(e.message)}).</p>`; });
    specimen().catch(() => {});
    try {
      [RESEARCH, DEVELOP] = await Promise.all([getJSON("data/research.json"), getJSON("data/develop.json")]);
      redrawCharts(); stabTable(); renderDevelop();
    } catch (e) { console.error(e); }
    let tm;
    window.addEventListener("resize", () => { clearTimeout(tm); tm = setTimeout(redrawCharts, 150); });
  }
  async function bootPrint() {
    const q = new URLSearchParams(location.search);
    state.team = q.get("team") || "JAX"; state.lang = q.get("lang") === "es" ? "es" : "en"; state.view = q.get("view") === "wh" ? "wh" : "fc";
    document.documentElement.lang = state.lang;
    const idx = await index(state.team);
    state.start = q.get("start") || idx.series[idx.series.length - 1].start;
    const p = await packet(state.team, state.start);
    const L = w();
    document.title = `${L.printTitle} · ${p.team_name} ${p.home ? "vs." : "at"} ${p.opp} · ${p.start}`;
    $("#cover").innerHTML = `<div class="product"><span>${esc(L.printTitle)}</span><span>${esc(p.team_name)}</span><span>${esc(L.level[p.level])}</span></div>
      <h1 class="ph1">${esc(p.home ? `${p.opp} ${L.at} ${p.team_name}` : `${p.team_name} ${L.at} ${p.opp}`)}</h1>${discussion(p)}${glanceTable(p)}${startsStrip(p)}
      <div class="howto print-howto">${$("#howto-src") ? $("#howto-src").innerHTML : ""}</div>`;
    $("#hitters").innerHTML = p.hitters.filter(h => h.pa > 0).map(h => hitterCard(h, p)).join("");
    $("#pitchers").innerHTML = p.pitchers.filter(x => !x.no_data).map(x => pitcherCard(x, p)).join("");
    $("#hitters-h").textContent = L.hitters;
    $("#pitchers-h").textContent = L.pitchers;
    document.body.classList.add("ready");
  }
  if (PAGE === "print") bootPrint(); else bootIndex();
})();
