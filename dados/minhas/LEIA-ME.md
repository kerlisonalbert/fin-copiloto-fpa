# Suas planilhas ficam aqui

Esta pasta está no `.gitignore`: **nada daqui vai para o GitHub**. É o lugar certo
para dado de empresa real.

## Como nomear

Para uma empresa que você vai chamar de `acme`:

```
dados/minhas/dre-acme.csv       (obrigatorio)
dados/minhas/balanco-acme.csv   (opcional - so necessario para o --dash completo)
```

Depois é só chamar pelo nome:

```
oraculo.cmd acme
oraculo.cmd acme --dash
```

## Formato

Quatro colunas obrigatórias, exatamente com estes nomes:

| coluna | o que é | exemplo |
|---|---|---|
| `competencia` | mês, no formato AAAA-MM | `2026-01` |
| `conta` | nome da linha da DRE ou do balanço | `Receita Líquida` |
| `orcado` | valor orçado / plano | `1000000` |
| `realizado` | valor realizado | `942300` |

Use `dados/MODELO-dre.csv` e `dados/MODELO-balanco.csv` como ponto de partida.

## Regras que evitam dor de cabeça

- **Ponto como separador decimal** (`942300.55`), não vírgula. Salve o CSV em UTF-8.
- **Sem separador de milhar** e sem `R$` — só o número.
- A polaridade é deduzida do **nome da conta**: contas com "receita", "lucro",
  "ebitda", "resultado" são *maior é melhor*; com "custo", "cmv", "despesa",
  "gasto" são *menor é melhor*. Nomeie suas contas com essas palavras.
- Para o balanço, use os nomes de conta do `MODELO-balanco.csv` — os indicadores
  (liquidez, Fleuriet, solvência) procuram por eles.

## Governança (leia antes de usar dado real)

- Dado de cliente **não sai desta máquina** no modo padrão (offline). Só o modo
  `--ia` envia o resumo para a API do modelo — pense nisso antes de usá-lo.
- Nunca commite esta pasta. O `.gitignore` protege, mas confira com
  `git status --short` antes de qualquer `git add`.
- Sem nome de pessoa física, CPF ou dado pessoal nas contas (LGPD). Trabalhe
  sempre com contas contábeis agregadas.
