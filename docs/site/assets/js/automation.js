/* Automação: reproduz os 8 nós do workflow n8n/alerta-critico.json e simula UMA execução com alertas do snapshot sintético.
   Nenhuma chamada de rede: não consulta a API e não dispara webhook. */
(function () {
  "use strict";
  var IF = window.IF, el = IF.el, D = window.INFOFROTA_SNAPSHOT;
  if (!D) return;

  var crit = D.alertas_recentes.filter(function (a) { return a.percentual >= 90; }).slice(0, 3);
  var novos = crit.slice(1);                                  // na simulação, o 1º alerta já tinha sido enviado
  var ref = D.alertas_recentes[0].criado_em;
  function linha(a) { return "• Linha " + a.linha + " (" + (a.parada || "sem parada") + "): " + a.percentual + "% às " + a.criado_em; }

  var NODES = [
    { t: "A cada 5 minutos", s: "Schedule Trigger", i: "i-timer",
      d: "Dispara o fluxo em intervalo fixo de cinco minutos.", c: "intervalo: 5 minutos", o: "Execução iniciada" },
    { t: "Configuração", s: "Set", i: "i-layers",
      d: "Define api_base_url, api_key (opcional) e webhook_url. Os valores reais ficam na instância do n8n; o repositório não contém nenhuma URL de webhook.", c: "api_base_url\napi_key (opcional)\nwebhook_url", o: "3 campos de configuração lidos" },
    { t: "Buscar alertas", s: "HTTP Request", i: "i-server",
      d: "Consulta a própria API do InfoFrota pelos alertas críticos das últimas 24 horas, no máximo 10.", c: "GET /alertas\n  ?tipo=CRITICO\n  &janela_horas=24\n  &limite=10\nX-API-Key: (se configurada)", o: "total: " + crit.length + "\nIDs: " + crit.map(function (a) { return a.id; }).join(", ") },
    { t: "Há alertas?", s: "IF", i: "i-git-branch",
      d: "Só segue adiante se a resposta trouxer pelo menos um alerta.", c: "$json.total > 0", o: "total = " + crit.length + " > 0 → segue" },
    { t: "Filtrar novos", s: "Code", i: "i-filter",
      d: "Compara os IDs com o histórico guardado no static data do workflow e descarta o que já foi enviado. Esse histórico só persiste com o workflow ativo.", c: "static data: alertasCriticosEnviados\nnovos = alertas.filter(id não enviado)", o: "já enviado: " + crit[0].id + "\nnovos: " + novos.map(function (a) { return a.id; }).join(", ") },
    { t: "Montar mensagem", s: "Code", i: "i-file-code-2",
      d: "Agrupa os novos alertas em uma única mensagem de texto.", c: "texto = N alerta(s) + janela + linhas + aviso de dados sintéticos", o: "mensagem com " + novos.length + " linha(s)" },
    { t: "Enviar notificação", s: "HTTP Request", i: "i-webhook",
      d: "POST em um webhook compatível com Discord (content) ou Slack (text).", c: "POST {{ webhook_url }}\n{ content, text }", o: "Nesta simulação o webhook NÃO é chamado." },
    { t: "Registrar enviados", s: "Code", i: "i-check",
      d: "Só executa depois que o envio retorna sucesso: grava os IDs no histórico (últimos 10.000). Se o envio falhar, o próximo ciclo tenta de novo.", c: "static.alertasCriticosEnviados\n  = união(histórico, novos)", o: "registrados: " + novos.map(function (a) { return a.id; }).join(", ") }
  ];

  var host = IF.$("#flowNodes"), insp = IF.$("#flowInspector"), play = IF.$("#flowPlay"), card = IF.$("#notifyCard");
  var lis = [], selected = 0, running = false;

  NODES.forEach(function (n, i) {
    var b = el("button", { type: "button", "aria-label": (i + 1) + ". " + n.t + " (" + n.s + ")", "aria-pressed": String(i === 0) }, IF.icon(n.i));
    b.addEventListener("click", function () { if (!running) inspect(i); });
    var li = el("li", { class: "fnode" + (i === 0 ? " is-sel" : "") }, [el("i", { class: "packet" }), b, el("span", { class: "fnode__t", text: n.t }), el("span", { class: "fnode__s", text: n.s })]);
    host.appendChild(li); lis.push(li);
  });

  function inspect(i, out) {
    selected = i;
    lis.forEach(function (l, k) { l.classList.toggle("is-sel", k === i && !running); IF.$("button", l).setAttribute("aria-pressed", String(k === i)); });
    var n = NODES[i];
    IF.clear(insp);
    insp.appendChild(el("div", null, [
      el("p", { class: "eyebrow-sm mono", text: "Nó " + (i + 1) + " de " + NODES.length + " · " + n.s }),
      el("h3", { text: n.t }),
      el("p", { text: n.d }),
      null
    ]));
    insp.appendChild(el("div", null, [
      el("pre", { class: "sqlblock", text: n.c }),
      out ? el("pre", { class: "sqlblock", style: { "margin-top": "8px" }, text: "→ " + n.o }) : null
    ]));
  }

  function renderCard(pop) {
    IF.clear(card);
    card.appendChild(el("b", null, [IF.icon("i-triangle-alert"), novos.length + " novo(s) alerta(s) crítico(s) de lotação."]));
    card.appendChild(el("div", { text: "Janela: últimas 24h (referência: " + ref + ")." }));
    card.appendChild(el("ul", null, novos.map(function (a) { return el("li", { text: linha(a) }); })));
    card.appendChild(el("div", { class: "foot", text: "Dados sintéticos de demonstração." }));
    card.classList.remove("is-pop");
    if (pop) { void card.offsetWidth; card.classList.add("is-pop"); }
  }

  function dist() {
    var v = matchMedia("(max-width: 1100px)").matches;
    return (v ? lis[0].getBoundingClientRect().height : lis[0].getBoundingClientRect().width) - 56;
  }

  async function simulate() {
    if (running) return;
    running = true; play.disabled = true;
    play.lastChild.textContent = "Simulando…";
    lis.forEach(function (l) { l.className = "fnode"; });
    host.style.setProperty("--dist", dist() + "px");
    lis.forEach(function (l) { l.style.setProperty("--dist", Math.max(dist(), 30) + "px"); });
    for (var i = 0; i < NODES.length; i++) {
      lis[i].classList.add(i === 6 ? "is-crit" : "is-run");
      inspect(i, true); lis[i].classList.remove("is-sel");
      await IF.sleep(900);
      lis[i].classList.remove("is-run", "is-crit"); lis[i].classList.add("is-done");
      if (i < NODES.length - 1) { lis[i].classList.add("is-send"); await IF.sleep(IF.reduced() ? 30 : 420); lis[i].classList.remove("is-send"); }
      if (i === 6) renderCard(true);
    }
    running = false; play.disabled = false;
    play.lastChild.textContent = "Simular de novo";
    inspect(0);
    lis[0].classList.add("is-sel");
  }

  play.addEventListener("click", simulate);
  renderCard(false);
  inspect(0);
})();
