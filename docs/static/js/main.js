// MAVE project page interactions.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const SVGNS = "http://www.w3.org/2000/svg";
const COL = { vanilla: "#857BDB", mave: "#C4831C" };

// ---- hero: plays once (muted), holds on the end card; ambient glow mirrors it ----
(() => {
  const v = $("#hero-video");
  if (!v) return;
  const snd = $("#hero-sound"), pp = $("#hero-pp"), rp = $("#hero-replay"), glow = $("#hero-glow");
  const hd = window.matchMedia("(min-width: 900px)").matches && (window.devicePixelRatio || 1) * window.innerWidth > 1100;
  v.src = hd ? v.dataset.srcHd : v.dataset.srcSd;
  v.muted = true;
  let userPaused = false, finished = false;

  const setPP = () => { pp.textContent = v.paused ? "▶ PLAY" : "❚❚ PAUSE"; };
  const play = () => v.play().then(setPP).catch(setPP);

  // ambient glow: draw the current frame into a tiny canvas that CSS blurs
  const ctx = glow && glow.getContext("2d");
  const paint = () => { if (ctx && v.readyState >= 2) ctx.drawImage(v, 0, 0, glow.width, glow.height); };
  if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
    const loop = () => { paint(); v.requestVideoFrameCallback(loop); };
    v.requestVideoFrameCallback(loop);
  } else {
    (function raf() { if (!v.paused) paint(); requestAnimationFrame(raf); })();
  }
  v.addEventListener("loadeddata", paint);
  v.addEventListener("seeked", paint);

  v.addEventListener("ended", () => {
    finished = true;
    // hold on the last frame (the end card)
    v.currentTime = Math.max(0, v.duration - 0.04);
    rp.hidden = false; setPP();
  });
  v.addEventListener("pause", setPP);
  v.addEventListener("play", setPP);

  // pause while scrolled away; resume on return unless finished or paused by the user
  new IntersectionObserver(([e]) => {
    if (e.isIntersecting) { if (!finished && !userPaused) play(); }
    else if (!v.paused) v.pause();
  }, { threshold: 0.35 }).observe(v);

  rp.addEventListener("click", () => { finished = false; userPaused = false; rp.hidden = true; v.currentTime = 0; play(); });
  pp.addEventListener("click", () => {
    if (v.paused) { if (finished) { finished = false; rp.hidden = true; v.currentTime = 0; } userPaused = false; play(); }
    else { userPaused = true; v.pause(); }
  });
  snd.addEventListener("click", () => {
    v.muted = !v.muted;
    snd.textContent = v.muted ? "♪ SOUND OFF" : "♪ SOUND ON";
    if (!v.muted && v.paused && !finished) { userPaused = false; play(); }
  });
})();

// ---- generic tab group: buttons[data-src] swap one <video> --------------------
function tabGroup(root) {
  const vid = $("video", root);
  const tabs = $$(".tab", root);
  const desc = $("[data-desc]", root);
  function set(t) {
    tabs.forEach((b) => { const on = b === t; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
    if (vid.getAttribute("src") !== t.dataset.src) { vid.src = t.dataset.src; vid.load(); }
    if (desc && t.dataset.text) desc.textContent = t.dataset.text;
    vid.play().catch(() => {});
  }
  tabs.forEach((t) => t.addEventListener("click", () => set(t)));
  $$("[data-act]", root).forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.act === "restart") { vid.currentTime = 0; vid.play(); }
    if (b.dataset.act === "toggle") { vid.paused ? vid.play() : vid.pause(); }
  }));
  if (tabs[0]) set(tabs.find((t) => t.classList.contains("on")) || tabs[0]);
}
$$("[data-tabs]").forEach(tabGroup);

