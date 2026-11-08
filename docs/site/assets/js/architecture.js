/* Arquitetura interativa. Os nós e as arestas espelham o repositório; o que só existe como ideia fica tracejado ("em estudo"). */
(function () {
  "use strict";
  var IF = window.IF, el = IF.el, REPO = "https://github.com/David-Evora/InfoFrota/blob/main/";
  var host = IF.$("#arch"), wires = IF.$("#archWires"), insp = IF.$("#archInspector");
  if (!host) return;

  var N = {
    gen: { row: "A", t: "Gerador sintético", s: "scripts/generate_data.py", i: "i-zap", st: "exp", layer: "Dados",
      d: "Cria o banco SQLite com ocupação por hora, clima, calendário e alertas. Tudo é simulado; nada vem de operação real.", f: ["scripts/generate_data.py", "db/schema.sql"] },
    csv: { row: "A", t: "Rótulos CETURB-ES", s: "data/linhas_ceturbes.csv", i: "i-route", st: "impl", layer: "Dados",
      d: "CSV aberto (CC0) usado só para nomear as linhas. Horários, ocupação e alertas continuam sintéticos.", f: ["data/linhas_ceturbes.csv"] },
    db: { row: "B", t: "SQLite somente leitura", s: "infofrota_ai/db.py", i: "i-database", st: "impl", layer: "Núcleo",
      d: "Toda consulta passa pela guarda de três camadas: instrução única SELECT/WITH, authorizer do SQLite e conexão mode=ro, com limite de 200 linhas e 5 segundos.", f: ["infofrota_ai/db.py", "db/schema.sql"] },
    rag: { row: "B", t: "RAG de esquema (BM25)", s: "infofrota_ai/rag.py", i: "i-search", st: "impl", layer: "Núcleo",
      d: "Recupera as tabelas, os valores válidos e as regras que importam para a pergunta e as entrega ao prompt.", f: ["infofrota_ai/rag.py", "tests/test_rag.py"] },
    api: { row: "B", t: "API FastAPI", s: "infofrota_ai/api.py", i: "i-server", st: "impl", layer: "Núcleo",
      d: "Rotas /saude, /perguntar, /alertas e /resumo, com chave opcional (X-API-Key), limite por IP e CORS opcional. Serve também o único site do projeto na raiz.", f: ["infofrota_ai/api.py", "tests/test_api.py"] },
    llm: { row: "B", t: "Provedor de LLM", s: "infofrota_ai/llm.py", i: "i-bot", st: "impl", layer: "Núcleo",
      d: "Anthropic, API compatível com OpenAI (como a Groq) ou modelo local com Hugging Face e PEFT. A chave fica no backend.", f: ["infofrota_ai/llm.py", "infofrota_ai/hf_llm.py"] },
    n8n: { row: "C", t: "Workflow n8n", s: "n8n/alerta-critico.json", i: "i-workflow", st: "val", layer: "Consumo e automação",
      d: "A cada cinco minutos busca alertas críticos na API e avisa só os novos. A persistência da deduplicação ainda está em validação.", f: ["n8n/alerta-critico.json", "compose.yaml"] },
    hook: { row: "C", t: "Webhook Discord ou Slack", s: "configurado no n8n", i: "i-webhook", st: "impl", layer: "Consumo e automação",
      d: "Destino da notificação. A URL é configurada na instância do n8n e não está no repositório.", f: ["n8n/alerta-critico.json"] },
    ui: { row: "C", t: "Site de apresentação", s: "docs/site/index.html", i: "i-layout-dashboard", st: "impl", layer: "Consumo e automação",
      d: "Único frontend do projeto: página estática com demonstrações e arquitetura interativa, servida em / pela API e publicada pelo GitHub Pages.", f: ["docs/site/index.html", "docs/site/assets/js/core.js", "docs/site/README.md"] },
    emb: { row: "D", t: "Captação embarcada", s: "conceito", i: "i-cpu", st: "plan", layer: "Em estudo", ghost: true,
      d: "Ideia de estimar a ocupação dentro do veículo por visão computacional. Sem firmware, modelo ou hardware neste repositório.", f: ["docs/architecture.md"] },
    real: { row: "D", t: "Dados operacionais reais", s: "depende de autorização", i: "i-globe", st: "plan", layer: "Em estudo", ghost: true,
      d: "Integração com fontes reais somente com autorização de quem detém os dados. Hoje não existe nenhuma.", f: ["docs/architecture.md"] }
  };
  var EDGES = [["gen", "db"], ["csv", "db"], ["db", "rag"], ["rag", "api"], ["db", "api"], ["api", "llm"], ["n8n", "api"], ["n8n", "hook"], ["ui", "api"], ["emb", "db", true], ["real", "db", true]];
  var STATUS = { impl: "Implementado", exp: "Experimental", val: "Em validação", plan: "Planejado" };
  var rowEl = { A: IF.$("#archA"), B: IF.$("#archB"), C: IF.$("#archC"), D: IF.$("#archD") };
  var nodes = {}, sel = "api";

  Object.keys(N).forEach(function (k) {
    var n = N[k];
    var b = el("button", { type: "button", class: "anode" + (n.ghost ? " anode--ghost" : ""), "aria-pressed": "false", "data-k": k }, [
      el("span", { class: "ai" }, IF.icon(n.i)), el("b", { text: n.t }), el("small", { text: n.s })
    ]);
    b.addEventListener("click", function () { choose(k); });
    b.addEventListener("mouseenter", function () { highlight(k); });
    b.addEventListener("mouseleave", function () { highlight(sel); });
    b.addEventListener("focus", function () { highlight(k); });
    b.addEventListener("blur", function () { highlight(sel); });
    rowEl[n.row].appendChild(b); nodes[k] = b;
  });

  var paths = [];
  function geometry() {
    IF.clear(wires); paths = [];
    if (host.clientWidth < 760) return;
    var base = host.getBoundingClientRect();
    wires.setAttribute("viewBox", "0 0 " + base.width + " " + base.height);
    var box = function (k) { var r = nodes[k].getBoundingClientRect(); return { l: r.left - base.left, r: r.right - base.left, t: r.top - base.top, b: r.bottom - base.top, cx: (r.left + r.right) / 2 - base.left, cy: (r.top + r.bottom) / 2 - base.top }; };
    EDGES.forEach(function (e) {
      var a = box(e[0]), b = box(e[1]), d;
      var sameRow = Math.abs(a.cy - b.cy) < 20;
      if (sameRow) {
        var left = a.cx < b.cx ? a : b, right = left === a ? b : a, gap = right.l - left.r;
        if (gap < 120) d = "M" + left.r + "," + left.cy + "L" + right.l + "," + right.cy;
        else d = "M" + a.cx + "," + a.b + "C" + a.cx + "," + (a.b + 26) + " " + b.cx + "," + (b.b + 26) + " " + b.cx + "," + b.b;
      } else {
        var down = b.cy > a.cy, y1 = down ? a.b : a.t, y2 = down ? b.t : b.b, m = (y1 + y2) / 2;
        d = "M" + a.cx + "," + y1 + "C" + a.cx + "," + m + " " + b.cx + "," + m + " " + b.cx + "," + y2;
      }
      var p = el("path", { d: d, class: e[2] ? "ghost" : "" });
      wires.appendChild(p); paths.push({ p: p, e: e });
    });
    highlight(sel);
  }

  function highlight(k) {
    var rel = {}; rel[k] = 1;
    paths.forEach(function (o) {
      var on = o.e[0] === k || o.e[1] === k;
      o.p.classList.toggle("on", on);
      if (on) { rel[o.e[0]] = 1; rel[o.e[1]] = 1; }
    });
    Object.keys(nodes).forEach(function (n) { nodes[n].classList.toggle("is-rel", !!rel[n] && n !== sel); nodes[n].classList.toggle("is-sel", n === sel); });
  }

  function choose(k) {
    sel = k;
    Object.keys(nodes).forEach(function (n) { nodes[n].setAttribute("aria-pressed", String(n === k)); });
    var n = N[k], viz = EDGES.filter(function (e) { return e[0] === k || e[1] === k; }).map(function (e) { return N[e[0] === k ? e[1] : e[0]].t; });
    IF.clear(insp);
    insp.appendChild(el("div", null, [
      el("p", { class: "fd__h", text: n.layer }),
      el("h3", { text: n.t }),
      el("p", { text: n.d }),
      el("span", { class: "badge badge--" + n.st, style: { "margin-top": "14px" }, text: STATUS[n.st] })
    ]));
    insp.appendChild(el("div", null, [
      el("p", { class: "fd__h", text: "Arquivos" }),
      el("ul", { class: "files" }, n.f.map(function (f) { return el("li", null, el("a", { href: REPO + f, target: "_blank", rel: "noopener", text: f })); })),
      el("p", { class: "fd__h", text: "Conecta com" }),
      el("ul", null, viz.map(function (t) { return el("li", { text: t }); }))
    ]));
    highlight(k);
  }

  choose("api");
  geometry();
  var rt; new ResizeObserver(function () { clearTimeout(rt); rt = setTimeout(geometry, 100); }).observe(host);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(geometry);
})();
