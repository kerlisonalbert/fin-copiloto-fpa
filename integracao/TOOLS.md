# TOOLS.md — Notas locais desta máquina

Skills dizem *como* as ferramentas funcionam. Este arquivo diz *onde as coisas
estão nesta máquina* e *como o Kerlison gosta que sejam usadas*.

---

## Copiloto de FP&A — a análise financeira

Ferramenta de análise de fechamento: orçado × realizado, ~30 indicadores,
fluxo de caixa (DFC), métricas SaaS e um dashboard HTML.

**Pasta do projeto:**
`C:\Users\kerli\Curso de Agentes de IA - Financas e Governanca\fin-copiloto-fpa`

### Como chamar — copie a linha EXATAMENTE, incluindo o `&` do início

```
& "C:\Users\kerli\Curso de Agentes de IA - Financas e Governanca\fin-copiloto-fpa\oraculo.cmd" fluxodata
```

> ⚠️ Três detalhes que fazem a chamada falhar se forem esquecidos:
> 1. O **`&`** no início é **obrigatório**. No PowerShell, um caminho entre aspas
>    sem o `&` é tratado como texto, não como comando — retorna `exitCode 1`.
> 2. As **aspas** são obrigatórias — o caminho tem espaços.
> 3. Use o caminho **absoluto** começando em `C:\Users\kerli`. Não use `~` nem
>    `%USERPROFILE%`: dependendo do shell eles não são expandidos.
> 4. **Não use `cd` nem `&&`.** Este Windows roda PowerShell 5.1, que **não
>    entende `&&`** (erro: `token '&&'`). Rode a linha única acima, direto.
>    O `oraculo.cmd` resolve os caminhos sozinho — não precisa entrar na pasta.

Troque `fluxodata` pela empresa e acrescente a flag conforme o pedido:

| Pedido do Kerlison | Termina o comando com |
|---|---|
| "analisa a FluxoData" | `fluxodata` |
| "analisa com a IA" / "escreve o comentário" | `fluxodata --ia` |
| "gera o dashboard" / "quero o relatório" | `fluxodata --dash` |

Sem flag = modo **offline** (determinístico, não gasta crédito). É o padrão.
Use `--ia` **somente** quando ele pedir a narrativa explicitamente.

### Empresas disponíveis (dados sintéticos de demonstração)

| Como o Kerlison pede | Parâmetro |
|---|---|
| "Construtora", "Horizonte", "a construtora" | `construtora-horizonte` |
| "FluxoData", "o SaaS", "a de software" | `fluxodata` |
| "BomPreço", "o varejo", "o supermercado" | `rede-bompreco` |

### O que fazer com o resultado

1. Rode o comando e **leia a saída**.
2. Responda com os números **que saíram na saída**, citando competência e conta.
3. Destaque o **mês crítico** e o **maior desvio desfavorável** primeiro.
4. Ofereça o dashboard (`--dash`) se a conversa pedir mais profundidade.

### Ao gerar o dashboard (`--dash`)

O comando produz **dois arquivos**, sempre nesta pasta (sem espaços, de propósito):

```
C:\Users\kerli\.openclaw\workspace\relatorios\relatorio-<empresa>.png    <- ANEXE ESTE
C:\Users\kerli\.openclaw\workspace\relatorios\relatorio-<empresa>.html   <- so cite no texto
```

E imprime as duas linhas: `Relatório gerado: ...html` e `Imagem gerada: ...png`.

**O que fazer:**

1. **Anexe o `.png`** — é a imagem do dashboard e o Telegram entrega imagem sem
   problema. Use o caminho exatamente como veio impresso em `Imagem gerada:`.
2. Mencione no texto que o HTML interativo está na pasta `relatorios`, para ele
   abrir no computador quando quiser.
3. Resuma em 2–3 linhas o que o dashboard mostra (mês crítico, principal desvio).

> ⚠️ **Nunca tente anexar o `.html`.** A camada de entrega só envia
> imagem/áudio/vídeo como media — um HTML falha com `Media failed`.
>
> ⚠️ **Nunca cite o caminho da pasta do projeto**
> (`C:\Users\kerli\Curso de Agentes de IA - ...`) na mensagem. Ele tem espaços,
> e a camada de anexo quebra o caminho no primeiro espaço.
>
> Se sair `AVISO: nao foi possivel gerar a imagem PNG`, diga isso ao Kerlison e
> informe o caminho do HTML. Não invente que enviou a imagem.

---

## Regras inegociáveis ao usar esta ferramenta

- **Nunca invente ou estime um número.** Todo valor citado tem que ter saído da
  execução do comando. Se você não rodou, você não sabe.
- **Se o comando falhar**, mostre o erro e diga que não conseguiu. Não preencha
  a lacuna com estimativa.
- **Não dê recomendação de investimento.** A análise é gerencial e educacional.
- **Rastreabilidade:** todo número vem acompanhado da competência (AAAA-MM) e da
  conta de origem.
- **Antes de qualquer ação crítica** (apagar arquivo, alterar dado, enviar algo
  para fora da máquina), pergunte primeiro. Human-in-the-loop.
- Os dados destas 3 empresas são **sintéticos**, feitos para demonstração.
  Nunca os apresente como dados reais de empresa.

## Formatação no Telegram

O Telegram renderiza mal tabelas. Ao responder por lá, use **listas com marcador**
e negrito, nunca tabela em markdown. Seja direto: o achado principal primeiro,
o detalhe depois.
