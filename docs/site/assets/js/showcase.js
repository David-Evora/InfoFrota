/* Vitrine da plataforma: capturas reais do painel do protótipo (primeira versão do painel, já substituída por este site), tiradas com dados sintéticos. */
(function () {
  "use strict";
  var IF = window.IF, el = IF.el;
  var tabs = IF.$("#showTabs"), screen = IF.$("#showScreen"), cap = IF.$("#showCaption");
  if (!tabs) return;
  var SHOTS = [
    { id: "visao", t: "Visão geral", src: "assets/img/dash-visao.jpg", alt: "Primeira versão do painel com indicadores, alertas recentes e ocupação por linha", c: "Indicadores, alertas recentes e ocupação por linha, calculados na API a partir do banco sintético." },
    { id: "linhas", t: "Linhas", src: "assets/img/dash-linhas.jpg", alt: "Painel do protótipo com a lista de linhas e a ocupação de cada uma", c: "Lista de linhas com ocupação e pico do dia, vinda de GET /resumo sobre o banco sintético." },
    { id: "assistente", t: "Assistente", src: "assets/img/dash-assistente.jpg", alt: "Painel do protótipo com uma pergunta em português, o SQL gerado e a tabela de resultado", c: "Pergunta em português, SQL somente leitura e tabela de resultado. Nesta captura o modelo de linguagem foi substituído por um simulador local." }
  ];
  var imgs = SHOTS.map(function (s, i) {
    var im = el("img", { src: s.src, alt: s.alt, width: 1366, height: 860, loading: "lazy", decoding: "async", class: i === 0 ? "is-on" : "" });
    screen.appendChild(im);
    var b = el("button", { type: "button", role: "tab", "aria-selected": String(i === 0), id: "shot-" + s.id, text: s.t, tabindex: i === 0 ? 0 : -1 });
    b.addEventListener("click", function () { pick(i); });
    b.addEventListener("keydown", function (e) {
      var k = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (!k) return;
      e.preventDefault(); var n = (i + k + SHOTS.length) % SHOTS.length; pick(n); tabs.children[n].focus();
    });
    tabs.appendChild(b);
    return im;
  });
  function pick(i) {
    imgs.forEach(function (im, k) { im.classList.toggle("is-on", k === i); });
    Array.prototype.forEach.call(tabs.children, function (b, k) { b.setAttribute("aria-selected", String(k === i)); b.tabIndex = k === i ? 0 : -1; });
    cap.textContent = SHOTS[i].c;
  }
  pick(0);
})();
