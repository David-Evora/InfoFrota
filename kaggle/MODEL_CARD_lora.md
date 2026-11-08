---
language: pt
license: llama3.1
base_model: meta-llama/Llama-3.1-8B-Instruct
library_name: peft
tags:
  - text-to-sql
  - lora
  - qlora
  - portuguese
  - sqlite
---

# InfoFrota Text-to-SQL (adaptador LoRA para Llama 3.1 8B Instruct)

Adaptador LoRA que ensina o Llama 3.1 8B Instruct a transformar perguntas em português em consultas SQLite para o banco **sintético** do projeto InfoFrota (ocupação de ônibus, alertas de lotação, linhas e paradas).

- Código, dados sintéticos e benchmark: https://github.com/David-Evora/InfoFrota
- Projeto independente. Não tem endosso nem parceria com órgãos ou operadoras de transporte. Só os rótulos das linhas vêm de um CSV aberto (CC0) da CETURB-ES.

## Uso pretendido e limites

Pesquisa e demonstração de Text-to-SQL em português sobre o esquema do InfoFrota. **Não use em produção** nem para decisões operacionais: o modelo foi treinado e medido apenas em dados simulados, e o SQL gerado deve sempre passar por uma guarda somente leitura (o repositório traz uma, em três camadas).

## Treino

- Base: `meta-llama/Llama-3.1-8B-Instruct`, quantização 4 bits (nf4), QLoRA.
- LoRA: r=16, alpha=32, dropout 0,05, nos módulos q, k, v, o, gate, up e down.
- 3 épocas, lote efetivo 16, taxa de aprendizado 2e-4 com cosseno. GPU T4 no Kaggle.
- Dados: 738 exemplos construídos por famílias de modelos de pergunta e SQL (679 treino, 59 validação), 8% de recusas para perguntas fora do domínio ou pedidos de escrita.
- Filtros contra vazamento do teste (similaridade de Jaccard, esqueleto de SQL, famílias próximas excluídas): ver `training/REPORT.md` no repositório.

## Avaliação

Benchmark congelado v2.1 com 56 perguntas (15 fáceis, 20 médias, 15 difíceis, 6 de limite), zero-shot, critério "o resultado contém o esperado".

| Condição | Acertos | Acurácia |
|---|---:|---:|
| Base, prompt compacto | 19/56 | 33,9% |
| Este adaptador, prompt compacto | 36/56 | 64,3% |
| Base + RAG de esquema (prompt ultra) | 28/56 | 50,0% |
| Variante treinada com contexto recuperado + RAG (prompt ultra) | 39/56 | 69,6% |

Leitura honesta dos números:
- Com 56 perguntas, diferenças de um ou dois acertos são ruído.
- A segunda rodada (variante com contexto, prompt ultra) foi planejada depois de analisar os erros da primeira.
- O nível difícil continua baixo: 3 de 15 no melhor caso.
- A pergunta D06 tem defeito conhecido na referência; a pontuação publicada não foi ajustada depois de ver o resultado.
- Os números vêm de dados sintéticos e não medem desempenho em operação real.

## Como carregar

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

base = "meta-llama/Llama-3.1-8B-Instruct"
tok = AutoTokenizer.from_pretrained(base)
modelo = AutoModelForCausalLM.from_pretrained(
    base, device_map="auto",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4"))
modelo = PeftModel.from_pretrained(modelo, "David-Evora/infofrota-text2sql-lora")
```

O prompt esperado está em `infofrota_ai/prompts.py` (modo `compacto`). Use a licença e os termos de uso do Llama 3.1 ao redistribuir.