// ---- applications: category tabs; both cases of the active type play together ---
(() => {
  const root = $("[data-apps]");
  if (!root) return;
  const cats = $$("[data-app-cats] .tab", root);
  const groups = $$("[data-app-cases]", root);
  function setCat(cat) {
    cats.forEach((b) => { const on = b.dataset.cat === cat; b.classList.toggle("on", on); b.setAttribute("aria-selected", on); });
    groups.forEach((g) => {
      const on = g.dataset.appCases === cat;
      g.hidden = !on;
      $$("video", g).forEach((v) => {
        if (on) { if (!v.getAttribute("src")) v.src = v.dataset.src; v.currentTime = 0; v.play().catch(() => {}); }
        else v.pause();
      });
    });
  }
  cats.forEach((t) => t.addEventListener("click", () => setCat(t.dataset.cat)));
  // start playing only once the section is on screen
  new IntersectionObserver((ents, obs) => {
    if (ents.some((e) => e.isIntersecting)) {
      setCat((cats.find((t) => t.classList.contains("on")) || cats[0]).dataset.cat);
      obs.disconnect();
    }
  }, { threshold: 0.15 }).observe(root);
})();

// ---- play videos only while on screen (saves bandwidth / battery) -------------
const io = new IntersectionObserver((ents) => ents.forEach((e) => {
  const v = e.target;
  if (e.isIntersecting) { if (!v.src && v.dataset.src) v.src = v.dataset.src; v.play().catch(() => {}); }
  else v.pause();
}), { threshold: 0.25 });
$$("video[data-lazy]").forEach((v) => io.observe(v));

// ---- data ---------------------------------------------------------------------
const DATA = JSON.parse($("#results-data").textContent);

// ---- tooltip --------------------------------------------------------------------
const tip = document.createElement("div"); tip.className = "tipbox"; document.body.appendChild(tip);
function showTip(e, rows) {
  tip.replaceChildren();
  rows.forEach(([key, label, value]) => {
    const row = document.createElement("div");
    if (key) { const k = document.createElement("span"); k.className = "tk"; k.style.background = key; row.appendChild(k); }
    const v = document.createElement("span"); v.className = "tv"; v.textContent = value; row.appendChild(v);
    const l = document.createElement("span"); l.style.color = "#A7AEC9"; l.textContent = "  " + label; row.appendChild(l);
    tip.appendChild(row);
  });
  tip.style.opacity = 1; moveTip(e);
}
function moveTip(e) { tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px"; }
function hideTip() { tip.style.opacity = 0; }

const el = (n, a = {}, p) => { const x = document.createElementNS(SVGNS, n); for (const k in a) x.setAttribute(k, a[k]); if (p) p.appendChild(x); return x; };
const txt = (p, x, y, s, a = {}) => { const t = el("text", { x, y, ...a }, p); t.textContent = s; return t; };

// ---- chart 1: dumbbell, vanilla -> MAVE total per agent ------------------------
(function dumbbell() {
  const host = $("#chart-total"); if (!host) return;
  const rows = DATA.recon, W = 560, padL = 150, padR = 36, rowH = 62, top = 26, H = top + rows.length * rowH + 30;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "MAVEBench total score, vanilla vs MAVE, per agent" }, host);
  const x = (v) => padL + (v / 100) * (W - padL - padR);
  [0, 25, 50, 75, 100].forEach((t) => {
    el("line", { x1: x(t), x2: x(t), y1: top - 10, y2: H - 26, stroke: "#2A3358", "stroke-width": 1 }, svg);
    txt(svg, x(t), H - 8, t, { "text-anchor": "middle", "font-size": 12 });
  });
  rows.forEach((r, i) => {
    const y = top + i * rowH + rowH / 2;
    txt(svg, 0, y + 5, r.agent, { class: "axlab", "font-size": 14 });
    el("line", { x1: x(r.vanilla), x2: x(r.mave), y1: y, y2: y, stroke: "#3A4578", "stroke-width": 2, "stroke-linecap": "round" }, svg);
    [["vanilla", r.vanilla], ["mave", r.mave]].forEach(([k, v]) => {
      el("circle", { cx: x(v), cy: y, r: 7, fill: COL[k], stroke: "#161D38", "stroke-width": 2 }, svg);
      txt(svg, x(v), y - 14, v.toFixed(1), { class: "val", "text-anchor": "middle", "font-size": 13 });
    });
    txt(svg, x(r.mave) + 14, y + 5, `+${(r.mave - r.vanilla).toFixed(1)}`, { "font-size": 12.5, fill: "#E6A93A", "font-weight": 600 });
    const hit = el("rect", { x: padL - 10, y: y - rowH / 2, width: W - padL, height: rowH, fill: "transparent", tabindex: 0 }, svg);
    const rowsTip = [[COL.mave, "MAVE", r.mave.toFixed(1)], [COL.vanilla, "Vanilla", r.vanilla.toFixed(1)], [null, "gain", "+" + (r.mave - r.vanilla).toFixed(1)]];
    hit.addEventListener("pointermove", (e) => showTip(e, [[null, r.agent, ""], ...rowsTip]));
    hit.addEventListener("pointerleave", hideTip);
  });
})();

