/* Lobby Ledger NY charts: plain SVG and HTML, no libraries, themed by CSS variables. */
window.LLCharts = (() => {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const short = (n, isMoney) => {
    const a = Math.abs(n);
    const s = a >= 1e9 ? (n / 1e9).toFixed(1) + "B" : a >= 1e6 ? (n / 1e6).toFixed(1) + "M" : a >= 1e3 ? Math.round(n / 1e3) + "K" : String(Math.round(n));
    return (isMoney ? "$" : "") + s.replace(".0", "");
  };
  const niceMax = (v) => {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  };

  /**
   * Vertical bars by year, optionally stacked.
   * series: [{label, cls, values: {year: number}}]
   */
  function yearBars({ title, years, series, isMoney = true, note = "" }) {
    if (!years.length || series.every((s) => !Object.values(s.values).some((v) => v > 0))) return "";
    const W = 560, H = 210, L = 52, R = 8, T = 10, B = 26;
    const totals = years.map((y) => series.reduce((s, x) => s + (x.values[y] || 0), 0));
    const max = niceMax(Math.max(...totals));
    const bw = Math.min(46, ((W - L - R) / years.length) * 0.62);
    const step = (W - L - R) / years.length;
    const yv = (v) => T + (H - T - B) * (1 - v / max);
    let svg = "";
    for (const f of [0, 0.5, 1]) {
      const v = max * f, y = yv(v);
      svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text class="tick" x="${L - 6}" y="${y + 4}" text-anchor="end">${short(v, isMoney)}</text>`;
    }
    const rows = [];
    years.forEach((yr, i) => {
      const x = L + step * i + (step - bw) / 2;
      let base = 0;
      const parts = [];
      for (const s of series) {
        const v = s.values[yr] || 0;
        if (v > 0) {
          const y0 = yv(base), y1 = yv(base + v);
          svg += `<rect class="${s.cls}" x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(1, y0 - y1).toFixed(1)}"><title>${yr}, ${esc(s.label)}: ${isMoney ? money(v) : v.toLocaleString("en-US")}</title></rect>`;
          parts.push(`${s.label} ${isMoney ? money(v) : v.toLocaleString("en-US")}`);
        }
        base += v;
      }
      svg += `<text class="tick" x="${(x + bw / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${yr}</text>`;
      rows.push(`<tr><th scope="row">${yr}</th>${series.map((s) => `<td>${isMoney ? money(s.values[yr] || 0) : (s.values[yr] || 0).toLocaleString("en-US")}</td>`).join("")}</tr>`);
    });
    const legend = series.length > 1 ? `<ul class="legend">${series.map((s) => `<li><span class="key ${s.cls}"></span>${esc(s.label)}</li>`).join("")}</ul>` : "";
    const table = `<table class="sr-only"><caption>${esc(title)}</caption><thead><tr><th>Year</th>${series.map((s) => `<th>${esc(s.label)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
    return `<figure class="chart"><figcaption>${esc(title)}</figcaption>${legend}
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}" preserveAspectRatio="xMidYMid meet">${svg}</svg>${table}${note ? `<p class="chart-note">${note}</p>` : ""}</figure>`;
  }

  /** Ranked horizontal bars. items: [{label, href, sub, value, display}] */
  function ranked({ title, items, isMoney = true, cls = "s-direct", note = "" }) {
    if (!items.length) return "";
    const max = Math.max(...items.map((i) => i.value)) || 1;
    return `<figure class="chart"><figcaption>${esc(title)}</figcaption><ol class="ranked">${items.map((i) => `
      <li><a href="${i.href}"><span class="r-label">${esc(i.label)}${i.sub ? `<span class="r-sub">${esc(i.sub)}</span>` : ""}</span>
      <span class="r-bar"><span class="${cls}" style="width:${Math.max(1.5, (100 * i.value) / max).toFixed(1)}%"></span></span>
      <span class="r-val">${i.display ?? (isMoney ? money(i.value) : i.value.toLocaleString("en-US"))}</span></a></li>`).join("")}</ol>${note ? `<p class="chart-note">${note}</p>` : ""}</figure>`;
  }

  /**
   * Timeline with one lane per kind of record.
   * lanes: [{label, cls, events: [{t, size, text}]}]  t = fractional year
   */
  function timeline({ title, lanes, from, to }) {
    const used = lanes.filter((l) => l.events.length);
    if (!used.length) return "";
    const W = 640, L = 150, R = 16, laneH = 46, T = 8, B = 26;
    const H = T + laneH * used.length + B;
    const x = (t) => L + ((t - from) / (to + 1 - from)) * (W - L - R);
    const maxSize = Math.max(...used.flatMap((l) => l.events.map((e) => e.size || 1)));
    let svg = "";
    for (let y = from; y <= to + 1; y++) {
      svg += `<line class="grid" x1="${x(y)}" x2="${x(y)}" y1="${T}" y2="${H - B}"/>`;
      if (y <= to) svg += `<text class="tick" x="${(x(y) + x(y + 1)) / 2}" y="${H - 8}" text-anchor="middle">${y}</text>`;
    }
    used.forEach((l, i) => {
      const cy = T + laneH * i + laneH / 2;
      svg += `<text class="lane" x="0" y="${cy + 4}">${esc(l.label)}</text><line class="axis" x1="${L}" x2="${W - R}" y1="${cy}" y2="${cy}"/>`;
      for (const e of l.events) {
        const r = l.sized ? 4 + 12 * Math.sqrt((e.size || 1) / maxSize) : 5;
        svg += `<circle class="${l.cls}" cx="${x(e.t).toFixed(1)}" cy="${cy}" r="${r.toFixed(1)}"><title>${esc(e.text)}</title></circle>`;
      }
    });
    const list = used.map((l) => `<li>${esc(l.label)}: ${l.events.map((e) => esc(e.text)).join("; ")}</li>`).join("");
    return `<figure class="chart wide"><figcaption>${esc(title)}</figcaption>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">${svg}</svg><ul class="sr-only">${list}</ul>
      <p class="chart-note">Each mark is one filing or contribution; larger circles mean more money. Hover or tap a mark for details.</p></figure>`;
  }

  return { yearBars, ranked, timeline, money, short };
})();
