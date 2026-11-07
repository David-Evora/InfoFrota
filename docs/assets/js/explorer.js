/* Explorador de funcionalidades: categoria, situação e busca de texto; cada cartão abre um painel com evidências. */
(function () {
  "use strict";
  var IF = window.IF, F = window.IF_FEATURES, el = IF.el;
  if (!F) return;
  var REPO = "https://github.com/David-Evora/InfoFrota/blob/main/";
  var st = { cat: "all", status: "all", q: "" };
  var grid = IF.$("#featGrid"), count = IF.$("#featCount"), empty = IF.$("#featEmpty"), input = IF.$("#featSearch");
  var catById = {}; F.cats.forEach(function (c) { catById[c.id] = c; });

  function norm(s) { return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  var hay = F.items.map(function (i) { return norm([i.titulo, i.resumo, i.detalhe, catById[i.cat].nome].join(" ")); });

  function match(i, k) {
    return (st.cat === "all" || i.cat === st.cat) && (st.status === "all" || i.status === st.status) && (!st.q || hay[k].indexOf(st.q) > -1);
  }
  /* contagem de cada filtro considera os OUTROS filtros ativos */
  function countFor(kind, val) {
    return F.items.filter(function (i, k) {
      var c = kind === "cat" ? val : st.cat, s = kind === "status" ? val : st.status;
      return (c === "all" || i.cat === c) && (s === "all" || i.status === s) && (!st.q || hay[k].indexOf(st.q) > -1);
    }).length;
  }

  function pressedGroup(host, kind, opts, withCount) {
    IF.clear(host);
    opts.forEach(function (o) {
      var b = el("button", { type: "button", "aria-pressed": String(st[kind] === o.id), "data-v": o.id }, [
        el("span", { text: o.nome }), withCount ? el("span", { class: "n", text: countFor(kind, o.id) }) : null
      ]);
      b.addEventListener("click", function () { st[kind] = o.id; render(); var nb = host.querySelector('[data-v="' + o.id + '"]'); if (nb) nb.focus(); }); // render recria os botões: devolve o foco
      host.appendChild(b);
    });
  }

  function glyph(id) {
    var h = 0; for (var i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    var g = el("svg", { class: "fcard__glyph", viewBox: "0 0 120 90", "aria-hidden": "true", fill: "none", stroke: "currentColor", "stroke-width": "1.5" });
    for (var k = 0; k < 6; k++) {
      h = (h * 1103515245 + 12345) >>> 0;
      var y = 20 + (h % 60);
      g.appendChild(el("rect", { x: 8 + k * 18, y: y, width: 10, height: 90 - y, rx: 2 }));
    }
    return g;
  }

  function card(i) {
    var c = el("article", { class: "fcard" + (i.wide ? " fcard--wide" : "") + (i.status === "plan" ? " fcard--plan" : "") });
    var open = el("button", { class: "fcard__open", type: "button", text: i.titulo, "aria-haspopup": "dialog" });
    open.addEventListener("click", function () { detail(i, open); });
    c.appendChild(el("div", { class: "fcard__top" }, [
      el("span", { class: "fcard__ico" }, IF.icon(i.icon)),
      el("span", { class: "fcard__cat", text: catById[i.cat].nome })
    ]));
    c.appendChild(el("h3", null, open));
    c.appendChild(el("p", { text: i.resumo }));
    c.appendChild(el("span", { class: "badge badge--" + i.status, text: F.status[i.status] }));
    c.appendChild(el("span", { class: "fcard__more" }, ["Ver evidências", IF.icon("i-arrow-up-right")]));
    c.appendChild(glyph(i.id));
    return c;
  }

  var NOTA = {
    impl: "Implementado: o código está no repositório.",
    exp: "Experimental: existe, mas os resultados são de experimento controlado, não de operação real.",
    val: "Em validação: o código existe, mas o comportamento em execução real ainda precisa ser confirmado.",
    plan: "Planejado: ainda não há implementação neste repositório."
  };
  var CORES = { impl: "var(--ok)", exp: "var(--accent-2)", val: "var(--warn)", plan: "var(--text-3)" };

  function detail(i, opener) {
    var dlg = IF.$("#featureDialog"), body = IF.$("#fdBody");
    IF.clear(body);
    var box = el("div", { class: "fd" }, [
      el("div", { class: "fd__meta" }, [el("span", { class: "badge badge--" + i.status, text: F.status[i.status] }), el("span", { class: "eyebrow-sm", text: catById[i.cat].nome })]),
      el("h3", { id: "fdTitle", text: i.titulo }),
      el("p", { text: i.resumo }),
      el("p", { class: "muted", text: i.detalhe }),
      el("h4", { class: "fd__h", text: "Evidências no repositório" }),
      el("ul", { class: "evid" }, i.evidence.map(function (p) {
        var dir = !/\.[a-z0-9]+$/i.test(p);
        return el("li", null, el("a", { href: REPO.replace("/blob/", dir ? "/tree/" : "/blob/") + p, target: "_blank", rel: "noopener" }, [el("span", { text: p }), IF.icon("i-arrow-up-right")]));
      })),
      el("p", { class: "fd__status", style: { "--c": CORES[i.status] }, text: NOTA[i.status] })
    ]);
    body.appendChild(box);
    IF.openDialog(dlg);
  }

  function render() {
    pressedGroup(IF.$("#featCats"), "cat", [{ id: "all", nome: "Todas" }].concat(F.cats), true);
    pressedGroup(IF.$("#featStatus"), "status", [{ id: "all", nome: "Todas" }].concat(Object.keys(F.status).map(function (k) { return { id: k, nome: F.status[k] }; })), false);
    IF.clear(grid);
    var shown = F.items.filter(match);
    shown.forEach(function (i) { grid.appendChild(card(i)); });
    count.textContent = shown.length + " de " + F.items.length + " funcionalidades";
    empty.classList.toggle("hidden", shown.length > 0);
  }

  input.addEventListener("input", function () { st.q = norm(input.value.trim()); render(); });
  IF.$("#featReset").addEventListener("click", function () { st = { cat: "all", status: "all", q: "" }; input.value = ""; render(); input.focus(); });
  render();
})();
