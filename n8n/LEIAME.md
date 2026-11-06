# Alerta de lotação crítica no n8n

Workflow: **a cada 5 minutos** consulta `GET /alertas?tipo=CRITICO&janela_horas=24`; se houver alertas, monta uma mensagem e envia para um webhook (Slack ou Discord).

1. Suba a API: `pip install -r requirements-api.txt` e `python -m infofrota_ai.api`.
2. No n8n: **Workflows > Import from file** e escolha `alerta-critico.json`.
3. No nó **Configuração**, ajuste `api_url`, `api_key` (só se definiu `INFOFROTA_API_KEY`) e `webhook_url`. Se o n8n roda em Docker e a API na sua máquina, use `http://host.docker.internal:8000`.
4. Execute uma vez com **Test workflow** antes de ativar.

Como os dados são sintéticos e terminam em 03/11/2026, o "agora" do `/alertas` é o horário do último alerta do banco; por isso o alerta sempre dispara na demonstração. Com dados reais, o mesmo workflow serve sem mudança.

O workflow não foi importado em uma instância do n8n por quem o escreveu (só o formato JSON foi validado). Se algum nó aparecer com erro, ajuste na interface; a API em si tem testes automatizados.
