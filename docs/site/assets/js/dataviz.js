/* Inteligência de dados: gráfico principal por hora, indicadores, mapa de calor e ranking.
   Tudo calculado em scripts/build_site_snapshot.py a partir do banco SINTÉTICO. SVG feito à mão, sem biblioteca. */
(function () {
  "use strict";
  var IF = window.IF, el = IF.el, D = window.INFOFROTA_SNAPSHOT;
  if (!D) return;

  var sel = "all";                     // "all" ou número da linha
  var byNum = {}; D.linhas.forEach(function (l) { byNum[l.numero] = l; });

  IF.$("#dataTag").textContent = "Dados sintéticos · " + IF.dataCurta(D.periodo[0]) + " a " + IF.dataCurta(D.periodo[1]) + " · " + D.linhas_monitoradas + " linhas · gerados por scripts/generate_data.py";

  /* ---------- série do gráfico principal ---------- */
  function serie(num) {
    var avg = [], max = [];
    for (var h = 0; h < 24; h++) {
      var vs = [], ps = [];
      (num === "all" ? D.linhas : [byNum[num]]).forEach(function (l) {
        if (l.horas[h] != null) vs.push(l.horas[h]);
        if (l.picos[h] != null) ps.push(l.picos[h]);
      });
      avg.push(vs.length ? vs.reduce(function (a, b) { return a + b; }, 0) / vs.length : null);
      max.push(ps.length ? Math.max.apply(null, ps) : null);
    }
    return { avg: avg, max: max };
  }

  /* trechos contínuos (a série tem lacunas nas horas sem operação) */
  function runs(arr) {
    var out = [], cur = [];
    arr.forEach(function (v, i) { if (v == null) { if (cur.length) out.push(cur); cur = []; } else cur.push([i, v]); });
    if (cur.length) out.push(cur);
    return out;
  }

  var chartBox = IF.$("#mainChart"), tip = el("div", { class: "tip", role: "presentation" });
  function drawMain() {
    var w = Math.max(280, Math.round(chartBox.clientWidth || 700)), h = w < 520 ? 250 : 320;
    var m = { l: 38, r: 10, t: 10, b: 26 }, iw = w - m.l - m.r, ih = h - m.t - m.b;
    var s = serie(sel), top = Math.max(100, Math.ceil(Math.max.apply(null, s.max.filter(function (x) { return x != null; })) / 10) * 10);
    var X = function (i) { return m.l + (i + .5) * iw / 24; }, Y = function (v) { return m.t + ih - v / top * ih; };

    var svg = el("svg", { viewBox: "0 0 " + w + " " + h, role: "img", "aria-label": "Ocupação por hora do dia: média e maior leitura. " + (sel === "all" ? "Todas as linhas." : "Linha " + sel + ".") });
    for (var g = 0; g <= top; g += 25) {
      svg.appendChild(el("line", { class: "gl", x1: m.l, x2: w - m.r, y1: Y(g), y2: Y(g) }));
      svg.appendChild(el("text", { x: m.l - 8, y: Y(g) + 4, "text-anchor": "end", text: g + "%" }));
    }
    svg.appendChild(el("line", { class: "th-w", x1: m.l, x2: w - m.r, y1: Y(75), y2: Y(75) }));
    svg.appendChild(el("line", { class: "th-c", x1: m.l, x2: w - m.r, y1: Y(90), y2: Y(90) }));
    for (var hr = 0; hr < 24; hr += (w < 520 ? 6 : 3)) svg.appendChild(el("text", { x: X(hr), y: h - 6, "text-anchor": "middle", text: IF.hora(hr) }));

    runs(s.max).forEach(function (r) {
      var d = "M" + X(r[0][0]) + "," + Y(0) + r.map(function (p) { return "L" + X(p[0]) + "," + Y(p[1]); }).join("") + "L" + X(r[r.length - 1][0]) + "," + Y(0) + "Z";
      svg.appendChild(el("path", { class: "area-max", d: d }));
    });
    var avgPath = el("path", { class: "ln-avg", d: runs(s.avg).map(function (r) { return r.map(function (p, k) { return (k ? "L" : "M") + X(p[0]) + "," + Y(p[1]); }).join(""); }).join("") });
    svg.appendChild(avgPath);

    var cursor = el("line", { class: "cursor", y1: m.t, y2: m.t + ih }), dot = el("circle", { class: "cdot", r: 5 });
    svg.appendChild(cursor); svg.appendChild(dot);
    for (var i = 0; i < 24; i++) (function (i) {
      var r = el("rect", { class: "hit", x: X(i) - iw / 48, y: m.t, width: iw / 24, height: ih });
      var show = function () {
        if (s.avg[i] == null) { hide(); return; }
        cursor.setAttribute("x1", X(i)); cursor.setAttribute("x2", X(i)); cursor.style.opacity = 1;
        dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(s.avg[i])); dot.style.opacity = 1;
        IF.clear(tip);
        tip.appendChild(el("div", { text: IF.hora(i) + " · " + (sel === "all" ? "todas as linhas" : "linha " + sel) }));
        tip.appendChild(el("div", { text: "média " + IF.pct(s.avg[i]) }));
        tip.appendChild(el("div", { text: "maior leitura " + IF.pct(s.max[i]) }));
        var box = chartBox.getBoundingClientRect(), px = X(i) * (box.width / w);
        tip.style.left = Math.min(Math.max(px + 12, 4), box.width - 150) + "px"; tip.style.top = "8px"; tip.style.opacity = 1;
      };
      r.addEventListener("pointerenter", show); r.addEventListener("pointermove", show);
      r.addEventListener("click", show);
      svg.appendChild(r);
    })(i);
    svg.addEventListener("pointerleave", hide);
    function hide() { cursor.style.opacity = 0; dot.style.opacity = 0; tip.style.opacity = 0; }

    /* equivalente textual e acessível (leitor de tela) */
    var tb = el("table", { class: "sr" }, [
      el("caption", { text: "Ocupação por hora (%)" }),
      el("thead", null, el("tr", null, ["Hora", "Média", "Maior leitura"].map(function (t) { return el("th", { scope: "col", text: t }); }))),
      el("tbody", null, s.avg.map(function (v, i) { return v == null ? null : el("tr", null, [el("td", { text: IF.hora(i) }), el("td", { text: IF.pct(v) }), el("td", { text: IF.pct(s.max[i]) })]); }))
    ]);

    IF.clear(chartBox); chartBox.appendChild(svg); chartBox.appendChild(tb); chartBox.appendChild(tip);
    if (!IF.reduced() && avgPath.getTotalLength) {
      var L = avgPath.getTotalLength();
      avgPath.style.strokeDasharray = L; avgPath.style.strokeDashoffset = L;
      avgPath.getBoundingClientRect();
      avgPath.style.transition = "stroke-dashoffset 1.1s cubic-bezier(.22,1,.36,1)"; avgPath.style.strokeDashoffset = 0;
    }
  }

  /* ---------- seleção compartilhada (pílulas, ranking, gráfico) ---------- */
  var pillLines = D.linhas.slice().sort(function (a, b) { return b.critico - a.critico; }).slice(0, 5).map(function (l) { return l.numero; });
  function drawPills() {
    var host = IF.$("#linePills"); IF.clear(host);
    ["all"].concat(pillLines).forEach(function (n) {
      var b = el("button", { type: "button", "aria-pressed": String(sel === n), text: n === "all" ? "Todas" : n });
      b.addEventListener("click", function () { choose(n); });
      host.appendChild(b);
    });
  }
  function choose(n) {
    sel = n;
    if (n !== "all" && pillLines.indexOf(n) < 0) { pillLines.push(n); if (pillLines.length > 7) pillLines.splice(5, 1); }
    IF.$("#mainTitle").textContent = n === "all" ? "Todas as linhas" : "Linha " + n + " · " + byNum[n].nome.toLowerCase().replace(/(^|\s|\/)\S/g, function (c) { return c.toUpperCase(); });
    drawPills(); drawMain(); drawRank();
  }

  /* ---------- indicadores ---------- */
  var T = D.totais, ratio = IF.$("#kpiRatio i");
  IF.$("#kpiAtt").textContent = IF.n0(T.atencao);
  IF.$("#kpiPct").textContent = IF.pct(T.critico / T.alertas * 100);
  var kc = IF.$("#kpiCrit");
  kc.textContent = IF.n0(T.critico);
  IF.whenVisible(kc, function () {
    ratio.style.setProperty("--w", (T.critico / T.alertas * 100) + "%");
    if (IF.reduced()) return;
    var t0 = performance.now();
    (function step(t) { var p = Math.min(1, (t - t0) / 1100), e = 1 - Math.pow(1 - p, 3); kc.textContent = IF.n0(Math.round(T.critico * e)); if (p < 1) requestAnimationFrame(step); })(t0);
  });

  var vals = D.alertas_por_dia.map(function (d) { return d.critico; }), mx = Math.max.apply(null, vals), mn = Math.min.apply(null, vals);
  var pts = vals.map(function (v, i) { return [i / (vals.length - 1) * 300, 56 - (v - mn) / (mx - mn || 1) * 48]; });
  var line = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); }).join("");
  var pk = D.alertas_por_dia.reduce(function (a, d) { return d.critico > a.critico ? d : a; });
  var lo = D.alertas_por_dia.reduce(function (a, d) { return d.critico < a.critico ? d : a; });
  var pkEl = el("p", { class: "muted", text: "Dia com mais críticos: " + IF.dataCurta(pk.data) + " (" + pk.critico + "). Dia mais calmo: " + IF.dataCurta(lo.data) + " (" + lo.critico + ")." });
  IF.$("#kpiSpark").parentNode.insertBefore(pkEl, IF.$("#kpiSpark"));
  IF.$("#kpiSpark").appendChild(el("svg", { viewBox: "0 0 300 64", preserveAspectRatio: "none", role: "img", "aria-label": "Alertas críticos por dia, de " + mn + " a " + mx }, [
    el("path", { class: "sa", d: line + "L300,64L0,64Z" }),
    el("path", { d: line, "vector-effect": "non-scaling-stroke" })
  ]));

  /* ---------- mapa de calor ---------- */
  var heat = IF.$("#heat"), HV = D.mapa_calor.valores, hmax = Math.max.apply(null, HV.map(function (r) { return Math.max.apply(null, r); }));
  var hnote = IF.$("#heatNote"), best = { d: 0, h: 0, v: -1 };
  heat.setAttribute("role", "img");
  heat.appendChild(el("span"));
  for (var hh = 0; hh < 24; hh++) heat.appendChild(el("span", { class: "hh", "aria-hidden": "true", text: hh }));
  D.mapa_calor.dias.forEach(function (dia, d) {
    heat.appendChild(el("span", { class: "hl", "aria-hidden": "true", text: dia.slice(0, 3) }));
    HV[d].forEach(function (v, h) {
      if (v > best.v) best = { d: d, h: h, v: v };
      var c = el("span", { class: "hc", style: { "--p": Math.round(v / hmax * 100) + "%" }, title: dia + " " + IF.hora(h) + ": " + IF.pct(v) });
      c.addEventListener("click", function () { hnote.textContent = dia + ", " + IF.hora(h) + ": ocupação média " + IF.pct(v) + "."; });
      heat.appendChild(c);
    });
  });
  heat.parentNode.insertBefore(el("div", { class: "legend", "aria-hidden": "true", style: { "margin-top": "14px" } }, [
    el("span", { text: "menos" }), el("span", { style: { width: "120px", height: "8px", "border-radius": "4px", background: "linear-gradient(90deg, var(--surface-2), var(--accent-2))" } }), el("span", { text: "mais ocupação média" })
  ]), hnote);
  var DEF_HEAT = "Maior ocupação média: " + D.mapa_calor.dias[best.d] + ", às " + IF.hora(best.h) + " (" + IF.pct(best.v) + "). Toque ou passe o mouse sobre uma célula para ler o valor.";
  hnote.textContent = DEF_HEAT;
  heat.setAttribute("aria-label", "Mapa de calor da ocupação média por dia da semana e hora. " + DEF_HEAT);

  /* ---------- ranking ---------- */
  var SORTS = {
    critico: { nome: "Críticos", f: function (l) { return l.critico; }, fmt: IF.n0 },
    atencao: { nome: "Atenção", f: function (l) { return l.atencao; }, fmt: IF.n0 },
    maximo: { nome: "Pico", f: function (l) { return l.maximo; }, fmt: IF.pct },
    media: { nome: "Média", f: function (l) { return l.media; }, fmt: IF.pct }
  }, sort = "critico";
  function drawRank() {
    var S = SORTS[sort], ls = D.linhas.slice().sort(function (a, b) { return S.f(b) - S.f(a); }).slice(0, 6), top = S.f(ls[0]) || 1, host = IF.$("#rank");
    var first = !host.firstChild;
    IF.clear(host);
    ls.forEach(function (l, i) {
      var tr = el("i", { style: { "--w": first && !IF.reduced() ? "0%" : (S.f(l) / top * 100) + "%" } });
      tr.dataset.w = (S.f(l) / top * 100) + "%";
      var b = el("button", { type: "button", "aria-pressed": String(sel === l.numero), title: l.nome }, [
        el("span", { class: "pos", text: i + 1 }), el("span", { class: "num", text: l.numero }), el("span", { class: "tr" }, tr), el("span", { class: "val", text: S.fmt(S.f(l)) })
      ]);
      b.addEventListener("click", function () { choose(sel === l.numero ? "all" : l.numero); });
      host.appendChild(el("li", null, b));
    });
    if (first && !IF.reduced()) IF.whenVisible(host, function () { requestAnimationFrame(function () { IF.$$(".tr i", host).forEach(function (i) { i.style.setProperty("--w", i.dataset.w); }); }); });
  }
  var rs = IF.$("#rankSort");
  Object.keys(SORTS).forEach(function (k) {
    var b = el("button", { type: "button", "aria-pressed": String(k === sort), text: SORTS[k].nome });
    b.addEventListener("click", function () { sort = k; IF.$$("button", rs).forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); drawRank(); });
    rs.appendChild(b);
  });

  drawPills(); drawMain(); drawRank();
  var rt; new ResizeObserver(function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.abs((chartBox.clientWidth || 0) - lastW) > 8) drawMain(); lastW = chartBox.clientWidth; }, 120); }).observe(chartBox);
  var lastW = chartBox.clientWidth;
  document.addEventListener("if:tema", function () { /* as cores vêm de variáveis CSS: nada a redesenhar */ });
})();
