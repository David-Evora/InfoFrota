/* Núcleo: helpers, formatação pt-BR e camada de serviço da API.
   Nenhuma credencial vive aqui: a chave do LLM fica no backend e o navegador só fala com a própria origem. */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var reduce = matchMedia("(prefers-reduced-motion: reduce)");

  var IF = (window.IF = {
    $: function (s, r) { return (r || document).querySelector(s); },
    $$: function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); },
    reduced: function () { return reduce.matches; },

    /* cria elemento HTML ou SVG; filhos aceitam texto (sempre como texto, nunca como HTML) */
    el: function (tag, attrs, kids) {
      var svg = /^(svg|path|g|circle|rect|line|text|use|defs|linearGradient|stop|polyline|title)$/.test(tag);
      var n = svg ? document.createElementNS(SVG_NS, tag) : document.createElement(tag);
      for (var k in attrs || {}) {
        var v = attrs[k];
        if (v == null || v === false) continue;
        if (k === "class") n.setAttribute("class", v);
        else if (k === "text") n.textContent = v;
        else if (k === "style" && typeof v === "object") for (var p in v) n.style.setProperty(p, v[p]);
        else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, v === true ? "" : v);
      }
      [].concat(kids || []).forEach(function (c) {
        if (c == null || c === false) return;
        n.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
      });
      return n;
    },
    icon: function (id, cls) {
      var s = document.createElementNS(SVG_NS, "svg");
      s.setAttribute("class", "icon" + (cls ? " " + cls : ""));
      s.setAttribute("aria-hidden", "true");
      var u = document.createElementNS(SVG_NS, "use");
      u.setAttribute("href", "#" + id);
      s.appendChild(u);
      return s;
    },
    clear: function (n) { while (n.firstChild) n.removeChild(n.firstChild); return n; },

    /* formatação pt-BR */
    n0: function (v) { return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(v); },
    n1: function (v) { return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v); },
    pct: function (v) { return IF.n1(v) + "%"; },
    hora: function (h) { return String(h).padStart(2, "0") + "h"; },
    dataCurta: function (iso) {
      var d = new Date(iso + "T12:00:00");
      return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "");
    },
    clamp: function (v, a, b) { return Math.min(b, Math.max(a, v)); },

    /* executa uma vez quando o elemento entra na tela */
    whenVisible: function (node, cb, margin) {
      if (!("IntersectionObserver" in window)) return cb();
      var io = new IntersectionObserver(function (es) {
        if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); cb(); }
      }, { rootMargin: margin || "0px 0px -12% 0px", threshold: 0.12 });
      io.observe(node);
    },
    /* cancelável: sleep que respeita movimento reduzido */
    sleep: function (ms) { return new Promise(function (r) { setTimeout(r, IF.reduced() ? Math.min(ms, 30) : ms); }); },

    /* Camada de serviço. O modo ao vivo só liga quando /saude responde na MESMA origem. */
    api: (function () {
      var meta = document.querySelector('meta[name="infofrota-api"]');
      var base = null;
      try {
        if (/^https?:$/.test(location.protocol) && meta) base = new URL(meta.content, location.href);
      } catch (e) { base = null; }

      function call(path, opts, ms) {
        if (!base) return Promise.reject(new Error("sem API"));
        var ctrl = new AbortController();
        var t = setTimeout(function () { ctrl.abort(); }, ms || 8000);
        opts = opts || {};
        opts.signal = ctrl.signal;
        opts.credentials = "same-origin";
        return fetch(new URL(path, base), opts).then(function (r) {
          clearTimeout(t);
          return r.json().catch(function () { return {}; }).then(function (j) {
            if (!r.ok) { var e = new Error((j && j.detail) || "HTTP " + r.status); e.status = r.status; throw e; }
            return j;
          });
        }, function (e) { clearTimeout(t); throw e; });
      }
      return {
        disponivel: !!base,
        saude: function () {
          return call("saude", {}, 2500).then(function (j) {
            if (!j || j.status !== "ok") throw new Error("resposta inesperada");
            return j;
          });
        },
        perguntar: function (pergunta) {
          return call("perguntar", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pergunta: pergunta, texto: false })
          }, 60000);
        }
      };
    })()
  });
})();
