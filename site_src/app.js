/* Relief page: renders data/snapshot.json. All text from data goes through esc(). */
(function () {
  "use strict";

  var PAGE = 50;
  var T = window.TicTime;

  function esc(v) {
    return String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function when(iso) {
    // House rule: the viewer's own zone by default, the zone always named, changed from the Time menu.
    if (!iso) { return ""; }
    if (T) { try { return T.format(iso, { year: true }); } catch (e) { /* fall through */ } }
    try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: "short" }); } catch (e) { return iso; }
  }
  // Publisher dates with no time of day are shown as dates, never shifted into the viewer's zone.
  function day(d) { return d ? String(d).slice(0, 10) : ""; }
  function num(n) { return Number(n || 0).toLocaleString("en-US"); }
  function chf(n) { return "CHF " + Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 }); }
  function pct(x) { return x === null || x === undefined ? "–" : Math.round(x * 100) + "%"; }
  function link(url, label) { return '<a href="' + esc(url) + '" rel="noopener">' + esc(label) + "</a>"; }

  var S, NAMES, appeals = [], notices = [], filtered = [], shown = PAGE, fuAll = false;
  function cname(c) { return NAMES[c] || c; }

  // "Current": IFRC marks it Active and its end date has not passed. IFRC keeps many appeals Active long after
  // their end date; those are listed in the table, marked, but left out of the totals and the funding chart.
  function current(a) { return a.status === "Active" && !a.past_end_date; }

  function tiles() {
    var ea = appeals.filter(function (a) { return a.appeal_type === "Emergency Appeal" && current(a); });
    var req = 0, fund = 0;
    ea.forEach(function (a) { req += a.amount_requested_chf || 0; fund += a.amount_funded_chf || 0; });
    var recent = appeals.filter(function (a) { return a.start_date >= S.recent_from; }).length;
    var past = appeals.filter(function (a) { return a.past_end_date; }).length;
    document.getElementById("tiles").innerHTML = [
      ["Current IFRC appeals", num(appeals.filter(current).length)],
      ["Started in the last 90 days", num(recent)],
      ["Current Emergency Appeals funded", pct(req ? fund / req : null) + " of " + chf(req)],
      ["Marked active but past their end date", num(past)],
      ["WHO notices, last 12 months", num(notices.length)]
    ].map(function (t) { return '<div class="tile"><span class="k">' + esc(t[0]) + '</span><span class="v">' + esc(t[1]) + "</span></div>"; }).join("");
  }

  function unusual() {
    var by = {};
    appeals.forEach(function (a) {
      var pc = a.place_context;
      if (!pc || !pc.appeals_last_90_days) { return; }
      by[a.country] = pc;
    });
    var rows = Object.keys(by).map(function (c) { return [c, by[c]]; })
      .sort(function (x, y) { return x[1].tail_probability - y[1].tail_probability || y[1].appeals_last_90_days - x[1].appeals_last_90_days; });
    var head = "<thead><tr><th scope='col'>Country</th><th scope='col'>Appeals, last 90 days</th><th scope='col'>Average per 90 days before</th><th scope='col'>Chance of this many</th></tr></thead>";
    document.getElementById("unusual").innerHTML = rows.length ? head + "<tbody>" + rows.slice(0, 15).map(function (r) {
      var p = r[1].tail_probability;
      return "<tr><td>" + esc(cname(r[0])) + "</td><td>" + esc(r[1].appeals_last_90_days) + "</td><td>" + esc(r[1].mean_per_90_days.toFixed(2)) +
        "</td><td>" + (p < 0.05 ? '<span class="badge badge-warn">' : "<span>") + esc(p < 0.001 ? "under 0.1%" : (p * 100).toFixed(1) + "%") + "</span></td></tr>";
    }).join("") + "</tbody>" : "<tbody><tr><td class='muted'>No appeal started in the last 90 days.</td></tr></tbody>";
  }

  function funding() {
    var ea = appeals.filter(function (a) { return a.appeal_type === "Emergency Appeal" && current(a) && a.amount_requested_chf > 0; })
      .sort(function (x, y) { return (x.funded_share || 0) - (y.funded_share || 0); });
    var list = fuAll ? ea : ea.slice(0, 15);
    document.getElementById("funding").innerHTML = list.map(function (a) {
      var w = Math.max(0, Math.min(1, a.funded_share || 0)) * 100;
      return '<div class="bar-row"><div class="bar-label">' + link(a.url, a.name) + ' <span class="muted small">' + esc(day(a.start_date)) +
        " to " + esc(day(a.end_date)) + '</span></div>' +
        '<div class="bar" role="img" aria-label="' + esc(pct(a.funded_share) + " funded of " + chf(a.amount_requested_chf)) + '"><span data-w="' + w.toFixed(1) + '"></span></div>' +
        '<div class="bar-val small">' + esc(pct(a.funded_share)) + " of " + esc(chf(a.amount_requested_chf)) + "</div></div>";
    }).join("") || '<p class="muted">No active Emergency Appeal.</p>';
    // The CSP (style-src 'self') blocks style attributes in markup; widths set through the CSSOM are allowed.
    Array.prototype.forEach.call(document.querySelectorAll("#funding .bar span[data-w]"), function (el) {
      el.style.width = el.getAttribute("data-w") + "%";
    });
    var b = document.getElementById("fu-more");
    b.hidden = fuAll || ea.length <= 15;
  }

  function whoTable() {
    var head = "<thead><tr><th scope='col'>Published</th><th scope='col'>Disease</th><th scope='col'>Place</th><th scope='col'>Notices on this country, two years before</th></tr></thead>";
    document.getElementById("who").innerHTML = head + "<tbody>" + notices.map(function (n) {
      var where = (n.countries || []).map(cname).concat(n.regions || []).join(", ") || n.place || "no place stated";
      var prior = n.prior_notices_730_days;
      var pr = prior ? Object.keys(prior).map(function (c) {
        return prior[c] === 0 ? '<span class="badge badge-warn">' + esc(cname(c)) + ": first</span>" : esc(cname(c) + ": " + prior[c]);
      }).join(" ") : '<span class="muted">–</span>';
      return '<tr id="' + esc(n.id) + '"><td>' + esc(day(n.published_day)) + "</td><td>" + link(n.url, n.disease) + "</td><td>" + esc(where) + "</td><td>" + pr + "</td></tr>";
    }).join("") + "</tbody>";
  }

  function applyFilters() {
    var t = document.getElementById("f-type").value, q = document.getElementById("f-q").value.trim().toLowerCase();
    var hidePast = document.getElementById("f-past").checked;
    filtered = appeals.filter(function (a) {
      if (t && a.appeal_type !== t) { return false; }
      if (hidePast && a.past_end_date) { return false; }
      if (!q) { return true; }
      return [a.name, a.code, a.hazard, cname(a.country), a.country].join(" ").toLowerCase().indexOf(q) >= 0;
    });
    shown = PAGE;
    appealTable();
  }

  function appealTable() {
    var head = "<thead><tr><th scope='col'>Started</th><th scope='col'>Appeal</th><th scope='col'>Type</th><th scope='col'>Country</th><th scope='col'>Requested</th><th scope='col'>Funded</th><th scope='col'>People</th><th scope='col'>Ends</th></tr></thead>";
    document.getElementById("appeals").innerHTML = head + "<tbody>" + filtered.slice(0, shown).map(function (a) {
      return '<tr id="' + esc(a.id) + '"><td>' + esc(day(a.start_date)) + "</td><td>" + link(a.url, a.name) + ' <span class="muted small">' + esc(a.code) + "</span></td><td>" +
        esc(a.appeal_type) + "</td><td>" + esc(cname(a.country)) + "</td><td>" + esc(chf(a.amount_requested_chf)) + "</td><td>" + esc(pct(a.funded_share)) + "</td><td>" +
        esc(a.people_targeted ? num(a.people_targeted) : "–") + "</td><td>" + esc(day(a.end_date)) + (a.past_end_date ? ' <span class="badge badge-warn">passed</span>' : "") + "</td></tr>";
    }).join("") + "</tbody>";
    document.getElementById("f-count").textContent = filtered.length + " of " + appeals.length;
    document.getElementById("more").hidden = shown >= filtered.length;
  }

  function lanes() {
    var label = { ifrc: "IFRC GO appeals", who: "WHO Disease Outbreak News" };
    document.getElementById("lanes").innerHTML = "<ul class='small'>" + Object.keys(S.lanes).map(function (k) {
      var l = S.lanes[k];
      var st = l.status === "ok" ? "read " + when(l.fetched_at) + ", " + num(l.items) + " items" :
        l.status === "failed" ? "<strong>not read</strong> on the last run (" + esc(l.error) + ")" + (l.from_previous ? "; showing the last good copy from " + esc(when(l.fetched_at)) : "; nothing to show") : esc(l.status);
      return "<li>" + esc(label[k] || k) + ": " + st + "</li>";
    }).join("") + "</ul>";
  }

  function render() {
    tiles(); unusual(); funding(); whoTable(); applyFilters(); lanes();
    document.getElementById("asof").textContent = "Collected " + when(S.generated_at) + " · method " + S.method_version;
    if (location.hash) { var el = document.getElementById(location.hash.slice(1)); if (el) { el.scrollIntoView(); } }
  }

  fetch("data/snapshot.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (data) {
    S = data; NAMES = data.country_names || {};
    var g = new Date(S.generated_at); g.setUTCDate(g.getUTCDate() - 90);
    S.recent_from = g.toISOString().slice(0, 10);
    appeals = S.items.filter(function (i) { return i.lane === "ifrc"; });
    notices = S.items.filter(function (i) { return i.lane === "who"; });
    ["f-type", "f-q", "f-past"].forEach(function (id) { document.getElementById(id).addEventListener("input", applyFilters); });
    document.getElementById("more").addEventListener("click", function () { shown += PAGE; appealTable(); });
    document.getElementById("fu-more").addEventListener("click", function () { fuAll = true; funding(); });
    if (T && T.mountSettings) { T.mountSettings(document.getElementById("time-settings")); }
    if (T && T.onChange) { T.onChange(render); }
    render();
  }).catch(function (e) {
    document.getElementById("asof").textContent = "Could not load the data: " + e;
  });
})();