// ---- chart 2: grouped bars, per-axis score (GPT-6.1 Sol) -----------------------
(function axes() {
  const host = $("#chart-axes"); if (!host) return;
  const rows = DATA.axes, W = 560, H = 290, padL = 40, padB = 40, top = 24;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Per-axis score, vanilla vs MAVE, GPT-6.1 Sol" }, host);
  const y = (v) => H - padB - v * (H - padB - top);
  [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
    el("line", { x1: padL, x2: W, y1: y(t), y2: y(t), stroke: "#2A3358", "stroke-width": 1 }, svg);
    txt(svg, padL - 8, y(t) + 4, t.toFixed(2), { "text-anchor": "end", "font-size": 11.5 });
  });
  const band = (W - padL) / rows.length, bw = 24, gap = 2;
  rows.forEach((r, i) => {
    const cx = padL + band * i + band / 2;
    [["vanilla", r.vanilla, -1], ["mave", r.mave, 1]].forEach(([k, v, s]) => {
      const bx = cx + (s < 0 ? -bw - gap / 2 : gap / 2), by = y(v), bh = y(0) - by;
      // 4px rounded data-end, square at baseline
      el("path", { d: `M${bx},${y(0)} V${by + 4} Q${bx},${by} ${bx + 4},${by} H${bx + bw - 4} Q${bx + bw},${by} ${bx + bw},${by + 4} V${y(0)} Z`, fill: COL[k] }, svg);
      txt(svg, bx + bw / 2, by - 7, v.toFixed(2), { class: "val", "text-anchor": "middle", "font-size": 12 });
      const hit = el("rect", { x: bx - 6, y: top, width: bw + 12, height: y(0) - top, fill: "transparent", tabindex: 0 }, svg);
      hit.addEventListener("pointermove", (e) => showTip(e, [[COL[k], `${k === "mave" ? "MAVE" : "Vanilla"} · ${r.axis}`, v.toFixed(3)]]));
      hit.addEventListener("pointerleave", hideTip);
    });
    txt(svg, cx, H - 14, r.axis, { class: "axlab", "text-anchor": "middle", "font-size": 13.5 });
  });
})();

