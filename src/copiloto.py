"""
copiloto.py — O Oráculo: junta o MOTOR (números) com a IA (narrativa).

Fluxo (é aqui que "números vêm do código, narrativa vem da IA" acontece):
  1. Carrega a planilha (sintética ou a do usuário — BYOD).
  2. O MOTOR (analise_fpa) calcula os desvios, achados e margens.
  3. Monta um "briefing" só com números REAIS calculados (a fonte da verdade).
  4. A IA recebe o briefing e escreve o comentário — proibida de inventar número.

Uso:
  python src/copiloto.py dados/dre-construtora-horizonte.csv
  python src/copiloto.py minha-planilha.csv --offline      (sem IA, determinístico)
  python src/copiloto.py dados/dre-fluxodata.csv --materialidade 0.05

Governança embutida: a IA só usa os números do briefing, cita a fonte,
não dá recomendação de investimento e admite quando não sabe.
"""

from __future__ import annotations
import os
import argparse
import pandas as pd

import analise_fpa as motor

# Carrega variáveis do .env, se python-dotenv estiver instalado (opcional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ---------------------------------------------------------------------------
# 1) BRIEFING — o pacote de números REAIS que a IA vai narrar
# ---------------------------------------------------------------------------
def montar_briefing(df: pd.DataFrame, materialidade: float) -> dict:
    """Reúne os fatos calculados pelo motor (nada aqui é 'chutado')."""
    empresa = df["empresa"].iloc[0] if "empresa" in df.columns else "empresa analisada"
    setor = df["setor"].iloc[0] if "setor" in df.columns else "não informado"
    meses = sorted(df["competencia"].unique())

    ach = motor.achados(df, materialidade=materialidade, top=6)

    # "Mês crítico" = a competência com o maior desvio desfavorável
    mes_critico = ach["competencia"].iloc[0] if not ach.empty else meses[-1]
    dre = motor.dre_competencia(df, mes_critico)
    kpis = motor.kpis_mensais(df)

    return {
        "empresa": empresa,
        "setor": setor,
        "periodo": f"{meses[0]} a {meses[-1]}",
        "materialidade_pct": materialidade * 100,
        "mes_critico": mes_critico,
        "achados": ach.to_dict("records"),
        "dre_mes_critico": dre.to_dict("records"),
        "kpis": kpis.to_dict("records"),
    }


def _fmt(v):
    return f"R$ {v:,.0f}"


