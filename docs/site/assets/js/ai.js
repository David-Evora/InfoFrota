/* Experiência de IA/RAG.
   SIMULAÇÃO (padrão): cenários gravados em scripts/build_site_snapshot.py. O contexto do RAG e o resultado vêm de execução real
   (índice BM25 e guarda de SQL do repositório, sobre o banco sintético); o SQL e o resumo foram escritos à mão e o LLM NÃO foi chamado.
   AO VIVO: só quando /saude responde na mesma origem. O formulário aparece com dois modos:
   Consulta única envia a pergunta ao /perguntar; Agente envia ao /agente (várias consultas SQL, até cerca de 3 minutos).
   Nenhuma chave passa pelo navegador. */
(function () {
  "use strict";
  var IF = window.IF, el = IF.el, D = window.INFOFROTA_SNAPSHOT;
  if (!D) return;

  var chat = IF.$("#aiChat"), trace = IF.$("#aiTrace"), scen = IF.$("#aiScen"), modeEl = IF.$("#aiMode"),
      note = IF.$("#aiNote"), form = IF.$("#aiForm"), input = IF.$("#aiInput"), send = IF.$("#aiSend"), replay = IF.$("#aiReplay");
  var token = 0, current = 0, live = false, lastScenario = null;

  /* ---------- realce de SQL (nós de texto; nada vira HTML) ---------- */
  var KW = /^(SELECT|FROM|WHERE|JOIN|LEFT|ON|GROUP|BY|ORDER|LIMIT|AS|AND|OR|COUNT|AVG|ROUND|CASE|WHEN|THEN|ELSE|END|DESC|ASC|DELETE|WITH|INSERT|UPDATE|DROP|IN|IS|NOT|NULL|DISTINCT|HAVING)$/i;
  function sqlNodes(sql, upto) {
    var txt = upto == null ? sql : sql.slice(0, upto), out = [];
    (txt.match(/'[^']*'?|\w+|\s+|[^\w\s]/g) || []).forEach(function (t) {
      if (/^'/.test(t)) out.push(el("span", { class: "st", text: t }));
      else if (/^\d+(\.\d+)?$/.test(t)) out.push(el("span", { class: "nm", text: t }));
      else if (KW.test(t)) out.push(el("span", { class: "kw", text: t }));
      else out.push(t);
    });
    return out;
  }
  function fmtCell(v) {
    if (typeof v === "number") return Number.isInteger(v) ? IF.n0(v) : IF.n1(v);
    return v == null ? "—" : String(v);
  }
  function table(cols, rows) {
    var show = rows.slice(0, 8);
    var t = el("table", { class: "rtable" }, [
      el("thead", null, el("tr", null, cols.map(function (c) { return el("th", { scope: "col", text: c }); }))),
      el("tbody", null, show.map(function (r) { return el("tr", null, r.map(function (c) { return el("td", { text: fmtCell(c) }); })); }))
    ]);
    var w = el("div", { class: "rwrap" }, t);
    if (rows.length > show.length) w.appendChild(el("p", { class: "muted", style: { padding: "8px 12px" }, text: "+ " + (rows.length - show.length) + " linhas não exibidas" }));
    return w;
  }

  /* ---------- trilha de etapas ---------- */
  var STEPS = [
    { t: "Pergunta recebida", i: "i-message-square-text" },
    { t: "Contexto recuperado (RAG)", i: "i-search" },
    { t: "SQL gerado pelo modelo", i: "i-terminal" },
    { t: "Guarda somente leitura", i: "i-shield-check" },
    { t: "Resultado", i: "i-database" }
  ];
  function buildTrace() {
    IF.clear(trace);
    return STEPS.map(function (s) {
      var body = el("div", { class: "tb" });
      var li = el("li", null, [el("span", { class: "dot" }, IF.icon(s.i)), el("div", null, [el("h4", { text: s.t }), body])]);
      trace.appendChild(li);
      return { li: li, body: body };
    });
  }
  function mark(st, state, content) {
    st.li.className = state ? "is-" + state : "";
    if (content !== undefined) { IF.clear(st.body); [].concat(content).forEach(function (c) { if (c) st.body.appendChild(typeof c === "object" ? c : document.createTextNode(c)); }); }
  }
  function short(s, n) { s = String(s == null ? "" : s); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  var NOTA_SINT = "Dados sintéticos de demonstração, não representam a operação real da CETURBES.";
  function msgErro(err, agente) {
    if (err && err.status === 401) return "A API exige chave de acesso (X-API-Key). Por segurança, este site nunca envia chaves.";
    if (err && err.status === 422) return "Pergunta inválida: use de 3 a 500 caracteres.";
    if (err && err.status === 429) return "Limite de pedidos por minuto ou cota diária do provedor atingido. Aguarde e tente de novo.";
    if (err && err.status === 502) return "O modelo falhou ao responder. Confira se o provedor está no ar e tente de novo.";
    if (err && err.status === 503) return "O modelo não está configurado ou está indisponível no momento.";
    if (err && err.status) return "A API respondeu com erro (" + err.status + "). Confira o provedor e a chave do modelo no backend.";
    if (err && err.name === "AbortError") return agente
      ? "A espera passou de 5 minutos e foi interrompida. Tente uma pergunta mais direta."
      : "A API não respondeu a tempo. Confira se ela continua rodando.";
    return "Sem resposta da API. Confira se ela continua rodando.";
  }
  function sqlPre(sql) {
    var pre = el("pre", { class: "sqlblock" });
    sqlNodes(String(sql || "")).forEach(function (x) { pre.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
    return pre;
  }
  /* Só as consultas SQL: a entrada é o SELECT e a observação vem truncada. */
  function blocoPassos(passos) {
    var sqls = (passos || []).filter(function (p) { return p && p.ferramenta === "sql"; });
    var det = el("details", { class: "apassos" });
    det.appendChild(el("summary", { text: sqls.length ? "Consultas SQL (" + sqls.length + ")" : "Consultas SQL (nenhuma)" }));
    if (!sqls.length) {
      det.appendChild(el("p", { class: "apasso", text: "O agente não executou consulta SQL." }));
      return det;
    }
    sqls.forEach(function (p, i) {
      var obs = p.observacao == null ? "" : String(p.observacao);
      det.appendChild(el("div", { class: "apasso" }, [
        el("p", { class: "eyebrow-sm", text: "Consulta " + (i + 1) }),
        sqlPre(p.entrada),
        el("p", { text: obs ? short(obs, 300) : "Sem resultado resumido." })
      ]));
    });
    return det;
  }

  var relogio = null;
  function pararRelogio() { if (relogio) { clearInterval(relogio); relogio = null; } }
  function tempoDecorrido(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }
  function iniciarRelogio(node, my) {
    pararRelogio();
    var t0 = Date.now();
    function tick() {
      if (my !== token) { pararRelogio(); return; }
      node.textContent = "Tempo decorrido: " + tempoDecorrido(Date.now() - t0);
    }
    tick();
    relogio = setInterval(tick, 1000);
    return t0;
  }

  function setMode(isLive) {
    modeEl.className = "mode " + (isLive ? "mode--live" : "mode--sim");
    modeEl.textContent = isLive ? "Ao vivo · API local" : "Simulação";
    modeEl.title = isLive ? "Resposta gerada agora pelo modelo configurado na API" : "Resposta gravada; o modelo de linguagem não foi chamado";
  }

  /* ---------- reprodução (simulada ou real) ---------- */
  async function play(c, isLive, myToken) {
    pararRelogio();
    chat.setAttribute("aria-busy", "false");
    var alive = function () { return myToken === token; };
    setMode(isLive);
    IF.clear(chat);
    var steps = buildTrace();
    chat.appendChild(el("div", { class: "msg msg--user", text: c.pergunta }));
    var ai = el("div", { class: "msg msg--ai" }), who = el("div", { class: "msg__who" }, [IF.icon("i-bot"), el("span", { text: "Assistente InfoFrota" + (isLive ? "" : " · simulação") })]);
    var out = el("div", { class: "msg__text" }, el("span", { class: "thinking", "aria-label": "Processando" }, [el("i"), el("i"), el("i")]));
    ai.appendChild(who); ai.appendChild(out); chat.appendChild(ai);

    mark(steps[0], "active"); await IF.sleep(420); if (!alive()) return;
    mark(steps[0], "done", c.pergunta.length + " caracteres, dentro do limite de 3 a 500.");

    mark(steps[1], "active"); await IF.sleep(480); if (!alive()) return;
    if (c.rag) {
      var chips = el("div", { class: "ctx" }), i = 0;
      c.rag.tabelas.forEach(function (t) { chips.appendChild(el("span", { class: "k-tab", style: { "--i": i++ }, text: t })); });
      c.rag.valores.forEach(function (v) { chips.appendChild(el("span", { class: "k-val", style: { "--i": i++ }, title: v, text: short(v, 44) })); });
      c.rag.regras.forEach(function (v) { chips.appendChild(el("span", { class: "k-rul", style: { "--i": i++ }, title: v, text: short(v, 44) })); });
      var vazio = !c.rag.tabelas.length;
      mark(steps[1], "done", vazio ? "Nenhuma tabela do esquema combina com a pergunta." : [chips, "Tabelas, valores válidos e regras entram no prompt."]);
    } else mark(steps[1], "done", "A API monta esse contexto no servidor; ele não é devolvido ao navegador.");

    if (!c.sql) {
      mark(steps[2], "skip", "O modelo recusou: a pergunta foge do que o banco contém.");
      mark(steps[3], "skip", "Nada a validar.");
      mark(steps[4], "skip", "Sem consulta, sem resultado.");
      IF.clear(out); out.classList.add("is-refuse"); out.textContent = c.texto; return;
    }

    mark(steps[2], "active");
    var pre = el("pre", { class: "sqlblock" });
    steps[2].body.appendChild(pre);
    for (var n = 12; n < c.sql.length + 12 && alive(); n += 12) {
      IF.clear(pre); sqlNodes(c.sql, Math.min(n, c.sql.length)).forEach(function (x) { pre.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
      await IF.sleep(28);
    }
    if (!alive()) return;
    IF.clear(pre); sqlNodes(c.sql).forEach(function (x) { pre.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
    mark(steps[2], "done");

    mark(steps[3], "active"); await IF.sleep(520); if (!alive()) return;
    var camadas = ["Instrução única SELECT ou WITH", "Authorizer do SQLite", "Conexão mode=ro, até 200 linhas e 5 s"];
    if (c.bloqueado) {
      var lista = el("ul", { class: "checks" }, camadas.map(function (t, k) {
        return el("li", { class: k === 0 ? "no" : "" }, k === 0 ? [el("span", { class: "ck" }, IF.icon("i-x")), el("span", { text: t + ": " + (c.erro || "reprovado") })] : [el("span", { class: "ck" }, IF.icon("i-clock")), el("span", { text: t + ": não chegou a executar" })]);
      }));
      mark(steps[3], "fail", lista);
      mark(steps[4], "skip", "Nada foi executado. O banco não foi tocado.");
      IF.clear(out); out.classList.add("is-block"); out.textContent = c.texto; return;
    }
    mark(steps[3], "done", el("ul", { class: "checks" }, camadas.map(function (t) { return el("li", { class: "ok" }, [el("span", { class: "ck" }, IF.icon("i-check")), el("span", { text: t })]); })));

    mark(steps[4], "active"); await IF.sleep(460); if (!alive()) return;
    if (c.erro) { mark(steps[4], "fail", c.erro); IF.clear(out); out.classList.add("is-block"); out.textContent = c.texto; return; }
    mark(steps[4], "done", c.linhas.length ? table(c.colunas, c.linhas) : "A consulta não retornou linhas.");
    IF.clear(out); out.textContent = c.texto;
  }

  function run(c, isLive) {
    lastScenario = { c: c, live: isLive };
    return play(c, isLive, ++token);
  }

  /* ---------- abas de cenário ---------- */
  D.cenarios.forEach(function (c, i) {
    var b = el("button", { type: "button", role: "tab", "aria-selected": String(i === 0), id: "scen" + i, text: c.rotulo });
    b.addEventListener("click", function () { select(i); });
    b.addEventListener("keydown", function (e) {
      var k = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!k) return;
      e.preventDefault(); var n = (i + k + D.cenarios.length) % D.cenarios.length; select(n); IF.$("#scen" + n).focus();
    });
    scen.appendChild(b);
  });
  function select(i) {
    current = i;
    IF.$$("button", scen).forEach(function (b, k) { b.setAttribute("aria-selected", String(k === i)); b.tabIndex = k === i ? 0 : -1; });
    run(D.cenarios[i], false);
  }
  IF.$$("button", scen).forEach(function (b, k) { b.tabIndex = k === 0 ? 0 : -1; });
  replay.addEventListener("click", function () { if (lastScenario) run(lastScenario.c, lastScenario.live); });

  /* ---------- modo ao vivo ---------- */
  var NOTE_SIM = "Simulação: contexto do RAG e resultado vêm de execução real sobre o banco sintético; o SQL e o resumo foram escritos à mão e o modelo de linguagem não foi chamado.";
  var noteBase = NOTE_SIM;
  var kind = "unica";
  var kindEl = IF.$("#aiKind");
  function paintNote() {
    var extra = "";
    if (live && kind === "agente") extra = " Modo agente: várias consultas SQL no servidor, em geral até 3 minutos. A página segue utilizável enquanto espera.";
    else if (live) extra = " Modo consulta única: uma pergunta vira um SQL. Uma pergunta a cada 3 s; a API também limita por IP.";
    note.textContent = noteBase + extra;
  }
  function setKind(k) {
    kind = k;
    IF.$$("button", kindEl).forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-kind") === k));
    });
    input.placeholder = k === "agente"
      ? "Pergunta que pode exigir várias consultas no banco sintético…"
      : "Pergunte algo sobre o banco sintético…";
    paintNote();
  }
  IF.$$("button", kindEl).forEach(function (b) {
    b.addEventListener("click", function () { setKind(b.getAttribute("data-kind")); });
  });
  kindEl.addEventListener("keydown", function (e) {
    var dir = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (!dir) return;
    var bs = IF.$$("button", kindEl), i = bs.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    var n = (i + dir + bs.length) % bs.length;
    bs[n].focus();
    setKind(bs[n].getAttribute("data-kind"));
  });
  note.textContent = NOTE_SIM;
  setMode(false);

  var cooling = false;
  function liberar() { setTimeout(function () { cooling = false; send.disabled = false; }, 3000); }

  function falhaAoVivo(my, out, steps, err, agente) {
    if (my !== token) return;
    pararRelogio();
    chat.setAttribute("aria-busy", "false");
    IF.clear(out); out.classList.add("is-block"); out.textContent = msgErro(err, agente);
    if (steps) mark(steps[0], "fail");
  }

  function rodarPergunta(q, my) {
    IF.clear(chat);
    chat.setAttribute("aria-busy", "true");
    chat.appendChild(el("div", { class: "msg msg--user", text: q }));
    var out = el("div", { class: "msg__text" }, el("span", { class: "thinking", "aria-label": "Processando" }, [el("i"), el("i"), el("i")]));
    chat.appendChild(el("div", { class: "msg msg--ai" }, [el("div", { class: "msg__who" }, [IF.icon("i-bot"), el("span", { text: "Assistente InfoFrota" })]), out]));
    var steps = buildTrace(); mark(steps[0], "active");
    IF.api.perguntar(q).then(function (r) {
      if (my !== token) return;
      var c = {
        pergunta: q, rag: null, sql: r.sql || "", bloqueado: !!r.bloqueado, erro: r.erro || null,
        colunas: r.colunas || [], linhas: r.linhas || [],
        texto: r.bloqueado ? (r.erro || "Consulta bloqueada pela guarda de leitura.") :
               !r.pode_responder ? (r.motivo || "O assistente não conseguiu responder a essa pergunta.") :
               r.erro ? "A consulta falhou: " + r.erro :
               (r.linhas || []).length + " linha(s) retornada(s)" + (r.truncado ? " (truncado)" : "") + (r.tentativas > 1 ? " após " + r.tentativas + " tentativas." : ".")
      };
      return play(c, true, my);
    }).catch(function (err) { falhaAoVivo(my, out, steps, err, false); })
      .then(liberar);
  }

  function rodarAgente(q, my) {
    IF.clear(chat);
    chat.setAttribute("aria-busy", "true");
    chat.appendChild(el("div", { class: "msg msg--user", text: q }));
    var out = el("div", { class: "msg__text" }, el("span", { class: "thinking", "aria-label": "Processando" }, [el("i"), el("i"), el("i")]));
    var espera = el("p", { class: "muted", text: "O agente está consultando o banco. Pode levar até 3 minutos." });
    chat.appendChild(el("div", { class: "msg msg--ai" }, [
      el("div", { class: "msg__who" }, [IF.icon("i-bot"), el("span", { text: "Assistente InfoFrota · agente" })]),
      out, espera
    ]));
    IF.clear(trace);
    var clock = el("p", { class: "elapsed", role: "timer", "aria-live": "off" });
    trace.appendChild(el("li", { class: "is-active" }, [
      el("span", { class: "dot" }, IF.icon("i-timer")),
      el("div", null, [el("h4", { text: "Agente em execução" }), el("div", { class: "tb" }, [
        "As consultas rodam no servidor. Dá para continuar usando a página.",
        clock
      ])])
    ]));
    var t0 = iniciarRelogio(clock, my);
    IF.api.agente(q).then(function (r) {
      if (my !== token) return;
      pararRelogio();
      chat.setAttribute("aria-busy", "false");
      var gasto = "Tempo decorrido: " + tempoDecorrido(Date.now() - t0);
      IF.clear(out);
      var texto = r && r.texto ? String(r.texto) : (r && r.erro ? "O agente não concluiu: " + r.erro : "O agente não devolveu texto.");
      out.textContent = texto;
      if (!r || !r.texto) out.classList.add("is-block");
      espera.className = "nota-sint";
      espera.textContent = (r && r.nota) ? String(r.nota) : NOTA_SINT;
      IF.clear(trace);
      trace.appendChild(el("li", { class: "is-done" }, [
        el("span", { class: "dot" }, IF.icon("i-database")),
        el("div", null, [
          el("h4", { text: "Consultas do agente" }),
          el("div", { class: "tb" }, [
            el("p", { class: "elapsed", text: "Concluído. " + gasto }),
            (r && r.texto && r.erro) ? el("p", { text: String(r.erro) }) : null,
            blocoPassos((r && r.passos) || [])
          ])
        ])
      ]));
    }).catch(function (err) {
      falhaAoVivo(my, out, null, err, true);
      if (my !== token) return;
      if (espera.parentNode) espera.parentNode.removeChild(espera);
      IF.clear(trace);
      trace.appendChild(el("li", { class: "is-fail" }, [
        el("span", { class: "dot" }, IF.icon("i-triangle-alert")),
        el("div", null, [el("h4", { text: "Agente interrompido" }), el("div", { class: "tb" }, el("p", { class: "elapsed", text: "Tempo decorrido: " + tempoDecorrido(Date.now() - t0) }))])
      ]));
    }).then(liberar);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (q.length < 3 || cooling) { input.focus(); return; }
    cooling = true; send.disabled = true;
    var my = ++token; lastScenario = null;
    pararRelogio();
    setMode(true);
    IF.$$("button", scen).forEach(function (b) { b.setAttribute("aria-selected", "false"); });
    input.value = "";
    if (kind === "agente") rodarAgente(q, my);
    else rodarPergunta(q, my);
  });

  if (IF.api.disponivel) {
    IF.api.saude().then(function () {
      form.classList.remove("hidden"); live = true;
      noteBase = NOTE_SIM + " A API local respondeu: o seletor acima escolhe consulta única ou agente. O navegador não envia chaves.";
      paintNote();
    }, function () { /* sem API: permanece em simulação; o seletor fica oculto com o formulário */ });
  }

  IF.whenVisible(IF.$("#aiConsole"), function () { select(0); });

  /* ---------- avaliação experimental ---------- */
  var ROUNDS = {
    compacto: { nome: "Prompt compacto", linhas: [
      { l: "Modelo base", s: "sem RAG", n: 19, base: true },
      { l: "Base + RAG", s: "contexto no prompt", n: 25 },
      { l: "LoRA", s: "treinado sem contexto", n: 36 },
      { l: "LoRA + RAG", s: "contexto só na avaliação", n: 36, best: true }
    ], nota: "Mesmo benchmark (v2.1), zero-shot. É o resultado definido antes de qualquer ajuste: 19 para 36 acertos, 33,9% para 64,3%. Com 56 perguntas, diferenças de um ou dois acertos são ruído." },
    ultra: { nome: "Prompt ultra", linhas: [
      { l: "Modelo base", s: "sem RAG", n: 19, base: true },
      { l: "Base + RAG", s: "contexto no prompt", n: 28 },
      { l: "LoRA com contexto, sem RAG", s: "treinado com contexto", n: 33 },
      { l: "LoRA com contexto + RAG", s: "mesmas condições do treino", n: 39, best: true }
    ], nota: "Segunda rodada, planejada depois de analisar os erros da primeira. Frente à rodada anterior, o ganho de 3 acertos está dentro do ruído e prompt e RAG mudaram ao mesmo tempo. O nível difícil segue baixo: 3 de 15." }
  };
  var TOTAL = 56, cur = "compacto", evalBox = IF.$("#evalChart"), evNote = IF.$("#evalNote"), evSeg = IF.$("#evalRound");
  function drawEval(animate) {
    var r = ROUNDS[cur];
    IF.clear(evalBox);
    var fills = r.linhas.map(function (x) {
      var f = el("span", { class: "ev__fill", style: { "--w": animate ? "0%" : (x.n / TOTAL * 100) + "%" }, text: x.n + "/" + TOTAL + " · " + IF.pct(x.n / TOTAL * 100) });
      evalBox.appendChild(el("div", { class: "ev" + (x.base ? " ev--base" : "") + (x.best ? " ev--best" : "") }, [
        el("div", { class: "ev__label" }, [x.l, el("small", { text: x.s })]),
        el("div", { class: "ev__track", role: "img", "aria-label": x.l + ": " + x.n + " de " + TOTAL + " acertos" }, f)
      ]));
      return { f: f, w: x.n / TOTAL * 100 };
    });
    if (animate) requestAnimationFrame(function () { requestAnimationFrame(function () { fills.forEach(function (o) { o.f.style.setProperty("--w", o.w + "%"); }); }); });
    evNote.textContent = r.nota + " Experimento sobre base sintética; não mede desempenho em operação real. Fonte: docs/experiments.md.";
  }
  Object.keys(ROUNDS).forEach(function (k) {
    var b = el("button", { type: "button", "aria-pressed": String(k === cur), text: ROUNDS[k].nome });
    b.addEventListener("click", function () {
      cur = k; IF.$$("button", evSeg).forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); drawEval(true);
    });
    evSeg.appendChild(b);
  });
  drawEval(false);
  var evFills = IF.$$(".ev__fill", evalBox);
  evFills.forEach(function (f) { f.dataset.w = f.style.getPropertyValue("--w"); f.style.setProperty("--w", "0%"); });
  IF.whenVisible(evalBox, function () { requestAnimationFrame(function () { IF.$$(".ev__fill", evalBox).forEach(function (f) { if (f.dataset.w) f.style.setProperty("--w", f.dataset.w); }); }); });
})();
