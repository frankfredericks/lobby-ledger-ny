/* Lobby Ledger NY: client-side renderer for data/city.json and data/state.json. */
(() => {
  "use strict";
  const CFG = Object.assign({ title: "Lobby Ledger NY", tagline: "Who funds and lobbies New York officials" }, window.SITE_CONFIG || {});
  const JUR = { city: "City", state: "State" };
  const cache = {};
  let D = null; // current jurisdiction data + indexes
  let state = { j: "city", from: null, to: null };

  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const plural = (n, w) => `${n.toLocaleString("en-US")} ${w}${n === 1 ? "" : "s"}`;

  // ---------------------------------------------------------------- data
  async function load(j) {
    if (cache[j]) return cache[j];
    let raw = window.__DATA__ && window.__DATA__[j];
    if (!raw) {
      const r = await fetch(`data/${j}.json`, { cache: "no-cache" });
      if (!r.ok) throw new Error(`Couldn’t load data/${j}.json (HTTP ${r.status}).`);
      raw = await r.json();
    }
    cache[j] = index(raw);
    return cache[j];
  }

  function index(d) {
    const by = (rows, i) => { const m = new Map(); for (const r of rows) { const k = r[i]; if (!m.has(k)) m.set(k, []); m.get(k).push(r); } return m; };
    d.ix = {
      cByDonor: by(d.contribs, 0), cByOff: by(d.contribs, 1),
      iecByDonor: by(d.ie_contribs, 0), iecByCmte: by(d.ie_contribs, 1),
      iesByCmte: by(d.ie_spend, 0), iesByOff: by(d.ie_spend, 1),
      lByClient: by(d.lobby, 0), lByFirm: by(d.lobby, 1),
      lByOff: new Map(), lByBill: new Map(),
      fByFirm: by(d.fundraising, 0), fByOff: by(d.fundraising, 1),
    };
    for (const r of d.lobby) {
      for (const o of r[5]) { if (!d.ix.lByOff.has(o)) d.ix.lByOff.set(o, []); d.ix.lByOff.get(o).push(r); }
      for (const b of r[4]) { if (!d.ix.lByBill.has(b)) d.ix.lByBill.set(b, []); d.ix.lByBill.get(b).push(r); }
    }
    return d;
  }

  const inRange = (y) => (!state.from || y >= state.from) && (!state.to || y <= state.to);
  const F = (rows) => (rows || []).filter((r) => inRange(r[2]));
  const ent = (id) => D.entities[id] || { name: id, roles: [] };
  const off = (id) => D.officials[id] || { name: id, office: "" };
  const bill = (id) => D.bills[id] || { label: id, session: "" };

  function srcUrl(src) {
    if (!src) return "";
    const i = src.indexOf("|");
    const code = src.slice(0, i), rest = src.slice(i + 1);
    if (code === "url") return rest;
    const s = D.meta.sources[code];
    if (!s) return "";
    return rest && s.api ? `${s.api}?${rest}` : s.page;
  }
  const srcLink = (src, label = "Source") => { const u = srcUrl(src); return u ? `<a class="src" href="${esc(u)}" target="_blank" rel="noopener">${label}</a>` : ""; };

  // ---------------------------------------------------------------- routing
  function hrefFor(kind, ...ids) {
    const q = [];
    if (state.from) q.push("from=" + state.from);
    if (state.to) q.push("to=" + state.to);
    const tail = q.length ? "?" + q.join("&") : "";
    return `#/${state.j}${kind ? "/" + kind + "/" + ids.map(encodeURIComponent).join("/") : ""}${tail}`;
  }
  const L = {
    o: (id) => `<a href="${hrefFor("o", id)}">${esc(off(id).name)}</a>`,
    e: (id) => `<a href="${hrefFor("e", id)}">${esc(ent(id).name)}</a>`,
    b: (id) => `<a href="${hrefFor("b", id)}">${esc(bill(id).label)}</a> <span class="detail" style="display:inline">(${esc(bill(id).session)})</span>${bill(id).title ? `<span class="bill-title">${esc(bill(id).title)}</span>` : ""}`,
    r: (eid, oid, text = "See connection") => `<a href="${hrefFor("r", eid, oid)}">${text}</a>`,
  };

  function parseHash() {
    const h = location.hash.replace(/^#\/?/, "");
    const [path, query] = h.split("?");
    const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    const q = new URLSearchParams(query || "");
    return { j: JUR[parts[0]] ? parts[0] : "city", kind: parts[1] || "", ids: parts.slice(2), from: +q.get("from") || null, to: +q.get("to") || null };
  }

  async function route() {
    const r = parseHash();
    state.j = r.j; state.from = r.from; state.to = r.to;
    renderChrome();
    const main = $("#main");
    try {
      D = await load(state.j);
    } catch (err) {
      main.innerHTML = `<p class="empty">${esc(err.message)} Check that the monthly data build has run, then reload.</p>`;
      return;
    }
    renderYears();
    renderNotice();
    const view = { o: viewOfficial, e: viewEntity, b: viewBill, r: viewRelationship }[r.kind] || viewHome;
    main.innerHTML = view(...r.ids);
    bindHome();
    const h1 = $("h1", main);
    if (r.kind && h1) { h1.setAttribute("tabindex", "-1"); h1.focus({ preventScroll: true }); }
    window.scrollTo(0, 0);
    document.title = (h1 ? h1.textContent + " — " : "") + CFG.title;
  }

  // ---------------------------------------------------------------- chrome
  function renderChrome() {
    for (const a of document.querySelectorAll(".tabs a")) {
      const on = a.dataset.j === state.j;
      a.setAttribute("aria-current", on ? "page" : "false");
      a.href = `#/${a.dataset.j}` + (state.from || state.to ? `?${state.from ? "from=" + state.from : ""}${state.from && state.to ? "&" : ""}${state.to ? "to=" + state.to : ""}` : "");
    }
  }
  function renderYears() {
    const [a, b] = D.meta.years.length ? D.meta.years : [D.meta.start_year, new Date().getFullYear()];
    const opts = (sel) => { let s = ""; for (let y = a; y <= b; y++) s += `<option ${y === sel ? "selected" : ""}>${y}</option>`; return s; };
    $("#from").innerHTML = opts(state.from || a);
    $("#to").innerHTML = opts(state.to || b);
    $("#updated").textContent = `${D.meta.refresh_label}. Last update ${new Date(D.meta.generated + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}.`;
  }
  function renderNotice() {
    const w = D.meta.warnings || [];
    $("#notice").innerHTML = w.length ? `<p><b>Coverage gap:</b> ${w.map(esc).join(" ")}</p>` : "";
  }
  function onYears() {
    let f = +$("#from").value, t = +$("#to").value;
    if (f > t) [f, t] = [t, f];
    const [a, b] = D.meta.years;
    state.from = f === a ? null : f; state.to = t === b ? null : t;
    const r = parseHash();
    location.hash = hrefFor(r.kind, ...r.ids);
  }

  // ---------------------------------------------------------------- shared bits
  const table = (head, rows, empty) => rows.length
    ? `<div class="scroll"><table><thead><tr>${head.map((h) => `<th${h.num ? ' class="num"' : ""}>${h.t ?? h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`
    : `<p class="empty">${empty}</p>`;
  const num = (h) => ({ t: h, num: true });
  const yearsOf = (rows) => { const ys = [...new Set(rows.map((r) => r[2]))].sort(); return ys.length > 1 ? `${ys[0]}–${ys[ys.length - 1]}` : String(ys[0] ?? ""); };
  const posTag = (p) => p && p !== "amend" && p !== "mixed" ? `<span class="pos ${p}">Self-described: ${p}</span>` : p ? `<span class="pos">Self-described: ${p === "amend" ? "seeking amendments" : "mixed"}</span>` : "";
  const rangeLabel = () => (state.from || state.to) ? `${state.from || D.meta.years[0]}–${state.to || D.meta.years[1]}` : "all years";
  const caveatLink = `<a class="caveat-link" href="methodology.html#relationships">What these connections do and don’t show</a>`;

  function sumBy(rows, keyIdx, amtIdx = 3) {
    const m = new Map();
    for (const r of rows) { const k = r[keyIdx]; const v = m.get(k) || { amt: 0, n: 0, rows: [] }; v.amt += r[amtIdx]; v.n += r[4] || 1; v.rows.push(r); m.set(k, v); }
    return [...m.entries()].sort((a, b) => b[1].amt - a[1].amt);
  }

  // ---------------------------------------------------------------- home
  const C = window.LLCharts;
  const yearList = () => { const [a, b] = D.meta.years.length ? D.meta.years : [D.meta.start_year, new Date().getFullYear()]; const out = []; for (let y = state.from || a; y <= (state.to || b); y++) out.push(y); return out; };
  const byYear = (rows, val = (r) => r[3]) => { const m = {}; for (const r of rows) m[r[2]] = (m[r[2]] || 0) + val(r); return m; };
  const countByYear = (rows) => byYear(rows, () => 1);
  const billName = (id) => bill(id).title || "";
  const clip = (t, n) => (t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t);

  const HOME_COLS = {
    o: [["From organizations", true], ["Lobbying filings", false]],
    e: [["Political giving", true], ["Lobbying filings", false]],
    b: [["Organizations", false], ["Filings", false]],
  };
  let homeSort = { o: 0, e: 0, b: 0 };

  function viewHome() {
    const offs = Object.keys(D.officials).map((id) => ({
      id, name: D.officials[id].name, sub: D.officials[id].office,
      v: [F(D.ix.cByOff.get(id)).reduce((s, r) => s + r[3], 0), F(D.ix.lByOff.get(id)).length],
    }));
    const ents = Object.keys(D.entities).map((id) => {
      const e = D.entities[id];
      return { id, name: e.name, alt: (e.aliases || []).join(" "), sub: roleLabel(e),
        v: [F(D.ix.cByDonor.get(id)).reduce((s, r) => s + r[3], 0) + F(D.ix.iecByDonor.get(id)).reduce((s, r) => s + r[3], 0),
            F(D.ix.lByClient.get(id)).length + F(D.ix.lByFirm.get(id)).filter((r) => r[0] !== id).length] };
    });
    const bills = Object.keys(D.bills).map((id) => {
      const rows = F(D.ix.lByBill.get(id));
      return { id, name: `${D.bills[id].label} (${shortSess(D.bills[id].session)})`, sub: billName(id), v: [new Set(rows.map((r) => r[0])).size, rows.length] };
    });
    const fmt = (kind, i, n) => (n ? (HOME_COLS[kind][i][1] ? C.short(n, true) : n.toLocaleString("en-US")) : "–");
    const col = (title, items, kind) => {
      const live = items.filter((x) => x.v[0] > 0 || x.v[1] > 0);
      const [c0, c1] = HOME_COLS[kind];
      return `<section data-kind="${kind}"><h2>${title} <span>${live.length.toLocaleString("en-US")}</span></h2>
        <div class="cols"><span>Sort by</span><button type="button" data-sort="0" aria-pressed="false">${c0[0]}</button><button type="button" data-sort="1" aria-pressed="false">${c1[0]}</button></div>
        <ol>${live.map((x) => `<li data-v0="${x.v[0]}" data-v1="${x.v[1]}" data-q="${esc((x.name + " " + (x.alt || "") + " " + (x.sub || "")).toLowerCase())}"><a href="${hrefFor(kind, x.id)}"><span><span class="nm">${esc(x.name)}</span>${x.sub ? `<span class="sub">${esc(x.sub)}</span>` : ""}</span><span class="n${x.v[0] ? "" : " zero"}">${fmt(kind, 0, x.v[0])}</span><span class="n${x.v[1] ? "" : " zero"}">${fmt(kind, 1, x.v[1])}</span></a></li>`).join("")}</ol>
        ${live.length > 25 ? `<button class="more" type="button">Show all ${live.length.toLocaleString("en-US")}</button>` : ""}
        ${live.length ? "" : `<p class="empty">Nothing recorded for ${rangeLabel()}.</p>`}</section>`;
    };

    const ys = yearList();
    const money = C.yearBars({ title: "Organization money by year", years: ys, series: [
      { label: "To officials’ campaigns", cls: "s-direct", values: byYear(F(D.contribs)) },
      { label: "To super PACs", cls: "s-pac", values: byYear(F(D.ie_contribs)) }] });
    const filings = C.yearBars({ title: "Lobbying filings by year", years: ys, isMoney: false, series: [
      { label: "Filings", cls: "s-lobby", values: countByYear(F(D.lobby)) }] });
    const topOrgs = C.ranked({ title: "Top political givers", items: ents.filter((x) => x.v[0] > 0).sort((a, b) => b.v[0] - a.v[0]).slice(0, 8)
      .map((x) => ({ label: x.name, href: hrefFor("e", x.id), value: x.v[0], sub: x.v[1] ? plural(x.v[1], "lobbying filing") : "" })),
      note: "Direct contributions plus super PAC contributions, including affiliated PACs listed separately." });
    const topBills = C.ranked({ title: "Most-lobbied bills", isMoney: false, cls: "s-lobby",
      items: bills.filter((x) => x.v[0] > 0).sort((a, b) => b.v[0] - a.v[0] || b.v[1] - a.v[1]).slice(0, 8)
        .map((x) => ({ label: x.name, href: hrefFor("b", x.id), value: x.v[0], sub: clip(x.sub || "", 60), display: plural(x.v[0], "org") })),
      note: "Ranked by the number of organizations whose filings name the bill." });

    return `<h1 class="sr-only">${JUR[state.j]} officials, organizations and bills</h1>
      <label class="search"><span class="sr-only">Search</span><input id="q" type="search" autocomplete="off" placeholder="Search officials, organizations, bills or topics"></label>
      <div class="charts">${money}${filings}${topOrgs}${topBills}</div>
      <div class="index">${col("Officials and candidates", offs, "o")}${col("Organizations", ents, "e")}${col("Bills", bills, "b")}</div>`;
  }

  function roleLabel(e) {
    const r = new Set(e.roles || []);
    if (r.has("ie_committee")) return "Super PAC";
    if (r.has("lobbyist") && !r.has("client")) return "Lobbying firm";
    if (r.has("client")) return "Lobbying client";
    if (r.has("ie_donor") && !r.has("donor")) return "Super PAC donor";
    return "Political donor";
  }

  function bindHome() {
    const q = $("#q");
    if (!q) return;
    const apply = () => {
      const t = q.value.trim().toLowerCase();
      for (const sec of document.querySelectorAll(".index section")) {
        const kind = sec.dataset.kind, k = homeSort[kind], ol = $("ol", sec);
        const lis = [...ol.children].sort((a, b) => (+b.dataset["v" + k] - +a.dataset["v" + k]) || (+b.dataset["v" + (1 - k)] - +a.dataset["v" + (1 - k)]));
        lis.forEach((li) => ol.appendChild(li));
        const expanded = sec.dataset.expanded === "1";
        let shown = 0;
        for (const li of lis) {
          const hit = !t || li.dataset.q.includes(t);
          li.hidden = !hit || (!t && !expanded && shown >= 25);
          if (hit) shown++;
        }
        for (const btn of sec.querySelectorAll("[data-sort]")) btn.setAttribute("aria-pressed", String(+btn.dataset.sort === k));
        const more = $(".more", sec);
        if (more) more.hidden = !!t || expanded;
      }
    };
    q.addEventListener("input", apply);
    for (const btn of document.querySelectorAll("[data-sort]")) btn.addEventListener("click", () => { homeSort[btn.closest("section").dataset.kind] = +btn.dataset.sort; apply(); });
    for (const b of document.querySelectorAll(".more")) b.addEventListener("click", () => { b.closest("section").dataset.expanded = "1"; apply(); });
    apply();
  }

  // ---------------------------------------------------------------- official
  function viewOfficial(id) {
    const o = off(id);
    if (!D.officials[id]) return notFound("official");
    const T = D.meta.threshold;
    const direct = sumBy(F(D.ix.cByOff.get(id)), 0).filter(([, v]) => v.amt >= T);
    const spends = sumBy(F(D.ix.iesByOff.get(id)), 0);
    const lob = F(D.ix.lByOff.get(id));
    const lobOrgs = new Map();
    for (const r of lob) { const v = lobOrgs.get(r[0]) || { n: 0, bills: new Set(), firms: new Set() }; v.n++; billsWith(r, id).forEach((b) => v.bills.add(b)); v.firms.add(r[1]); lobOrgs.set(r[0], v); }
    const fund = sumBy(F(D.ix.fByOff.get(id)), 0);
    const totalDirect = direct.reduce((s, [, v]) => s + v.amt, 0);

    const directRows = direct.map(([eid, v]) => `<tr><td>${L.e(eid)}${ent(eid).db ? ' <span class="badge db">Doing business with the City</span>' : ""}</td><td class="num">${money(v.amt)}</td><td class="num">${v.n}</td><td>${yearsOf(v.rows)}</td><td>${L.r(eid, id)}</td><td>${srcLink(v.rows[0][5])}</td></tr>`);
    const ieBlocks = spends.map(([cid, v]) => {
      const stance = v.rows.find((r) => r[4])?.[4] || "";
      const donors = sumBy(F(D.ix.iecByCmte.get(cid)), 0).filter(([, d]) => d.amt >= T);
      const rows = donors.map(([did, d]) => `<tr><td>${L.e(did)}</td><td class="num">${money(d.amt)}</td><td>${yearsOf(d.rows)}</td><td>${srcLink(d.rows[0][5])}</td></tr>`);
      return `<h3>${L.e(cid)}: spent ${money(v.amt)} ${stance ? (stance === "support" ? "supporting" : "opposing") : "on"} ${esc(o.name)} <span class="detail">${srcLink(v.rows[0][5], "Spending record")}</span></h3>
        ${table(["Donor to this committee", num("Given to committee"), "Years", ""], rows, `No donors of ${money(T)} or more reported for ${rangeLabel()}.`)}`;
    });
    const lobRows = [...lobOrgs.entries()].sort((a, b) => b[1].n - a[1].n).map(([eid, v]) =>
      `<tr><td>${L.e(eid)}<span class="detail">via ${[...v.firms].filter((f) => f !== eid).map((f) => esc(ent(f).name)).join(", ") || "in-house"}</span></td><td class="num">${v.n}</td><td><div class="chips">${[...v.bills].slice(0, 8).map(chip).join("")}${v.bills.size > 8 ? `<span class="detail">+${v.bills.size - 8} more</span>` : ""}</div></td><td>${L.r(eid, id)}</td></tr>`);
    const fundRows = fund.map(([eid, v]) => `<tr><td>${L.e(eid)}</td><td class="num">${money(v.amt)}</td><td>${esc([...new Set(v.rows.map((r) => r[4]).filter(Boolean))].join(", "))}</td><td>${yearsOf(v.rows)}</td><td>${srcLink(v.rows[0][5])}</td></tr>`);

    return `${crumbs()}<header class="record-head"><h1><span class="mark">${esc(o.name)}</span></h1><p>${esc(o.office || "Official or candidate")}. Showing ${rangeLabel()}.</p></header>
      <ul class="totals"><li><b>${money(totalDirect)}</b><span>from organizations giving ${money(T)}+</span></li><li><b>${spends.length}</b><span>super PACs spending on this race</span></li><li><b>${lobOrgs.size}</b><span>organizations that lobbied this office</span></li></ul>
      <div class="charts">${C.yearBars({ title: "Money around this race, by year", years: yearList(), series: [
        { label: "From organizations", cls: "s-direct", values: byYear(F(D.ix.cByOff.get(id))) },
        { label: "Super PAC spending for", cls: "s-pac", values: byYear(F(D.ix.iesByOff.get(id)).filter((r) => r[4] !== "oppose")) },
        { label: "Super PAC spending against", cls: "s-oppose", values: byYear(F(D.ix.iesByOff.get(id)).filter((r) => r[4] === "oppose")) }],
        note: "Organization money includes all organization contributions, not only those above the threshold." })}
      ${C.yearBars({ title: "Lobbying filings naming this official", years: yearList(), isMoney: false, series: [{ label: "Filings", cls: "s-lobby", values: countByYear(lob) }] })}</div>
      <section class="block"><h2>Organization donors</h2><p class="sub">Organizations whose contributions to this campaign total ${money(T)} or more in the selected years. Individual donors aren’t shown. ${caveatLink}</p>
        ${table(["Organization", num("Total"), num("Contributions"), "Years", "", ""], directRows, `No organization gave ${money(T)} or more in ${rangeLabel()}.`)}</section>
      <section class="block"><h2>Super PAC (independent expenditure) donors</h2><p class="sub">Independent committees can’t coordinate with candidates. Donors gave to the committee, not to the candidate; the committee then spent on this race.</p>
        ${ieBlocks.join("") || `<p class="empty">No independent spending recorded on this race for ${rangeLabel()}.</p>`}</section>
      <section class="block"><h2>Lobbied by</h2><p class="sub">Organizations whose lobbying filings name this official or their staff.</p>
        ${table(["Organization", num("Filings"), "Bills named", ""], lobRows, `No lobbying filings name this official in ${rangeLabel()}.`)}</section>
      ${D.fundraising.length ? `<section class="block"><h2>Fundraising by lobbyists</h2><p class="sub">Registered lobbyists who reported raising money or consulting for this campaign.</p>${table(["Lobbyist", num("Amount"), "Activity", "Years", ""], fundRows, `None reported for ${rangeLabel()}.`)}</section>` : ""}`;
  }

  // ---------------------------------------------------------------- entity
  function viewEntity(id) {
    const e = ent(id);
    if (!D.entities[id]) return notFound("organization");
    const ids = [id, ...(e.affiliates || [])];
    const gather = (map) => ids.flatMap((x) => F(map.get(x)));
    const gifts = gather(D.ix.cByDonor);
    const ieGifts = gather(D.ix.iecByDonor);
    const asClient = F(D.ix.lByClient.get(id));
    const asFirm = F(D.ix.lByFirm.get(id)).filter((r) => r[0] !== id);
    const lob = asClient.concat(asFirm);
    const spends = F(D.ix.iesByCmte.get(id));
    const raised = F(D.ix.iecByCmte.get(id));
    const fund = F(D.ix.fByFirm.get(id));

    // connections with officials
    const conn = new Map();
    const CN = (oid) => conn.get(oid) || (conn.set(oid, { give: 0, filings: 0, bills: new Set(), ie: 0, fund: 0 }), conn.get(oid));
    for (const r of gifts) CN(r[1]).give += r[3];
    for (const r of lob) for (const o of r[5]) { const c = CN(o); c.filings++; billsWith(r, o).forEach((b) => c.bills.add(b)); }
    for (const g of ieGifts) {
      for (const s of F(D.ix.iesByCmte.get(g[1]))) {
        const c = CN(s[1]);
        c.ieVia = c.ieVia || new Set();
        c.ieVia.add(g[1]);
      }
    }
    for (const r of fund) CN(r[1]).fund += r[3];
    const connRows = [...conn.entries()].sort((a, b) => (b[1].give + b[1].filings * 1e4 + b[1].fund) - (a[1].give + a[1].filings * 1e4 + a[1].fund)).map(([oid, c]) =>
      `<tr><td>${L.o(oid)}<span class="detail">${esc(off(oid).office)}</span></td><td class="num">${c.give ? money(c.give) : "–"}</td><td class="num">${c.filings || "–"}</td><td>${c.ieVia ? [...c.ieVia].map((x) => esc(ent(x).name)).join(", ") : "–"}</td><td>${L.r(id, oid)}</td></tr>`);

    const billMap = new Map();
    for (const r of lob) for (const b of r[4]) { const v = billMap.get(b) || { n: 0, pos: new Set(), offs: new Set() }; v.n++; if (r[8] && r[8][b]) v.pos.add(r[8][b]); offsFor(r, b).forEach((o) => v.offs.add(o)); billMap.set(b, v); }
    const billRows = [...billMap.entries()].sort((a, b) => b[1].n - a[1].n).map(([b, v]) =>
      `<tr><td>${L.b(b)}</td><td class="num">${v.n}</td><td>${[...v.pos].map(posTag).join(" ")}</td><td>${v.offs.size}</td></tr>`);

    const otherTargets = new Map();
    for (const r of lob) for (const t of r[6]) otherTargets.set(t, (otherTargets.get(t) || 0) + 1);
    const otherRows = [...otherTargets.entries()].sort((a, b) => b[1] - a[1]).slice(0, 40).map(([t, n]) => `<tr><td>${esc(t)}</td><td class="num">${n}</td></tr>`);

    const giftRows = sumBy(gifts, 1).map(([oid, v]) => `<tr><td>${L.o(oid)}</td><td>${[...new Set(v.rows.map((r) => r[0]))].map((x) => esc(ent(x).name)).join(", ")}</td><td class="num">${money(v.amt)}</td><td class="num">${v.n}</td><td>${yearsOf(v.rows)}</td><td>${srcLink(v.rows[0][5])}</td></tr>`);
    const ieRows = sumBy(ieGifts, 1).map(([cid, v]) => {
      const targets = sumBy(F(D.ix.iesByCmte.get(cid)), 1).map(([oid, s]) => `${s.rows[0][4] === "oppose" ? "opposed" : s.rows[0][4] === "support" ? "supported" : "spent on"} ${L.o(oid)} (${money(s.amt)})`).join("; ");
      return `<tr><td>${L.e(cid)}<span class="detail">${targets || "No spending recorded in these years"}</span></td><td class="num">${money(v.amt)}</td><td>${yearsOf(v.rows)}</td><td>${srcLink(v.rows[0][5])}</td></tr>`;
    });
    const partner = new Map();
    for (const r of asClient) partner.set(r[1], (partner.get(r[1]) || 0) + 1);
    const clientMap = new Map();
    for (const r of asFirm) clientMap.set(r[0], (clientMap.get(r[0]) || 0) + 1);
    const roles = new Set(e.roles);
    const badges = [roles.has("client") && "Lobbying client", roles.has("lobbyist") && "Lobbying firm", roles.has("ie_committee") && "Super PAC / independent committee", (roles.has("donor") || roles.has("ie_donor")) && "Political donor"].filter(Boolean)
      .map((b) => `<span class="badge">${b}</span>`).join("") + (e.db ? `<span class="badge db">On the City’s Doing Business list</span>` : "");
    const comp = asClient.reduce((s, r) => s + (r[7] || 0), 0);

    return `${crumbs()}<header class="record-head"><h1><span class="mark">${esc(e.name)}</span></h1>
      ${e.aliases && e.aliases.length ? `<p>Also filed as: ${e.aliases.map(esc).join("; ")}</p>` : ""}
      ${e.affiliates && e.affiliates.length ? `<p>Affiliated committees and organizations, included below: ${e.affiliates.map(L.e).join(", ")}</p>` : ""}
      <div class="badges">${badges}</div></header>
      <ul class="totals"><li><b>${money(gifts.reduce((s, r) => s + r[3], 0))}</b><span>to officials’ campaigns</span></li><li><b>${money(ieGifts.reduce((s, r) => s + r[3], 0))}</b><span>to super PACs</span></li><li><b>${lob.length}</b><span>lobbying filings</span></li>${comp ? `<li><b>${money(comp)}</b><span>paid to lobbyists</span></li>` : ""}</ul>
      <div class="charts">${C.yearBars({ title: "Political giving by year", years: yearList(), series: [
        { label: "To officials’ campaigns", cls: "s-direct", values: byYear(gifts) },
        { label: "To super PACs", cls: "s-pac", values: byYear(ieGifts) }] })}
      ${C.yearBars({ title: "Lobbying filings by year", years: yearList(), isMoney: false, series: [{ label: "Filings", cls: "s-lobby", values: countByYear(lob) }] })}
      ${C.ranked({ title: "Officials this organization gave the most to", items: sumBy(gifts, 1).slice(0, 6).map(([oid, v]) => ({ label: off(oid).name, sub: off(oid).office, href: hrefFor("r", id, oid), value: v.amt })) })}
      ${C.ranked({ title: "Officials this organization lobbied most", isMoney: false, cls: "s-lobby", items: [...conn.entries()].filter(([, c]) => c.filings).sort((a, b) => b[1].filings - a[1].filings).slice(0, 6).map(([oid, c]) => ({ label: off(oid).name, sub: off(oid).office, href: hrefFor("r", id, oid), value: c.filings, display: plural(c.filings, "filing") })) })}</div>
      <section class="block"><h2>Connections with officials</h2><p class="sub">Every official this organization gave to, lobbied, or whose race it funded through a super PAC, ${rangeLabel()}. ${caveatLink}</p>
        ${table(["Official", num("Gave directly"), num("Lobbying filings"), "Via super PAC", ""], connRows, `No connections with officials in ${rangeLabel()}.`)}</section>
      <section class="block"><h2>Bills lobbied</h2><p class="sub">Positions appear only when the filer wrote one in; New York doesn’t require it.</p>
        ${table(["Bill", num("Filings"), "Position", "Officials named"], billRows, `No bills named in ${rangeLabel()}.`)}</section>
      ${otherRows.length ? `<section class="block"><h2>Other agencies and staff lobbied</h2>${table(["Target as filed", num("Filings")], otherRows, "")}</section>` : ""}
      <section class="block"><h2>Donations to officials</h2>${table(["Official", "Given by", num("Total"), num("Contributions"), "Years", ""], giftRows, `No direct contributions in ${rangeLabel()}.`)}</section>
      <section class="block"><h2>Super PAC giving</h2>${table(["Committee", num("Given"), "Years", ""], ieRows, `No super PAC contributions in ${rangeLabel()}.`)}</section>
      ${spends.length || raised.length ? `<section class="block"><h2>This committee’s donors</h2>${table(["Donor", num("Given"), "Years", ""], sumBy(raised, 0).map(([d, v]) => `<tr><td>${L.e(d)}</td><td class="num">${money(v.amt)}</td><td>${yearsOf(v.rows)}</td><td>${srcLink(v.rows[0][5])}</td></tr>`), "No donors reported.")}</section>` : ""}
      ${partner.size ? `<section class="block"><h2>Lobbying firms hired</h2>${table(["Firm", num("Filings")], [...partner.entries()].map(([f, n]) => `<tr><td>${f === id ? "In-house" : L.e(f)}</td><td class="num">${n}</td></tr>`), "")}</section>` : ""}
      ${clientMap.size ? `<section class="block"><h2>Clients</h2>${table(["Client", num("Filings")], [...clientMap.entries()].sort((a, b) => b[1] - a[1]).map(([c, n]) => `<tr><td>${L.e(c)}</td><td class="num">${n}</td></tr>`), "")}</section>` : ""}
      ${fund.length ? `<section class="block"><h2>Fundraising and consulting for candidates</h2>${table(["Candidate", num("Amount"), "Year", ""], fund.map((r) => `<tr><td>${L.o(r[1])}</td><td class="num">${money(r[3])}</td><td>${r[2]}</td><td>${srcLink(r[5])}</td></tr>`), "")}</section>` : ""}`;
  }

  // ---------------------------------------------------------------- bill
  function viewBill(id) {
    const b = bill(id);
    if (!D.bills[id]) return notFound("bill");
    const rows = F(D.ix.lByBill.get(id));
    const orgs = new Map();
    for (const r of rows) { const v = orgs.get(r[0]) || { n: 0, firms: new Set(), offs: new Set(), pos: new Set(), rows: [] }; v.n++; v.firms.add(r[1]); offsFor(r, id).forEach((o) => v.offs.add(o)); if (r[8] && r[8][id]) v.pos.add(r[8][id]); v.rows.push(r); orgs.set(r[0], v); }
    const ext = b.url || (state.j === "state" ? `https://www.nysenate.gov/legislation/bills/${b.session.split("-")[0]}/${b.label}` : "https://legistar.council.nyc.gov/Legislation.aspx");
    const extLabel = state.j === "state" ? "Read the bill on nysenate.gov" : b.url ? "Read the bill on the Council’s legislation site" : "Find the bill on the Council’s legislation site";
    const tr = [...orgs.entries()].sort((a, c) => c[1].n - a[1].n).map(([eid, v]) =>
      `<tr><td>${L.e(eid)}<span class="detail">via ${[...v.firms].filter((f) => f !== eid).map((f) => esc(ent(f).name)).join(", ") || "in-house"}</span></td><td class="num">${v.n}</td><td>${yearsOf(v.rows)}</td><td>${[...v.pos].map(posTag).join(" ")}</td><td><div class="chips">${[...v.offs].slice(0, 6).map(L.o).join("")}${v.offs.size > 6 ? `<span class="detail">+${v.offs.size - 6} more</span>` : ""}</div></td><td>${srcLink(v.rows[0][9])}</td></tr>`);
    return `${crumbs()}<header class="record-head"><h1><span class="mark">${esc(b.label)}</span>${b.title ? `: ${esc(b.title)}` : ""}</h1>
      <p>${state.j === "state" ? "New York State Legislature" : "New York City Council"}, ${esc(b.session)} session.${b.versions && b.versions.length ? " Versions cited: " + b.versions.map(esc).join(", ") + "." : ""}${b.parts && b.parts.length ? " Budget parts cited: " + b.parts.map(esc).join(", ") + "." : ""}</p>
      <p><a href="${esc(ext)}" target="_blank" rel="noopener">${extLabel}</a></p></header>
      ${new Set(rows.map((r) => r[2])).size > 1 ? `<div class="charts">${C.yearBars({ title: "Lobbying filings on this bill, by year", years: yearList(), isMoney: false, series: [{ label: "Filings", cls: "s-lobby", values: countByYear(rows) }] })}</div>` : ""}
      <section class="block"><h2>Organizations that lobbied this bill</h2><p class="sub">${plural(orgs.size, "organization")}, ${rangeLabel()}. Bill numbers were standardized from what filers typed, so check the source filing when it matters.</p>
        ${table(["Organization", num("Filings"), "Years", "Position", "Officials named", ""], tr, `No lobbying recorded on this bill in ${rangeLabel()}.`)}</section>`;
  }

  const PERIOD_MONTH = { "jan/feb": 0, "mar/apr": 2, "may/june": 4, "may/jun": 4, "july/aug": 6, "jul/aug": 6, "sep/oct": 8, "nov/dec": 10 };
  function periodT(year, period) {
    const p = String(period || "").trim().toLowerCase();
    if (p in PERIOD_MONTH) return year + (PERIOD_MONTH[p] + 1) / 12;
    const n = parseInt(p, 10);
    return n >= 1 && n <= 6 ? year + (2 * n - 1) / 12 : year + 0.5;
  }
  function relTimeline(gifts, iePaths, lob, fund, o) {
    const ys = [...gifts, ...lob, ...fund, ...iePaths.map((p) => p[1])].map((r) => r[2]);
    if (!ys.length) return "";
    const from = Math.min(...ys), to = Math.max(...ys);
    return C.timeline({ title: "Timeline of money and lobbying", from, to, lanes: [
      { label: "Direct contributions", cls: "s-direct", sized: true, events: gifts.map((r) => ({ t: r[2] + 0.5, size: r[3], text: `${r[2]}: ${money(r[3])} from ${ent(r[0]).name}` })) },
      { label: "Super PAC spending", cls: "s-pac", sized: true, events: iePaths.map(([g, sp]) => ({ t: sp[2] + 0.5, size: sp[3], text: `${sp[2]}: ${ent(sp[0]).name} spent ${money(sp[3])} ${sp[4] === "oppose" ? "opposing" : "supporting"} ${o.name}` })) },
      { label: "Lobbying contacts", cls: "s-lobby", events: lob.map((r) => ({ t: periodT(r[2], r[3]), text: `${r[2]} ${r[3]}: lobbying filing${r[4].length ? " on " + r[4].map((b) => bill(b).label).join(", ") : ""}` })) },
      { label: "Lobbyist fundraising", cls: "s-oppose", sized: true, events: fund.map((r) => ({ t: r[2] + 0.5, size: r[3], text: `${r[2]}: ${money(r[3])} ${r[4] || "raised"}` })) },
    ] });
  }

  // ---------------------------------------------------------------- relationship
  function viewRelationship(eid, oid) {
    if (!D.entities[eid] || !D.officials[oid]) return notFound("connection");
    const e = ent(eid), o = off(oid);
    const ids = [eid, ...(e.affiliates || [])];
    const gifts = ids.flatMap((x) => F(D.ix.cByDonor.get(x))).filter((r) => r[1] === oid);
    const lob = F(D.ix.lByClient.get(eid)).concat(F(D.ix.lByFirm.get(eid)).filter((r) => r[0] !== eid)).filter((r) => r[5].includes(oid));
    const iePaths = [];
    for (const g of ids.flatMap((x) => F(D.ix.iecByDonor.get(x)))) for (const s of F(D.ix.iesByCmte.get(g[1]))) if (s[1] === oid) iePaths.push([g, s]);
    const fund = F(D.ix.fByFirm.get(eid)).filter((r) => r[1] === oid);

    const giftRows = gifts.sort((a, b) => a[2] - b[2]).map((r) => `<tr><td>${r[2]}</td><td>${esc(ent(r[0]).name)}</td><td class="num">${money(r[3])}</td><td class="num">${r[4]}</td><td>${srcLink(r[5], "Source records")}</td></tr>`);
    const lobRows = lob.sort((a, b) => a[2] - b[2] || String(a[3]).localeCompare(String(b[3]))).map((r) => `<tr><td>${r[2]} ${esc(r[3])}</td><td>${r[0] === eid ? (r[1] === eid ? "In-house" : esc(ent(r[1]).name)) : "For " + L.e(r[0])}</td><td><div class="chips">${billsWith(r, oid).map((b) => `<span>${chip(b)} ${posTag(r[8] && r[8][b])}</span>`).join("") || '<span class="detail">No bill number given</span>'}</div></td><td>${srcLink(r[9], "Filing")}</td></tr>`);
    const ieRows = iePaths.map(([g, s]) => `<tr><td><div class="path">${esc(ent(g[0]).name)} <span class="arrow" aria-hidden="true">gave ${money(g[3])} to</span> ${L.e(g[1])} <span class="arrow" aria-hidden="true">which ${s[4] === "oppose" ? "spent opposing" : "spent supporting"}</span> ${esc(o.name)} (${money(s[3])})</div></td><td>${g[2]}</td><td>${srcLink(g[5], "Donation")} ${srcLink(s[5], "Spending")}</td></tr>`);

    return `${crumbs()}<header class="record-head"><h1><span class="mark">${esc(e.name)}</span> and ${esc(o.name)}</h1><p>All public filings connecting this organization and this official, ${rangeLabel()}.</p></header>
      <div class="caveat" role="note"><p><b>Read this before drawing conclusions.</b> These records show that money was given or that a lobbyist reported contacting this office. They don’t show that the official agreed to anything, changed a vote, or knew about a donation to a super PAC, which by law can’t coordinate with candidates.</p>
        <p>Names were matched across separate government datasets, and matching can be wrong. Check each source record before citing it. <a href="methodology.html#relationships">How matching works</a>. <a href="methodology.html#corrections">Report an error</a>.</p></div>
      <div class="charts one">${relTimeline(gifts, iePaths, lob, fund, o)}</div>
      <section class="block"><h2>Direct contributions</h2>${table(["Year", "Given by", num("Amount"), num("Contributions"), ""], giftRows, `None in ${rangeLabel()}.`)}</section>
      <section class="block"><h2>Through super PACs</h2>${table(["Path", "Year", "Sources"], ieRows, `None in ${rangeLabel()}.`)}</section>
      <section class="block"><h2>Lobbying filings naming this official</h2>${table(["Period", "Lobbyist", "Bills", ""], lobRows, `None in ${rangeLabel()}.`)}</section>
      ${fund.length ? `<section class="block"><h2>Fundraising and consulting</h2>${table(["Year", num("Amount"), "Activity", ""], fund.map((r) => `<tr><td>${r[2]}</td><td class="num">${money(r[3])}</td><td>${esc(r[4])}</td><td>${srcLink(r[5])}</td></tr>`), "")}</section>` : ""}
      <p>Full record: ${L.e(eid)}. Full record: ${L.o(oid)}.</p>`;
  }

  // State filings pair bills with the officials lobbied on them (r[10]); City filings don't.
  const billsWith = (r, oid) => r[10] ? r[4].filter((b) => (r[10][b] || []).includes(oid)) : r[4];
  const offsFor = (r, b) => r[10] ? (r[10][b] || []) : r[5];

  const shortSess = (s) => { const [a, b] = String(s).split("-"); return b ? `${a}–${b.slice(2)}` : s; };
  const chip = (b) => { const x = bill(b), t = x.title || ""; return `<a href="${hrefFor("b", b)}" title="${esc(t)}">${esc(x.label)} <span class="bt">(${esc(shortSess(x.session))})${t ? " " + esc(t.length > 44 ? t.slice(0, 43).trimEnd() + "…" : t) : ""}</span></a>`; };

  const crumbs = () => `<nav class="crumbs" aria-label="Breadcrumb"><a href="${hrefFor("")}">All ${JUR[state.j]} records</a></nav>`;
  const notFound = (what) => `${crumbs()}<h1>That ${what} isn’t in the ${JUR[state.j]} data</h1><p>It may be on the other tab, or the link may be from an older build. Search from the start page instead.</p>`;

  // ---------------------------------------------------------------- boot
  function boot() {
    document.title = CFG.title;
    $(".brand").innerHTML = `${esc(CFG.title)}<small>${esc(CFG.tagline)}</small>`;
    if (CFG.credit && $("#credit")) $("#credit").textContent = CFG.credit;
    if (window.__DEMO__) document.body.insertAdjacentHTML("afterbegin", `<div class="demo-banner">Demo data: every name below is invented. The live site is built from public filings.</div>`);
    $("#from").addEventListener("change", onYears);
    $("#to").addEventListener("change", onYears);
    window.addEventListener("hashchange", route);
    route();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
