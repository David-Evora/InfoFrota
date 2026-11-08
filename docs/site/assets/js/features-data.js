/* Catálogo de funcionalidades. Fonte da verdade: o repositório.
   Cada item cita arquivos reais em `evidence`; tests/test_site.py confere que todos existem.
   status: impl (implementado) | exp (experimental) | val (em validação) | plan (planejado). */
window.IF_FEATURES = {
  cats: [
    { id: "ia", nome: "Inteligência artificial", icon: "i-bot" },
    { id: "dados", nome: "Dados", icon: "i-database" },
    { id: "alertas", nome: "Alertas e automação", icon: "i-bell" },
    { id: "api", nome: "API e integrações", icon: "i-plug" },
    { id: "seg", nome: "Segurança", icon: "i-shield-check" },
    { id: "plat", nome: "Plataforma", icon: "i-layout-dashboard" },
    { id: "plan", nome: "Em estudo", icon: "i-flask-conical" }
  ],
  status: {
    impl: "Implementado",
    exp: "Experimental",
    val: "Em validação",
    plan: "Planejado"
  },
  items: [
    {
      id: "text2sql", cat: "ia", status: "impl", wide: true, icon: "i-terminal",
      titulo: "Text-to-SQL em português",
      resumo: "Transforma uma pergunta em linguagem natural em uma consulta SQL e devolve o resultado em tabela.",
      detalhe: "O assistente monta um prompt com o esquema recuperado, pede o SQL ao modelo, interpreta a resposta e executa só depois de passar pela guarda de leitura. Perguntas fora do escopo recebem recusa explícita em vez de um SQL inventado.",
      evidence: ["infofrota_ai/assistant.py", "infofrota_ai/prompts.py", "tests/test_core.py"]
    },
    {
      id: "rag", cat: "ia", status: "impl", icon: "i-search",
      titulo: "RAG de esquema (BM25)",
      resumo: "Recupera tabelas, valores válidos e regras do domínio relevantes para cada pergunta.",
      detalhe: "O índice é lexical (BM25) e usa apenas o banco e as regras do domínio. O benchmark de avaliação nunca entra no índice, para não contaminar a medição.",
      evidence: ["infofrota_ai/rag.py", "tests/test_rag.py"]
    },
    {
      id: "provedores", cat: "ia", status: "impl", icon: "i-plug",
      titulo: "Provedores de LLM intercambiáveis",
      resumo: "Anthropic, API compatível com OpenAI (como a Groq) ou um modelo local com Hugging Face e PEFT.",
      detalhe: "O provedor é escolhido por variáveis de ambiente. A chave fica no backend e nunca é enviada ao navegador.",
      evidence: ["infofrota_ai/llm.py", "infofrota_ai/hf_llm.py"]
    },
    {
      id: "reparo", cat: "ia", status: "impl", icon: "i-repeat",
      titulo: "Reparo automático de SQL",
      resumo: "Se a consulta falha, o modelo recebe o erro e tenta corrigir uma única vez.",
      detalhe: "Uma tentativa de reparo, não um laço aberto: o custo e a latência ficam limitados.",
      evidence: ["infofrota_ai/assistant.py"]
    },
    {
      id: "lora", cat: "ia", status: "exp", icon: "i-flask-conical",
      titulo: "Fine-tuning LoRA do Llama 3.1 8B",
      resumo: "Adaptação QLoRA treinada no Kaggle sobre pares de pergunta e SQL.",
      detalhe: "Os adaptadores treinados não estão versionados no repositório. O relatório de treino registra os filtros usados para reduzir similaridade entre treino e teste.",
      evidence: ["kaggle/train_lora.py", "training/REPORT.md"]
    },
    {
      id: "benchmark", cat: "ia", status: "exp", icon: "i-chart-column",
      titulo: "Benchmark congelado de 56 perguntas",
      resumo: "Avalia base, RAG e LoRA nas mesmas perguntas, por nível de dificuldade.",
      detalhe: "Resultados de experimento com uma base sintética e 56 perguntas. Diferenças de um ou dois acertos são ruído, e os números não medem desempenho em operação real.",
      evidence: ["infofrota_ai/evaluate.py", "docs/experiments.md", "evaluation/questions.json"]
    },
    {
      id: "sqlite", cat: "dados", status: "exp", icon: "i-database",
      titulo: "Base experimental sintética",
      resumo: "Banco SQLite gerado por script, com linhas, paradas, ocupação por hora, clima e calendário.",
      detalhe: "Os dados são simulados e declarados como tal em toda a interface. A base não é versionada: ela é gerada localmente por scripts/generate_data.py.",
      evidence: ["scripts/generate_data.py", "db/schema.sql"]
    },
    {
      id: "linhas", cat: "dados", status: "impl", icon: "i-route",
      titulo: "Rótulos reais de linhas",
      resumo: "Números e nomes de linhas vindos de um CSV aberto (CC0) da CETURB-ES.",
      detalhe: "Só os rótulos das linhas são reais. A ocupação, os horários e os alertas associados são sintéticos.",
      evidence: ["data/linhas_ceturbes.csv", "scripts/generate_data.py"]
    },
    {
      id: "resumo", cat: "dados", status: "impl", icon: "i-activity",
      titulo: "Resumo diário por linha",
      resumo: "Endpoint com ocupação média, picos e contagem de alertas, com filtro por linha e tipo.",
      detalhe: "Alimenta a API e as visualizações do protótipo com dados sintéticos.",
      evidence: ["infofrota_ai/api.py", "tests/test_api.py"]
    },
    {
      id: "limiares", cat: "alertas", status: "impl", icon: "i-triangle-alert",
      titulo: "Alertas de lotação em dois níveis",
      resumo: "Atenção a partir de 75% e crítico a partir de 90% de ocupação.",
      detalhe: "Cada alerta guarda percentual, parada, horário, se foi resolvido e se houve ação de precaução. O percentual pode passar de 100.",
      evidence: ["infofrota_ai/api.py", "scripts/generate_data.py", "db/schema.sql"]
    },
    {
      id: "n8n", cat: "alertas", status: "val", wide: true, icon: "i-workflow",
      titulo: "Workflow n8n de alerta crítico",
      resumo: "A cada cinco minutos consulta a API, descarta alertas já enviados e notifica um webhook.",
      detalhe: "A deduplicação usa o armazenamento do próprio workflow e só registra os IDs depois que o envio é confirmado. A persistência entre execuções ainda precisa ser validada com o workflow ativo, por isso o item é marcado como em validação.",
      evidence: ["n8n/alerta-critico.json", "compose.yaml"]
    },
    {
      id: "webhook", cat: "alertas", status: "impl", icon: "i-webhook",
      titulo: "Notificação por webhook",
      resumo: "A mensagem é montada no workflow e enviada a um webhook compatível com Discord ou Slack.",
      detalhe: "A URL do webhook é configurada na instância do n8n. Nenhuma URL real está no repositório.",
      evidence: ["n8n/alerta-critico.json"]
    },
    {
      id: "fastapi", cat: "api", status: "impl", icon: "i-server",
      titulo: "API FastAPI com quatro rotas",
      resumo: "Saúde, perguntar, alertas e resumo. O modelo só é carregado na primeira pergunta.",
      detalhe: "Rotas: /saude, /perguntar, /alertas e /resumo. O único site do projeto é servido pela API na raiz.",
      evidence: ["infofrota_ai/api.py", "tests/test_api.py"]
    },
    {
      id: "compose", cat: "api", status: "impl", icon: "i-container",
      titulo: "Docker Compose com API e n8n",
      resumo: "Dois serviços prontos para subir juntos. A API é publicada apenas em 127.0.0.1.",
      detalhe: "Pensado para rodar na máquina do desenvolvedor. Não é uma configuração de produção.",
      evidence: ["compose.yaml", "Dockerfile.api"]
    },
    {
      id: "auth", cat: "api", status: "impl", icon: "i-key-round",
      titulo: "Chave de API e limite por minuto",
      resumo: "Autenticação opcional por X-API-Key e limite de requisições por IP.",
      detalhe: "Ambos são opcionais e configurados por variável de ambiente. Não substituem a revisão necessária antes de qualquer exposição pública.",
      evidence: ["infofrota_ai/api.py", "tests/test_api.py"]
    },
    {
      id: "guarda", cat: "seg", status: "impl", icon: "i-shield-check",
      titulo: "Guarda SQL somente leitura",
      resumo: "Três camadas: instrução única SELECT/WITH, authorizer do SQLite e conexão mode=ro.",
      detalhe: "Há ainda limite de 200 linhas e de 5 segundos por consulta. Uma instrução como DELETE é barrada antes de tocar no banco.",
      evidence: ["infofrota_ai/db.py", "tests/test_core.py"]
    },
    {
      id: "web", cat: "plat", status: "impl", icon: "i-layout-dashboard",
      titulo: "Site de apresentação",
      resumo: "Página institucional estática com catálogo de funcionalidades, demonstrações, visualizações e arquitetura interativa.",
      detalhe: "Este é o único frontend do projeto. É servido pela API em / e pode ser publicado diretamente pelo GitHub Pages a partir de docs/site/.",
      evidence: ["docs/site/index.html", "docs/site/assets/js/core.js", "docs/site/README.md", "tests/test_site.py"]
    },
    {
      id: "embarcada", cat: "plan", status: "plan", icon: "i-cpu",
      titulo: "Captação embarcada de passageiros",
      resumo: "Ideia: estimar embarques, desembarques e ocupação dentro do veículo por visão computacional.",
      detalhe: "Está apenas descrita na documentação de arquitetura como conceito em estudo. Não há firmware, modelo de visão nem hardware validado neste repositório.",
      evidence: ["docs/architecture.md"]
    },
    {
      id: "real", cat: "plan", status: "plan", icon: "i-globe",
      titulo: "Dados operacionais autorizados",
      resumo: "Integrar fontes reais somente com autorização de quem detém os dados.",
      detalhe: "Hoje não existe nenhuma integração com dados operacionais reais, nem parceria ou endosso institucional.",
      evidence: ["docs/architecture.md"]
    },
    {
      id: "hardening", cat: "plan", status: "plan", icon: "i-lock",
      titulo: "Autenticação e hardening de produção",
      resumo: "Revisar autenticação, autorização, TLS, exposição de rede e logs antes de qualquer uso fora do ambiente local.",
      detalhe: "A chave de API opcional existente é um primeiro passo, não um sistema de autenticação completo.",
      evidence: ["README.md", "docs/INFOFROTA_AI.md"]
    }
  ]
};
