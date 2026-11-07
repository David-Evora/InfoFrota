/* Introdução: 48 leituras reais do snapshot (4 linhas × 12 horas) que se dispersam, agrupam e viram tabela.
   O estado acompanha o passo do texto que cruza o meio da janela. */
(function () {
  "use strict";
  var IF = window.IF, $ = IF.$, D = window.INFOFROTA_SNAPSHOT;
  var svg = $("#introViz");
  if (!svg || !D) return;

  var HORAS = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17];
  var linhas = D.linhas.slice().sort(function (a, b) { return b.maximo - a.maximo; }).slice(0, 4);
  var W = 30, H = 14;

  function seed(n) { var s = n * 9301 + 49297; return function () { s = (s * 9301 + 49297) % 233280; return s / 233280; }; }
  var rnd = seed(7);

  function cor(v) { return v >= 90 ? "var(--crit)" : v >= 75 ? "var(--warn)" : "var(--text-3)"; }

  /* camadas: fundo das linhas da tabela, destaque, registros, rótulos */
  var gBg = IF.el("g"), gRec = IF.el("g"), gLab = IF.el("g");
  svg.appendChild(gBg); svg.appendChild(gRec); svg.appendChild(gLab);

  var recs = [], pos = { 0: [], 1: [], 2: [] };
  var origem = [[40, 64], [290, 64], [40, 236], [290, 236]];
  var hl = -1, hv = 0;

  linhas.forEach(function (l, li) {
    HORAS.forEach(function (h, hi) {
      var v = l.picos[h] == null ? 0 : l.picos[h];
      if (v > hv) { hv = v; hl = li * 12 + hi; }
      recs.push({ v: v });
      pos[0].push([14 + rnd() * (520 - W - 28), 14 + rnd() * (400 - H - 28), (rnd() - .5) * 70]);
      pos[1].push([origem[li][0] + (hi % 4) * 40, origem[li][1] + Math.floor(hi / 4) * 26, 0]);
      pos[2].push([92 + hi * 35, 78 + li * 58 + 14, 0]);
    });
  });
  recs.forEach(function (r, i) {
    r.n = IF.el("rect", { class: "rec", width: W, height: H, rx: 3 });
    r.n.style.fill = cor(r.v);
    r.n.style.opacity = r.v >= 75 ? 1 : .55;
    r.n.style.transformBox = "fill-box";
    r.n.style.transformOrigin = "center";
    gRec.appendChild(r.n);
  });

  /* tabela: faixas das linhas e destaque do maior pico */
  linhas.forEach(function (l, li) {
    gBg.appendChild(IF.el("rect", { class: "rowbg", x: 16, y: 70 + li * 58, width: 488, height: 44, rx: 8 }));
  });
  var hy = 70 + Math.floor(hl / 12) * 58;
  gBg.appendChild(IF.el("rect", { class: "rowhl", x: 16, y: hy, width: 488, height: 44, rx: 8 }));

  /* rótulos */
  linhas.forEach(function (l, li) {
    gLab.appendChild(IF.el("text", { class: "vlabel vlabel--g", x: origem[li][0], y: origem[li][1] - 12, text: "LINHA " + l.numero }));
    gLab.appendChild(IF.el("text", { class: "vlabel vlabel--t" + (li * 12 <= hl && hl < li * 12 + 12 ? " vlabel--crit" : ""), x: 28, y: 70 + li * 58 + 27, text: l.numero }));
  });
  [0, 5, 11].forEach(function (hi) {
    gLab.appendChild(IF.el("text", { class: "vlabel vlabel--t", x: 92 + hi * 35, y: 56, text: IF.hora(HORAS[hi]) }));
  });
  gLab.appendChild(IF.el("text", { class: "vlabel vlabel--t vlabel--crit", x: 92 + (hl % 12) * 35 - 4, y: hy + 62, text: "pico " + IF.pct(hv) }));

  var legendas = [
    "Registros dispersos · ilustração com leituras sintéticas",
    "Agrupados por linha · contexto recuperado",
    "Tabela com o maior pico destacado · dados sintéticos"
  ];
  var cap = $("#introCaption"), cur = -1;
  function show(s) {
    if (s === cur) return; cur = s;
    recs.forEach(function (r, i) {
      var p = pos[s][i];
      r.n.style.transform = "translate(" + p[0] + "px," + p[1] + "px) rotate(" + p[2] + "deg)";
      r.n.style.transitionDelay = IF.reduced() ? "0s" : (i % 12) * 14 + "ms";
    });
    svg.classList.toggle("show-1", s === 1);
    svg.classList.toggle("show-2", s === 2);
    cap.textContent = legendas[s];
    IF.$$(".step").forEach(function (n, i) { n.classList.toggle("is-active", i === s); });
  }
  show(0);

  /* passo ativo = o que cruza ~45% da altura da janela */
  var steps = IF.$$(".step");
  function onScroll() {
    var mid = innerHeight * 0.45, best = 0, d = 1e9;
    steps.forEach(function (n, i) {
      var r = n.getBoundingClientRect();
      var dist = r.top <= mid && r.bottom >= mid ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid));
      if (dist < d) { d = dist; best = i; }
    });
    show(best);
  }
  var tick = false;
  addEventListener("scroll", function () { if (!tick) { tick = true; requestAnimationFrame(function () { tick = false; onScroll(); }); } }, { passive: true });
  addEventListener("resize", onScroll);
  onScroll();
})();
