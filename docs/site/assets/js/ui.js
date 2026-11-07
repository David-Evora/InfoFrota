/* Comportamento global: tema, navegação, revelação ao rolar, diálogos, cópia. */
(function () {
  "use strict";
  var IF = window.IF, $ = IF.$, $$ = IF.$$;
  var root = document.documentElement;
  root.classList.add("js");

  /* ---------- tema ---------- */
  var toggle = $("#themeToggle");
  var themeMeta = $('meta[name="theme-color"]');
  function paintTheme(t) {
    root.dataset.theme = t;
    toggle.setAttribute("aria-pressed", String(t === "light"));
    toggle.setAttribute("aria-label", t === "light" ? "Mudar para o tema escuro" : "Mudar para o tema claro");
    if (themeMeta) themeMeta.setAttribute("content", t === "light" ? "#F5F7FB" : "#0B1220");
  }
  paintTheme(root.dataset.theme === "light" ? "light" : "dark");
  toggle.addEventListener("click", function () {
    var t = root.dataset.theme === "light" ? "dark" : "light";
    paintTheme(t);
    try { localStorage.setItem("infofrota-tema", t); } catch (e) {}
    document.dispatchEvent(new CustomEvent("if:tema", { detail: t }));
  });

  /* ---------- navegação ---------- */
  var nav = $("#nav"), burger = $("#navBurger"), links = $$("#navLinks a");
  function solid() { nav.classList.toggle("is-solid", window.scrollY > 8); }
  solid();
  addEventListener("scroll", solid, { passive: true });

  function menu(open) {
    nav.classList.toggle("is-open", open);
    burger.setAttribute("aria-expanded", String(open));
    burger.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    document.body.style.overflow = open ? "hidden" : "";
  }
  burger.addEventListener("click", function () { menu(!nav.classList.contains("is-open")); });
  links.forEach(function (a) { a.addEventListener("click", function () { menu(false); }); });
  addEventListener("keydown", function (e) {
    if (e.key === "Escape" && nav.classList.contains("is-open")) { menu(false); burger.focus(); }
  });
  addEventListener("resize", function () { if (innerWidth > 1020 && nav.classList.contains("is-open")) menu(false); });

  /* seção ativa: a que cruza a linha a ~35% da altura da janela */
  var map = {};
  links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
  var secs = Object.keys(map).map(function (id) { return document.getElementById(id); }).filter(Boolean);
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.removeAttribute("aria-current"); });
        map[e.target.id].setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-35% 0px -60% 0px" });
    secs.forEach(function (s) { io.observe(s); });
  }

  /* ---------- revelar ao rolar ---------- */
  var rev = $$(".reveal");
  rev.forEach(function (n) {
    var i = $$(".reveal", n.parentElement).filter(function (x) { return x.parentElement === n.parentElement; }).indexOf(n);
    n.style.setProperty("--i", Math.min(i, 5));
  });
  if ("IntersectionObserver" in window) {
    var ro = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); ro.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    rev.forEach(function (n) { ro.observe(n); });
  } else rev.forEach(function (n) { n.classList.add("is-in"); });

  /* ---------- diálogos nativos ---------- */
  IF.openDialog = function (dlg) {
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
  };
  $$("dialog.sheet").forEach(function (d) {
    d.addEventListener("click", function (e) {
      if (e.target === d || e.target.closest("[data-close]")) d.close();
    });
  });
  var run = $("#runOpen");
  if (run) run.addEventListener("click", function () { IF.openDialog($("#runDialog")); });

  /* ---------- copiar ---------- */
  $$("[data-copy]").forEach(function (box) {
    var btn = $(".code__copy", box), code = $("code", box);
    btn.addEventListener("click", function () {
      var txt = code.textContent;
      var done = function (ok) {
        btn.textContent = ok ? "Copiado" : "Selecione e copie";
        setTimeout(function () { btn.textContent = "Copiar"; }, 1800);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(function () { done(true); }, function () { done(false); });
      else {
        var r = document.createRange(); r.selectNodeContents(code);
        var s = getSelection(); s.removeAllRanges(); s.addRange(r);
        done(false);
      }
    });
  });
})();
