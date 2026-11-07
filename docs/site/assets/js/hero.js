/* Hero: barras de ocupação, chip de alerta, pergunta digitada e veículos ilustrativos sobre as rotas.
   Tudo vem do snapshot sintético; os veículos são só ilustração (não há GPS). */
(function () {
  "use strict";
  var IF = window.IF, $ = IF.$, D = window.INFOFROTA_SNAPSHOT;
  if (!D) return;

  /* barras: as 4 linhas com maior ocupação média na hora de pico */
  var top = D.linhas.map(function (l) {
    return { n: l.numero, v: Math.max.apply(null, l.horas.filter(function (x) { return x != null; })) };
  }).sort(function (a, b) { return b.v - a.v; }).slice(0, 4);
  var bars = $("#heroBars");
  top.forEach(function (l) {
    bars.appendChild(IF.el("li", null, [
      IF.el("span", { text: l.n }),
      IF.el("span", { class: "track" }, IF.el("i", { class: "fill", style: { "--w": Math.min(l.v, 100) + "%" } })),
      IF.el("b", { text: Math.round(l.v) + "%" })
    ]));
  });

  /* alerta mais recente com 90% ou mais */
  var a = D.alertas_recentes.filter(function (x) { return x.percentual >= 90; })[0];
  if (a) {
    $("#heroAlertTitle").textContent = "Alerta crítico · linha " + a.linha;
    $("#heroAlertMeta").textContent = IF.pct(a.percentual) + " · " + a.parada;
  } else $("#heroAlert").classList.add("hidden");

  /* pergunta digitada alternando entre os cenários respondíveis */
  var qs = D.cenarios.filter(function (c) { return c.sql && !c.bloqueado; }).slice(0, 3);
  var out = $("#heroTypedText"), sqlBox = $("#heroSql"), qi = 0, alive = true; // sem pausa por aba: timers em segundo plano já são limitados pelo navegador
  function oneLine(sql) { return sql.replace(/\s+/g, " ").slice(0, 96) + (sql.length > 96 ? "…" : ""); }
  function still() { out.textContent = qs[0].pergunta; sqlBox.textContent = oneLine(qs[0].sql); }
  async function loop() {
    while (alive) {
      var c = qs[qi % qs.length]; qi++;
      sqlBox.textContent = ""; out.textContent = "";
      for (var i = 1; i <= c.pergunta.length && alive; i++) { out.textContent = c.pergunta.slice(0, i); await IF.sleep(34); }
      await IF.sleep(450);
      var s = oneLine(c.sql);
      for (var j = 8; j <= s.length && alive; j += 8) { sqlBox.textContent = s.slice(0, j); await IF.sleep(26); }
      sqlBox.textContent = s;
      await IF.sleep(3400);
    }
  }
  if (IF.reduced()) still(); else loop();

  /* veículos ilustrativos andando nas rotas */
  var svg = $("#stage svg"), routes = ["route-a", "route-b", "route-c"].map(function (id) { return document.getElementById(id); });
  var vehs = routes.map(function (p, i) {
    var len = p.getTotalLength();
    var trail = IF.el("path", { class: "net__trail net__veh--" + "abc"[i], d: p.getAttribute("d"), stroke: "currentColor" });
    var c = IF.el("circle", { r: 6, class: "net__veh net__veh--" + "abc"[i] });
    svg.appendChild(trail); svg.appendChild(c);
    return { p: p, len: len, c: c, t: [0.18, 0.52, 0.8][i], v: [0.011, 0.0085, 0.0098][i], trail: trail };
  });
  vehs.forEach(function (v) { v.trail.style.stroke = getComputedStyle(v.c).fill; v.trail.style.strokeDasharray = "0 " + v.len; });
  function place(v) {
    var pt = v.p.getPointAtLength(v.t * v.len);
    v.c.setAttribute("cx", pt.x); v.c.setAttribute("cy", pt.y);
    v.trail.style.strokeDasharray = Math.max(0, v.t * v.len) + " " + v.len;
  }
  vehs.forEach(place);
  var raf = 0, last = 0, inView = true;
  function tick(ts) {
    var dt = Math.min(48, ts - last) / 16.7; last = ts;
    vehs.forEach(function (v) { v.t += v.v * dt * 0.1; if (v.t > 1) v.t = 0.02; place(v); });
    raf = inView && !document.hidden ? requestAnimationFrame(tick) : 0;
  }
  function start() { if (!raf && !IF.reduced()) { last = performance.now(); raf = requestAnimationFrame(tick); } }
  if (!IF.reduced()) {
    new IntersectionObserver(function (es) { inView = es[0].isIntersecting; if (inView) start(); }).observe($("#stage"));
    document.addEventListener("visibilitychange", start);
    start();
  }
  document.addEventListener("if:tema", function () { vehs.forEach(function (v) { v.trail.style.stroke = getComputedStyle(v.c).fill; }); });

  /* paralaxe leve: só com ponteiro fino e sem preferência por menos movimento */
  var stage = $("#stage");
  if (!IF.reduced() && matchMedia("(hover: hover) and (pointer: fine)").matches) {
    var layers = IF.$$("[data-depth]", stage);
    stage.addEventListener("pointermove", function (e) {
      var r = stage.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      layers.forEach(function (l) {
        var d = +l.dataset.depth;
        l.style.setProperty("--px", (-x * d).toFixed(1) + "px");
        l.style.setProperty("--py", (-y * d).toFixed(1) + "px");
      });
    });
    stage.addEventListener("pointerleave", function () {
      layers.forEach(function (l) { l.style.setProperty("--px", "0px"); l.style.setProperty("--py", "0px"); });
    });
  }
})();
