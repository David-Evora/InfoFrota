---
title: InfoFrota AI - agente de dados
emoji: 🚌
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.32.0
app_file: app.py
pinned: false
license: mit
short_description: Agente que consulta um banco sintético de lotação de ônibus
---

Demo do agente do [InfoFrota AI](https://github.com/David-Evora/InfoFrota): pergunta em português, o modelo consulta o banco SQLite (somente leitura) em vários passos com Tool Calling e responde.

Os dados são sintéticos (linhas reais da CETURBES; frota, viagens e lotação gerados por código com semente fixa) e não representam a operação real. Projeto independente, sem endosso da CETURB/ES.
