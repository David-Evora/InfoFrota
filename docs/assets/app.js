(() => {
  const navItems = [...document.querySelectorAll('.nav-item')];
  const views = [...document.querySelectorAll('.view')];
  const breadcrumb = document.getElementById('breadcrumbCurrent');
  const sidebar = document.getElementById('sidebar');
  const mobileMenu = document.getElementById('mobileMenu');

  const labels = {
    overview: 'Visão geral',
    lines: 'Linhas',
    fleet: 'Frota',
    reports: 'Relatórios',
    assistant: 'Assistente IA'
  };

  function showView(name) {
    if (!labels[name]) return;
    navItems.forEach((item) => item.classList.toggle('active', item.dataset.view === name));
    views.forEach((view) => view.classList.toggle('active', view.id === `view-${name}`));
    breadcrumb.textContent = labels[name];
    sidebar.classList.remove('open');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (window.location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  }

  navItems.forEach((item) => item.addEventListener('click', () => showView(item.dataset.view)));
  mobileMenu?.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.querySelector('.brand')?.addEventListener('click', (event) => {
    event.preventDefault();
    showView('overview');
  });

  const initial = window.location.hash.replace('#', '');
  if (labels[initial]) showView(initial);

  const lineSearch = document.getElementById('lineSearch');
  lineSearch?.addEventListener('input', () => {
    const query = lineSearch.value.trim().toLowerCase();
    document.querySelectorAll('#linesTable tr').forEach((row) => {
      row.hidden = !row.textContent.toLowerCase().includes(query);
    });
  });

  const question = document.getElementById('assistantQuestion');
  const form = document.getElementById('assistantForm');
  const result = document.getElementById('assistantResult');
  const answerText = document.getElementById('answerText');
  const sqlText = document.getElementById('sqlText');

  const exampleResponse = {
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

  function displayExample(text) {
    const normalized = text.toLowerCase();
    let item = exampleResponse.generic;
    if (normalized.includes('linha') || normalized.includes('ocupação') || normalized.includes('lotação')) item = exampleResponse.line;
    else if (normalized.includes('hora') || normalized.includes('dia') || normalized.includes('demanda') || normalized.includes('pico')) item = exampleResponse.time;
    answerText.textContent = item.answer;
    sqlText.textContent = item.sql;
    result.classList.remove('hidden');
  }

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = question.value.trim();
    if (!text) {
      question.focus();
      question.setCustomValidity('Digite uma pergunta para visualizar o exemplo.');
      question.reportValidity();
      return;
    }
    question.setCustomValidity('');
    displayExample(text);
  });

  document.querySelectorAll('.suggestion').forEach((button) => {
    button.addEventListener('click', () => {
      question.value = button.textContent.trim();
      displayExample(question.value);
    });
  });
})();