def briefing_em_texto(b: dict) -> str:
    """Transforma o briefing (números) num texto que a IA lê como fonte."""
    linhas = [
        f"Empresa: {b['empresa']} | Setor: {b['setor']}",
        f"Período analisado: {b['periodo']}",
        f"Materialidade (limite p/ sinalizar): {b['materialidade_pct']:.0f}%",
        f"Mês crítico identificado: {b['mes_critico']}",
        "",
        "DESVIOS MATERIAIS DESFAVORÁVEIS (orçado -> realizado):",
    ]
    for a in b["achados"]:
        linhas.append(
            f"  - {a['competencia']} | {a['conta']}: {a['variacao_pct']*100:+.1f}% "
            f"({_fmt(a['orcado'])} -> {_fmt(a['realizado'])})"
        )
    linhas += ["", f"DRE do mês crítico ({b['mes_critico']}):"]
    for d in b["dre_mes_critico"]:
        linhas.append(
            f"  - {d['conta']}: orçado {_fmt(d['orcado'])} | "
            f"realizado {_fmt(d['realizado'])} | desvio {_fmt(d['variacao_abs'])}"
        )
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# 2) NARRATIVA OFFLINE (determinística, sem IA) — fallback e base dos testes
# ---------------------------------------------------------------------------
def narrar_offline(b: dict) -> str:
    empresa, mes = b["empresa"], b["mes_critico"]
    do_mes = [a for a in b["achados"] if a["competencia"] == mes]
    if not do_mes:
        return (f"{empresa}: nenhum desvio acima de {b['materialidade_pct']:.0f}% "
                f"no período {b['periodo']}. Execução dentro do plano.")

    partes = [f"ANÁLISE — {empresa} ({b['setor']}) | período {b['periodo']}", ""]
    partes.append(f"Ponto de atenção em {mes}:")
    for a in do_mes:
        direcao = "acima" if a["variacao_abs"] > 0 else "abaixo"
        partes.append(
            f"  • {a['conta']} ficou {a['variacao_pct']*100:+.1f}% {direcao} do orçado "
            f"({_fmt(a['orcado'])} -> {_fmt(a['realizado'])})."
        )
    # leitura de margem no mês crítico
    kpi_mes = next((k for k in b["kpis"] if k["competencia"] == mes), None)
    if kpi_mes and kpi_mes.get("margem_ebitda_real") is not None:
        partes.append(
            f"\nMargem EBITDA em {mes}: {kpi_mes['margem_ebitda_real']*100:.1f}% "
            f"(plano: {kpi_mes['margem_ebitda_orc']*100:.1f}%)."
        )
    partes.append(
        f"\nRecomendação: investigar a causa-raiz em {mes} e revisar o forecast. "
        f"(Sinalizados apenas desvios acima de {b['materialidade_pct']:.0f}%.)"
    )
    partes.append(
        "\n— Números calculados a partir da planilha (rastreáveis). "
        "Não constitui recomendação de investimento."
    )
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# 3) NARRATIVA COM IA (o Oráculo escreve como um analista sênior)
# ---------------------------------------------------------------------------
SYSTEM_ORACULO = """Você é o Oráculo, um copiloto de FP&A. Escreva um comentário
gerencial curto e profissional (pt-BR), como um analista financeiro sênior.

REGRAS INVIOLÁVEIS:
- Use SOMENTE os números do briefing. Está proibido inventar ou estimar valores.
- Ao citar um número, referencie a fonte (competência e conta).
- Não dê recomendação de investimento. Foco é gestão/FP&A.
- Se algo não estiver no briefing, diga que não há dado suficiente.
- Tom profissional e direto, sem emojis. Destaque a causa provável do desvio
  e uma ação sugerida. Seja conciso (no máximo ~180 palavras)."""


def narrar_ia(b: dict, modelo: str) -> str:
    """Chama a API da Anthropic. Se falhar, cai no modo offline."""
    try:
        import anthropic
    except ImportError:
        return "[aviso: pacote 'anthropic' não instalado — usando modo offline]\n\n" + narrar_offline(b)

    try:
        client = anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente
        prompt = (
            "Comente a análise de FP&A abaixo. Use apenas estes números:\n\n"
            + briefing_em_texto(b)
        )
        resp = client.messages.create(
            model=modelo, max_tokens=600,
            system=SYSTEM_ORACULO,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        return (f"[aviso: não foi possível usar a IA ({e}). Modo offline abaixo.]\n\n"
                + narrar_offline(b))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Oráculo — copiloto de FP&A")
    p.add_argument("arquivo", help="CSV no formato: competencia, conta, orcado, realizado")
    p.add_argument("--offline", action="store_true", help="não usa IA (determinístico)")
    p.add_argument("--materialidade", type=float,
                   default=float(os.getenv("MATERIALIDADE", "0.05")),
                   help="limite p/ sinalizar desvio (ex.: 0.05 = 5%%)")
    p.add_argument("--modelo", default=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
                   help="modelo da IA (ou defina ANTHROPIC_MODEL no .env)")
    args = p.parse_args()

    df = motor.carregar_dre(args.arquivo)
    b = montar_briefing(df, args.materialidade)

    print("=" * 60)
    print("BRIEFING (números calculados pelo motor — a fonte da verdade)")
    print("=" * 60)
    print(briefing_em_texto(b))
    print("\n" + "=" * 60)
    print("ORÁCULO (narrativa " + ("offline" if args.offline else "com IA") + ")")
    print("=" * 60)
    print(narrar_offline(b) if args.offline else narrar_ia(b, args.modelo))


if __name__ == "__main__":
    main()