// ---- leaderboard: best / second best per column among reconstruction methods ---
(function board() {
  const tb = $("#board-body"); if (!tb) return;
  const cols = [["ore", true], ["rra"], ["rta"], ["cam"], ["ord"], ["hota"], ["iou"], ["char"], ["total"]];
  const rec = DATA.leaderboard.filter((r) => r.group !== "none");
  const rank = {};
  cols.forEach(([c, low]) => {
    const vals = [...new Set(rec.map((r) => r[c]))].sort((a, b) => (low ? a - b : b - a));
    rank[c] = { best: vals[0], second: vals[1] };
  });
  let grp = null;
  DATA.leaderboard.forEach((r) => {
    if (r.group !== grp && r.group !== "none") {
      grp = r.group;
      const g = document.createElement("tr"); g.className = "grp";
      const td = document.createElement("td"); td.colSpan = 10; td.textContent = grp === "mave" ? "MAVE (ours)" : "Vanilla agents";
      g.appendChild(td); tb.appendChild(g);
    }
    const tr = document.createElement("tr"); if (r.group === "mave") tr.className = "mave";
    const name = document.createElement("td"); name.textContent = r.method; tr.appendChild(name);
    cols.forEach(([c]) => {
      const td = document.createElement("td"); const v = r[c];
      td.textContent = c === "total" ? v.toFixed(1) : v.toFixed(3);
      if (r.group !== "none") { if (v === rank[c].best) td.className = "best"; else if (v === rank[c].second) td.className = "second"; }
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  });
})();

// ---- efficiency: score vs cost (arrows vanilla -> MAVE per agent) -------------
const mins = (t) => { const m = /(\d+)m(\d+)s/.exec(t); return +m[1] + +m[2] / 60; };
(function costChart() {
  const host = $("#chart-cost"); if (!host) return;
  const rows = DATA.efficiency, W = 560, H = 330, padL = 44, padR = 18, top = 18, padB = 42;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Total score versus API cost per shot, vanilla and MAVE" }, host);
  const x = (v) => padL + (v / 0.7) * (W - padL - padR), y = (v) => H - padB - (v - 20) / 70 * (H - padB - top);
  [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7].forEach((t) => {
    el("line", { x1: x(t), x2: x(t), y1: top, y2: H - padB, stroke: "#2A3358", "stroke-width": 1 }, svg);
    txt(svg, x(t), H - padB + 18, "$" + t.toFixed(1), { "text-anchor": "middle", "font-size": 11.5 });
  });
  [20, 40, 60, 80].forEach((t) => {
    el("line", { x1: padL, x2: W - padR, y1: y(t), y2: y(t), stroke: "#2A3358", "stroke-width": 1 }, svg);
    txt(svg, padL - 8, y(t) + 4, t, { "text-anchor": "end", "font-size": 11.5 });
  });
  txt(svg, (padL + W - padR) / 2, H - 4, "API cost per shot", { "text-anchor": "middle", "font-size": 12 });
  txt(svg, padL + 4, top + 4, "Total ↑", { "font-size": 12 });
  const defs = el("defs", {}, svg);
  const mk = el("marker", { id: "arw", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0,0 L10,5 L0,10 z", fill: "#7E86A8" }, mk);
  rows.filter((r) => r.group === "mave").forEach((m) => {
    const v = rows.find((r) => r.group === "vanilla" && r.method === m.method);
    const x1 = x(v.cost), y1 = y(v.total), x2 = x(m.cost), y2 = y(m.total), d = Math.hypot(x2 - x1, y2 - y1);
    el("line", { x1, y1, x2: x2 - (x2 - x1) / d * 11, y2: y2 - (y2 - y1) / d * 11, stroke: "#7E86A8", "stroke-width": 1.5, "marker-end": "url(#arw)" }, svg);
  });
  rows.forEach((r) => {
    const cx = x(r.cost), cy = y(r.total);
    el("circle", { cx, cy, r: 6, fill: COL[r.group], stroke: "#161D38", "stroke-width": 2 }, svg);
    if (r.group === "mave") {
      const below = r.method.startsWith("Claude");
      txt(svg, cx + 10, cy + (below ? 18 : -8), r.method, { class: "val", "font-size": 12 });
    }
    const hit = el("circle", { cx, cy, r: 14, fill: "transparent", tabindex: 0 }, svg);
    const show = (e) => showTip(e, [[COL[r.group], `${r.group === "mave" ? "MAVE" : "Vanilla"} · ${r.method}`, r.total.toFixed(1)], [null, "cost / shot", "$" + r.cost.toFixed(3)]]);
    hit.addEventListener("pointermove", show); hit.addEventListener("pointerleave", hideTip);
  });
})();

// ---- efficiency: agent time per shot, vanilla vs MAVE (+ observation) ----------
(function timeChart() {
  const host = $("#chart-time"); if (!host) return;
  const ag = DATA.efficiency.filter((r) => r.group === "mave").map((r) => r.method);
  const obs = mins(DATA.obs_time);
  const W = 560, padL = 150, padR = 96, top = 14, bandH = 76, bh = 18, H = top + ag.length * bandH + 30;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Agent minutes per shot, vanilla vs MAVE" }, host);
  const x = (v) => padL + v / 25 * (W - padL - padR);
  [0, 5, 10, 15, 20, 25].forEach((t) => {
    el("line", { x1: x(t), x2: x(t), y1: top, y2: H - 26, stroke: "#2A3358", "stroke-width": 1 }, svg);
    txt(svg, x(t), H - 8, t + "m", { "text-anchor": "middle", "font-size": 11.5 });
  });
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 5, height: 5, fill: "#161D38" }, pat);
  el("rect", { width: 2, height: 5, fill: "#C4831C" }, pat);
  const bar = (x0, x1, yy, fill, roundEnd) => {
    const r = roundEnd ? 4 : 0;
    el("path", { d: `M${x0},${yy} H${x1 - r} Q${x1},${yy} ${x1},${yy + r} V${yy + bh - r} Q${x1},${yy + bh} ${x1 - r},${yy + bh} H${x0} Z`, fill }, svg);
  };
  ag.forEach((name, i) => {
    const v = DATA.efficiency.find((r) => r.group === "vanilla" && r.method === name);
    const m = DATA.efficiency.find((r) => r.group === "mave" && r.method === name);
    const y0 = top + i * bandH + 8;
    txt(svg, 0, y0 + bh + 6, name, { class: "axlab", "font-size": 14 });
    bar(x(0), x(mins(v.time)), y0, COL.vanilla, true);
    txt(svg, x(mins(v.time)) + 8, y0 + 13, v.time, { class: "val", "font-size": 12 });
    const y1 = y0 + bh + 4;
    bar(x(0), x(mins(m.time)) - 1, y1, COL.mave, false);
    bar(x(mins(m.time)) + 1, x(mins(m.time) + obs), y1, "url(#hatch)", true);
    txt(svg, x(mins(m.time) + obs) + 8, y1 + 13, m.time + " + " + DATA.obs_time, { class: "val", "font-size": 12 });
    const hit = el("rect", { x: 0, y: y0 - 4, width: W, height: bh * 2 + 12, fill: "transparent", tabindex: 0 }, svg);
    hit.addEventListener("pointermove", (e) => showTip(e, [[null, name, ""], [COL.vanilla, "Vanilla", v.time], [COL.mave, "MAVE agent", m.time], [null, "+ Metric Observation", DATA.obs_time]]));
    hit.addEventListener("pointerleave", hideTip);
  });
})();

// ---- efficiency table -------------------------------------------------------------
(function effTable() {
  const tb = $("#eff-body"); if (!tb) return;
  const rows = DATA.efficiency;
  const best = { time: Math.min(...rows.map((r) => mins(r.time))), cost: Math.min(...rows.map((r) => r.cost)), total: Math.max(...rows.map((r) => r.total)) };
  let grp = null;
  rows.forEach((r) => {
    if (r.group !== grp) {
      grp = r.group;
      const g = document.createElement("tr"); g.className = "grp";
      const td = document.createElement("td"); td.colSpan = 5; td.textContent = grp === "mave" ? "MAVE (ours)" : "Vanilla agents";
      g.appendChild(td); tb.appendChild(g);
    }
    const tr = document.createElement("tr"); if (r.group === "mave") tr.className = "mave";
    [[r.method], [r.time, mins(r.time) === best.time], [r.prims.toFixed(1)], ["$" + r.cost.toFixed(3), r.cost === best.cost], [r.total.toFixed(1), r.total === best.total]]
      .forEach(([v, isBest]) => { const td = document.createElement("td"); td.textContent = v; if (isBest) td.className = "best"; tr.appendChild(td); });
    tb.appendChild(tr);
  });
})();

// ---- BibTeX copy ---------------------------------------------------------------
(() => {
  const b = $("#copy-bib"), pre = $("#bibtex"); if (!b || !pre) return;
  b.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(pre.textContent); b.textContent = "Copied ✓"; }
    catch (_) { b.textContent = "Select & copy"; }
    setTimeout(() => (b.textContent = "Copy"), 1500);
  });
})();
