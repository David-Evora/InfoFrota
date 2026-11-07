(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  /* Tudo que vem da API entra na página como texto (textContent / nós de texto), nunca como HTML. */
  const el = (tag, props = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else node.setAttribute(key, value === true ? '' : value);
    }
    node.append(...children.filter((child) => child !== null && child !== undefined && child !== false));
    return node;
  };

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- Navegação ---------- */
  const navItems = $$('.nav-item');
  const views = $$('.view');
  const breadcrumb = $('#breadcrumbCurrent');
  const sidebar = $('#sidebar');
  const mobileMenu = $('#mobileMenu');

  const labels = {
    overview: 'Visão geral',
    lines: 'Linhas',
    fleet: 'Frota',
    reports: 'Relatórios',
    assistant: 'Assistente IA'
  };

  function setMenu(open) {
    sidebar.classList.toggle('open', open);
    mobileMenu?.setAttribute('aria-expanded', String(open));
  }

  function showView(name) {
    if (!labels[name]) return;
    navItems.forEach((item) => {
      const active = item.dataset.view === name;
      item.classList.toggle('active', active);
      if (active) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });
    views.forEach((view) => view.classList.toggle('active', view.id === `view-${name}`));
    breadcrumb.textContent = labels[name];
    setMenu(false);
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
    if (window.location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  }

  navItems.forEach((item) => item.addEventListener('click', () => showView(item.dataset.view)));
  mobileMenu?.addEventListener('click', () => setMenu(!sidebar.classList.contains('open')));
  $('.brand')?.addEventListener('click', (event) => {
    event.preventDefault();
    showView('overview');
  });

  const initial = window.location.hash.replace('#', '');
  if (labels[initial]) showView(initial);

  /* ---------- Formatação ---------- */
  const num = (v, digits = 1) => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: digits });
  const pct = (v) => `${num(v)}%`;
  const parts = (iso) => String(iso || '').slice(0, 10).split('-');
  const dataBR = (iso) => { const [a, m, d] = parts(iso); return d && m && a ? `${d}/${m}/${a}` : '—'; };
  const diaMes = (iso) => { const [, m, d] = parts(iso); return d && m ? `${d}/${m}` : '—'; };
  const horaMin = (s) => (String(s || '').match(/(\d{2}):(\d{2})/) || [])[0] || '—';
  const dataHora = (s) => (s ? `${diaMes(s)} ${horaMin(s)}` : '—');
  const clamp = (v, min = 0, max = 100) => Math.min(max, Math.max(min, Number(v) || 0));
  const capitalizar = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
  const cel = (v) => (v === null || v === undefined ? '—' : typeof v === 'number' ? (Number.isInteger(v) ? String(v) : num(v, 2)) : String(v));

  /* ---------- Cliente da API (mesma origem) ---------- */
  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  async function api(path, { method = 'GET', body, timeout = 15000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(path, {
        method,
        signal: controller.signal,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined
      });
      let data = null;
      try { data = await res.json(); } catch { /* resposta sem JSON */ }
      if (!res.ok) throw new ApiError(res.status, typeof data?.detail === 'string' ? data.detail : '');
      if (data === null) throw new ApiError(res.status, 'Resposta inesperada da API.');
      return data;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error.name === 'AbortError') throw new ApiError(0, 'A API demorou demais para responder.');
      throw new ApiError(0, 'Não foi possível falar com a API.');
    } finally {
      clearTimeout(timer);
    }
  }

  function mensagemDeErro(error) {
    const detalhe = error.message ? ` (${error.message})` : '';
    switch (error.status) {
      case 401: return 'A API exige chave (X-API-Key). Esta interface não guarda chaves: desative INFOFROTA_API_KEY no ambiente local ou consulte a API diretamente.';
      case 422: return 'Pergunta inválida: use entre 3 e 500 caracteres.';
      case 429: return 'Muitos pedidos em pouco tempo. Aguarde um instante e tente de novo.';
      case 502: return error.message || 'O modelo falhou ao responder.';
      case 503: return `O modelo ainda não está configurado no servidor; confira o .env.api e a chave do provedor${detalhe}.`;
      default: return error.message || 'Erro inesperado.';
    }
  }

  /* ---------- Modo: demonstração (estático) ou ao vivo (API na mesma origem) ---------- */
  const state = { live: false, saude: null };

  async function detectarApi() {
    try {
      const saude = await api('/saude', { timeout: 2500 });
      if (saude && saude.status === 'ok') Object.assign(state, { live: true, saude });
    } catch { /* sem API: fica o modo demonstração */ }
  }

  function aplicarModo() {
    const { live, saude } = state;
    document.body.dataset.mode = live ? 'live' : 'demo';
    $('#modePill').classList.toggle('live', live);
    $('#modePillText').textContent = live ? 'API conectada · dados sintéticos' : 'Dados demonstrativos';
    $('#modeFoot').textContent = live ? 'API CONECTADA' : 'DEMONSTRAÇÃO ESTÁTICA';
    $('#footerNote').textContent = live ? 'Protótipo · Dados sintéticos · 2026' : 'Protótipo visual · Dados fictícios · 2026';
    if (!live) return;

    const periodo = Array.isArray(saude.periodo) ? `${dataBR(saude.periodo[0])} a ${dataBR(saude.periodo[1])}` : 'período não informado';
    $('#modeNoticeText').replaceChildren(
      el('strong', { text: 'Modo ao vivo:' }),
      ` indicadores, linhas, alertas e o assistente consultam a API local sobre um banco SQLite com dados sintéticos (${periodo}). Não há conexão com sensores, dados reais, CETURB/ES ou sistema operacional. A curva diária, o mapa, a frota e os relatórios continuam ilustrativos.`
    );
    $('#headingDateLabel').textContent = 'BANCO EXPERIMENTAL';
    $('#headingDateValue').textContent = periodo;

    $('#assistantSub').textContent = 'Pergunte em português; o modelo gera um SQL somente leitura e a API executa no banco sintético.';
    $('#assistantChip').textContent = 'Ao vivo · experimental';
    $('#assistantIntro').textContent = 'Olá! Sou a camada experimental de consulta do InfoFrota. Cada pergunta é traduzida em SQL, validada como somente leitura e executada no banco sintético.';
    $('#assistantTextoRow').classList.remove('hidden');
    $('#assistantHint').textContent = 'Ctrl + Enter envia · respostas de modelo podem errar; confira o SQL';
    $('#assistantSubmitText').textContent = 'Perguntar';
    $('#linesChip').textContent = 'Dados sintéticos · API';
    $('#linesLimit').textContent = 'Os valores vêm de um banco SQLite gerado por simulação (GET /resumo). Não são leituras de sensores nem dados oficiais, e não devem ser lidos como a operação real das linhas.';
    atualizarModelo();
  }

  function atualizarModelo() {
    const modelo = state.saude?.modelo;
    $('#modelInfo').textContent = modelo
      ? `Modelo ativo no servidor: ${modelo}. Não é o modelo medido no benchmark.`
      : 'O modelo é carregado na primeira pergunta e não é o modelo medido no benchmark.';
  }

  /* ---------- Painel, linhas e alertas (ao vivo) ---------- */
  const kpis = $$('#view-overview .kpi-grid .kpi-card');

  function setKpi(index, { icon, label, value, unit, tag, tagClass, text }) {
    const card = kpis[index];
    if (!card) return;
    $('.kpi-icon', card).textContent = icon;
    $('.kpi-label', card).textContent = label;
    const valueNode = $('.kpi-value', card);
    valueNode.textContent = value;
    if (unit) valueNode.append(el('span', { class: 'unit', text: unit }));
    $('.kpi-foot', card).replaceChildren(el('span', { class: tagClass, text: tag }), el('span', { text }));
  }

  function mensagemNoPainel(node, texto) {
    node.replaceChildren(el('p', { class: 'panel-error', role: 'status', text: texto }));
  }

  function renderKpis(resumo) {
    const { saude } = state;
    const topo = resumo?.linhas?.[0];
    setKpi(0, { icon: '⇄', label: 'Linhas monitoradas', value: String(saude.linhas_monitoradas ?? '—'), tag: 'Sintético', tagClass: 'neutral-tag', text: 'com leituras simuladas' });
    if (!resumo) {
      setKpi(1, { icon: '♙', label: 'Maior ocupação média', value: '—', tag: 'Indisponível', tagClass: 'neutral-tag', text: 'falha ao ler /resumo' });
      setKpi(2, { icon: '!', label: 'Alertas críticos no dia', value: '—', tag: 'Indisponível', tagClass: 'neutral-tag', text: 'falha ao ler /resumo' });
      setKpi(3, { icon: '▦', label: 'Dia de referência', value: '—', tag: 'Indisponível', tagClass: 'neutral-tag', text: 'falha ao ler /resumo' });
      return;
    }
    setKpi(1, { icon: '♙', label: 'Maior ocupação média', value: topo ? num(topo.media_percentual) : '—', unit: topo ? '%' : '', tag: topo ? `Linha ${topo.linha}` : '—', tagClass: 'orange-text', text: `média em ${diaMes(resumo.data)}` });
    setKpi(2, { icon: '!', label: 'Alertas críticos no dia', value: String(resumo.totais?.critico ?? 0), tag: `${resumo.totais?.atencao ?? 0} de atenção`, tagClass: 'red-text', text: 'todas as linhas' });
    setKpi(3, { icon: '▦', label: 'Dia de referência', value: diaMes(resumo.data), tag: 'Sintético', tagClass: 'neutral-tag', text: `${resumo.total_linhas} linhas com resumo` });
  }

  function renderBarras(resumo) {
    const top = (resumo.linhas || []).slice(0, 5);
    $('#barsSub').textContent = `Média diária das ${top.length} linhas mais cheias em ${dataBR(resumo.data)}`;
    $('#barsLegend').textContent = 'Ocupação média do dia';
    $('#barsScale').textContent = 'Escala: 0–100% da capacidade';
    $('#barsNote').textContent = 'Dados sintéticos · fonte: GET /resumo. O pico do dia de cada linha está na aba Linhas.';
    $('#overviewBars').replaceChildren(...top.map((l) => el('div', { class: 'bar-row', title: `${l.linha} · ${l.linha_nome} · pico ${pct(l.max_percentual)}` },
      el('span', { class: 'bar-name', text: l.linha }),
      el('div', { class: 'bar-track' }, el('i', { class: l.media_percentual >= 75 ? 'high' : null, style: `width:${clamp(l.media_percentual)}%` })),
      el('b', { text: pct(l.media_percentual) })
    )));
  }

  const situacao = (maximo) => (maximo >= 90 ? ['critical', 'Crítico'] : maximo >= 75 ? ['attention', 'Atenção'] : ['normal', 'Normal']);

  function renderLinhas(resumo) {
    const linhas = resumo.linhas || [];
    $('#linesSub').textContent = `Ocupação, pico e alertas por linha em ${dataBR(resumo.data)} (${resumo.total_linhas} linhas monitoradas).`;
    $('#linesTitle').textContent = 'Linhas do banco experimental';
    $('#linesNote').textContent = 'Dados sintéticos gerados por simulação; "Pico do dia" usa os limites do sistema: atenção ≥ 75% e crítico ≥ 90%.';
    $('#linesHead').replaceChildren(el('tr', {}, ...['Linha', 'Perfil', 'Ocupação média', 'Máxima', 'Hora de pico', 'Alertas (atenção / crítico)', 'Pico do dia'].map((t) => el('th', { scope: 'col', text: t }))));
    $('#linesTable').replaceChildren(...linhas.map((l) => {
      const [classe, rotulo] = situacao(l.max_percentual);
      return el('tr', {},
        el('td', {}, el('strong', { text: l.linha }), el('small', { class: 'line-name', title: l.linha_nome, text: l.linha_nome })),
        el('td', { text: capitalizar(l.tipo) }),
        el('td', {}, el('span', { class: 'percent-bar' }, el('i', { class: l.media_percentual >= 75 ? 'hot' : null, style: `width:${clamp(l.media_percentual)}%` })), pct(l.media_percentual)),
        el('td', { text: pct(l.max_percentual) }),
        el('td', { text: horaMin(l.hora_pico) }),
        el('td', { text: `${l.total_alertas_atencao ?? 0} / ${l.total_alertas_critico ?? 0}` }),
        el('td', {}, el('span', { class: `status ${classe}`, text: rotulo }))
      );
    }));
    $('#lineSearch').dispatchEvent(new Event('input'));
  }

  function renderAlertas(dados) {
    $('#alertsSub').textContent = `Maiores ocupações nas ${dados.janela_horas} h até ${dataHora(dados.referencia)} (referência: último alerta do banco)`;
    $('#alertCount').textContent = `${dados.total} em ${dados.janela_horas} h`;
    const lista = $('#alertList');
    if (!dados.alertas.length) return mensagemNoPainel(lista, 'Nenhum alerta na janela de tempo.');
    lista.replaceChildren(...dados.alertas.map((a) => {
      const critico = a.tipo === 'CRITICO';
      return el('div', { class: 'alert-item' },
        el('span', { class: `alert-symbol ${critico ? 'critical' : 'warning'}`, 'aria-hidden': 'true', text: '!' }),
        el('div', {},
          el('strong', { text: `Linha ${a.linha} · ${a.parada || 'trecho não informado'}` }),
          el('p', { text: a.mensagem }),
          el('small', { text: `${dataHora(a.criado_em)} · ${pct(a.percentual)} · ${a.resolvido ? 'resolvido' : 'em aberto'}` })
        ),
        el('span', { class: `severity ${critico ? 'critical-text' : 'warning-text'}`, text: critico ? 'Crítico' : 'Atenção' })
      );
    }));
  }

  async function carregarPainel() {
    const [resumo, alertas] = await Promise.allSettled([api('/resumo?limite=50'), api('/alertas?janela_horas=24&limite=5')]);

    if (resumo.status === 'fulfilled') {
      renderKpis(resumo.value);
      renderBarras(resumo.value);
      renderLinhas(resumo.value);
    } else {
      renderKpis(null);
      const aviso = `Não foi possível carregar o resumo: ${mensagemDeErro(resumo.reason)}`;
      mensagemNoPainel($('#overviewBars'), aviso);
      mensagemNoPainel($('#linesTable'), aviso);
    }

    if (alertas.status === 'fulfilled') renderAlertas(alertas.value);
    else mensagemNoPainel($('#alertList'), `Não foi possível carregar os alertas: ${mensagemDeErro(alertas.reason)}`);
  }

  /* ---------- Busca de linhas ---------- */
  const lineSearch = $('#lineSearch');
  lineSearch?.addEventListener('input', () => {
    const query = lineSearch.value.trim().toLowerCase();
    $$('#linesTable tr').forEach((row) => {
      row.hidden = !row.textContent.toLowerCase().includes(query);
    });
  });

  /* ---------- Assistente ---------- */
  const form = $('#assistantForm');
  const question = $('#assistantQuestion');
  const result = $('#assistantResult');
  const answerText = $('#answerText');
  const sqlText = $('#sqlText');
  const sqlLabel = $('#sqlLabel');
  const statusLine = $('#resultStatus');
  const tableBox = $('#resultTable');
  const foot = $('#resultFoot');
  const submit = $('#assistantSubmit');
  const submitText = $('#assistantSubmitText');
  const textoBox = $('#assistantTexto');
  let busy = false;

  const exemplos = {
    line: {
      answer: 'Neste cenário fictício, as linhas 591 e 562 aparecem com os maiores percentuais médios de ocupação. Em uma integração real, o assistente consultaria os registros consolidados e apresentaria o período analisado.',
      sql: "SELECT l.numero, ROUND(AVG(d.media_percentual), 1) AS ocupacao_media\nFROM resumos_dia d\nJOIN linhas l ON l.id = d.linha_id\nGROUP BY l.id\nORDER BY ocupacao_media DESC\nLIMIT 5;"
    },
    time: {
      answer: 'Neste exemplo, a curva ilustrativa destaca maior demanda no fim da tarde. Uma análise real compararia dias equivalentes e consideraria calendário, linha e condições climáticas.',
      sql: "SELECT hora, ROUND(AVG(media_percentual), 1) AS ocupacao_media\nFROM v_relatorio_linha_hora\nGROUP BY hora\nORDER BY hora;"
    },
    generic: {
      answer: 'Esta é uma resposta de demonstração. Na versão integrada, a pergunta seria interpretada pelo módulo InfoFrota AI e o contexto relevante do banco seria recuperado antes da geração do SQL.',
      sql: "-- SQL demonstrativo; nenhuma consulta foi executada\nSELECT linha_numero, media_percentual\nFROM v_relatorio_linha_hora\nORDER BY media_percentual DESC\nLIMIT 10;"
    }
  };

  function mostrarResultado({ titulo, chip, status, statusKind, texto, tabela, sql, sqlRotulo, rodape }) {
    $('#resultTitle').textContent = titulo;
    $('#resultChip').textContent = chip;
    statusLine.className = `result-status ${status ? statusKind : 'hidden'}`;
    statusLine.textContent = status || '';
    answerText.textContent = texto || '';
    answerText.classList.toggle('hidden', !texto);
    tableBox.classList.toggle('hidden', !tabela);
    tableBox.replaceChildren(...(tabela ? [tabela] : []));
    sqlLabel.classList.toggle('hidden', !sql);
    sqlText.classList.toggle('hidden', !sql);
    sqlLabel.textContent = sqlRotulo || '';
    sqlText.textContent = sql || '';
    foot.textContent = rodape || '';
    result.classList.remove('hidden');
  }

  function mostrarExemplo(text) {
    const t = text.toLowerCase();
    let item = exemplos.generic;
    if (/hor[aá]rio|hora|pico|ao longo do dia|chuva|clima/.test(t)) item = exemplos.time;
    else if (/linha|ocupa|lota|alerta/.test(t)) item = exemplos.line;
    mostrarResultado({
      titulo: 'EXEMPLO DE RESPOSTA', chip: 'Fictício', texto: item.answer, sql: item.sql, sqlRotulo: 'SQL ilustrativo · não executado',
      rodape: 'O módulo Text-to-SQL funciona via CLI e API em Python. Esta página estática não está conectada a ele; abra-a pela API local para consultar o banco experimental.'
    });
  }

  function montarTabela(colunas, linhas) {
    return el('table', {},
      el('thead', {}, el('tr', {}, ...colunas.map((c) => el('th', { scope: 'col', text: c })))),
      el('tbody', {}, ...linhas.map((linha) => el('tr', {}, ...linha.map((v) => el('td', { text: cel(v) })))))
    );
  }

  function mostrarResposta(r) {
    let status = '';
    let statusKind = 'info';
    let sqlRotulo = 'SQL gerado pelo modelo · executado em modo somente leitura';

    if (r.bloqueado) {
      [status, statusKind, sqlRotulo] = [`Consulta bloqueada pela proteção somente leitura: ${r.erro}`, 'warn', 'SQL gerado pelo modelo · bloqueado, não foi executado'];
    } else if (!r.pode_responder) {
      status = r.erro ? `Não consegui interpretar a saída do modelo: ${r.erro}` : `O assistente não pôde responder${r.motivo ? `: ${r.motivo}` : '.'}`;
    } else if (r.erro) {
      [status, statusKind, sqlRotulo] = [`A consulta falhou: ${r.erro}`, 'warn', 'SQL gerado pelo modelo · falhou na execução'];
    } else if (!r.linhas?.length) {
      status = 'A consulta rodou, mas não retornou linhas.';
    }

    const tabela = r.colunas?.length && r.linhas?.length ? montarTabela(r.colunas, r.linhas) : null;
    const rodape = [
      r.truncado ? `Mostrando só as primeiras ${r.linhas.length} linhas (limite do servidor).` : '',
      r.tentativas > 1 ? `Precisou de ${r.tentativas} tentativas (o SQL foi corrigido após um erro).` : '',
      r.nota || 'Dados sintéticos de demonstração.'
    ].filter(Boolean).join(' ');

    mostrarResultado({ titulo: 'RESPOSTA', chip: 'Dados sintéticos', status, statusKind, texto: r.texto, tabela, sql: r.sql, sqlRotulo, rodape });
  }

  function setBusy(value) {
    busy = value;
    submit.disabled = value;
    result.setAttribute('aria-busy', String(value));
    submitText.textContent = value ? 'Consultando…' : 'Perguntar';
    submit.classList.toggle('loading', value);
  }

  async function perguntarAoVivo(pergunta) {
    setBusy(true);
    try {
      const resposta = await api('/perguntar', { method: 'POST', body: { pergunta, texto: textoBox.checked }, timeout: 90000 });
      mostrarResposta(resposta);
      api('/saude', { timeout: 5000 }).then((saude) => { state.saude = saude; atualizarModelo(); }).catch(() => {});
    } catch (error) {
      mostrarResultado({ titulo: 'RESPOSTA', chip: 'Erro', status: mensagemDeErro(error), statusKind: 'error', rodape: 'Nada foi executado no banco.' });
    } finally {
      setBusy(false);
    }
  }

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    if (busy) return;
    const text = question.value.trim();
    if (text.length < 3) {
      question.setCustomValidity('Digite uma pergunta com pelo menos 3 caracteres.');
      question.reportValidity();
      question.setCustomValidity('');
      question.focus();
      return;
    }
    if (state.live) perguntarAoVivo(text);
    else mostrarExemplo(text);
  });

  question?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  $$('.suggestion').forEach((button) => {
    button.addEventListener('click', () => {
      question.value = button.textContent.trim();
      if (state.live) question.focus();
      else mostrarExemplo(question.value);
    });
  });

  /* ---------- Início ---------- */
  (async () => {
    await detectarApi();
    aplicarModo();
    if (state.live) carregarPainel();
  })();
})();
