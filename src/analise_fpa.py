"""
analise_fpa.py — O "motor de cálculo" do Copiloto de FP&A (Oráculo).

PRINCÍPIO CENTRAL DO CASE: os números vêm do CÓDIGO (aqui), nunca da IA.
Estas funções calculam tudo de forma determinística e auditável. Depois,
o agente (Oráculo) apenas INTERPRETA e COMENTA esses resultados — ele nunca
inventa uma cifra. Isso é o que dá credibilidade num contexto financeiro.

Funciona com QUALQUER planilha no formato padrão (BYOD — bring your own data):
colunas mínimas -> competencia (AAAA-MM), conta, orcado, realizado.
"""

from __future__ import annotations
import pandas as pd

# Colunas obrigatórias no arquivo de entrada
COLUNAS_OBRIGATORIAS = ["competencia", "conta", "orcado", "realizado"]


# ---------------------------------------------------------------------------
# 1) CARREGAR E VALIDAR (a "portaria" dos dados)
# ---------------------------------------------------------------------------
def carregar_dre(caminho: str) -> pd.DataFrame:
    """Lê um CSV de DRE e valida o formato. Erro claro se algo faltar."""
    df = pd.read_csv(caminho)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(
            f"Planilha inválida: faltam as colunas {faltando}. "
            f"O formato esperado é: {COLUNAS_OBRIGATORIAS} "
            f"(competencia no formato AAAA-MM)."
        )
    # Garante tipos numéricos (se vier texto, converte; erro vira NaN)
    df["orcado"] = pd.to_numeric(df["orcado"], errors="coerce")
    df["realizado"] = pd.to_numeric(df["realizado"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# 2) POLARIDADE DE CADA CONTA (o que é "bom" quando sobe?)
# ---------------------------------------------------------------------------
def _polaridade(conta: str) -> str:
    """
    Diz se, para aquela conta, 'realizado > orçado' é bom ou ruim.
    - Receita/Lucro/EBITDA: quanto MAIOR, melhor.
    - Custo/CMV/Despesa: quanto MENOR, melhor.
    Funciona também para contas do usuário (BYOD), pelo nome.
    """
    c = conta.lower()
    if any(t in c for t in ["receita", "lucro", "ebitda", "resultado", "margem"]):
        return "maior_melhor"
    if any(t in c for t in ["custo", "cmv", "cpv", "despesa", "gasto"]):
        return "menor_melhor"
    return "maior_melhor"  # padrão seguro


def _classificar(conta: str, variacao: float) -> str:
    """Favorável ou Desfavorável, considerando a polaridade da conta."""
    if variacao == 0:
        return "Neutro"
    bom_subir = _polaridade(conta) == "maior_melhor"
    subiu = variacao > 0
    return "Favorável" if (bom_subir == subiu) else "Desfavorável"


# ---------------------------------------------------------------------------
# 3) ANÁLISE ORÇADO vs REALIZADO (o coração do FP&A)
# ---------------------------------------------------------------------------
def variacoes(df: pd.DataFrame, materialidade: float = 0.05) -> pd.DataFrame:
    """
    Calcula, por competência e conta:
      - variacao_abs  = realizado - orcado
      - variacao_pct  = variacao_abs / orcado
      - tipo          = Favorável / Desfavorável (respeitando a polaridade)
      - material      = True se |variacao_pct| >= materialidade (ex.: 5%)
    Cada linha do resultado É a "fonte" (competência + conta) que o Oráculo cita.
    """
    r = df.copy()
    r["variacao_abs"] = r["realizado"] - r["orcado"]
    # evita divisão por zero
    r["variacao_pct"] = r.apply(
        lambda x: (x["variacao_abs"] / x["orcado"]) if x["orcado"] else 0.0, axis=1
    )
    r["tipo"] = r.apply(lambda x: _classificar(x["conta"], x["variacao_abs"]), axis=1)
    r["material"] = r["variacao_pct"].abs() >= materialidade
    return r[["competencia", "conta", "orcado", "realizado",
              "variacao_abs", "variacao_pct", "tipo", "material"]]


def achados(df: pd.DataFrame, materialidade: float = 0.05,
            top: int = 5) -> pd.DataFrame:
    """
    Os "achados": os maiores desvios DESFAVORÁVEIS e MATERIAIS.
    É o que o Oráculo aponta primeiro — o que exige atenção.
    """
    v = variacoes(df, materialidade)
    ruins = v[(v["tipo"] == "Desfavorável") & (v["material"])].copy()
    ruins["impacto"] = ruins["variacao_pct"].abs()
    return ruins.sort_values("impacto", ascending=False).head(top)


# ---------------------------------------------------------------------------
# 4) DRE DE UM MÊS (fechamento)
# ---------------------------------------------------------------------------
def dre_competencia(df: pd.DataFrame, competencia: str) -> pd.DataFrame:
    """Monta a DRE (orçado, realizado, variação) de uma competência."""
    mes = df[df["competencia"] == competencia].copy()
    if mes.empty:
        raise ValueError(f"Sem dados para a competência {competencia}.")
    mes["variacao_abs"] = mes["realizado"] - mes["orcado"]
    return mes[["conta", "orcado", "realizado", "variacao_abs"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5) KPIs / MARGENS (saúde)
# ---------------------------------------------------------------------------
def kpis_mensais(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula margens por competência (orçado e realizado):
      - margem_bruta = Lucro Bruto / Receita Líquida
      - margem_ebitda = EBITDA / Receita Líquida
    Só usa contas que existirem na planilha (robusto p/ BYOD).
    """
    def _valor(mes_df, conta, coluna):
        linha = mes_df[mes_df["conta"].str.lower() == conta.lower()]
        return float(linha[coluna].iloc[0]) if not linha.empty else None

    linhas = []
    for comp, mes_df in df.groupby("competencia"):
        rec_o = _valor(mes_df, "Receita Líquida", "orcado")
        rec_r = _valor(mes_df, "Receita Líquida", "realizado")
        lb_o = _valor(mes_df, "Lucro Bruto", "orcado")
        lb_r = _valor(mes_df, "Lucro Bruto", "realizado")
        eb_o = _valor(mes_df, "EBITDA", "orcado")
        eb_r = _valor(mes_df, "EBITDA", "realizado")
        linhas.append({
            "competencia": comp,
            "margem_bruta_orc": (lb_o / rec_o) if rec_o and lb_o is not None else None,
            "margem_bruta_real": (lb_r / rec_r) if rec_r and lb_r is not None else None,
            "margem_ebitda_orc": (eb_o / rec_o) if rec_o and eb_o is not None else None,
            "margem_ebitda_real": (eb_r / rec_r) if rec_r and eb_r is not None else None,
        })
    return pd.DataFrame(linhas).sort_values("competencia").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Demonstração rápida (rodar: python src/analise_fpa.py caminho.csv)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    caminho = sys.argv[1] if len(sys.argv) > 1 else "dados/dre-construtora-horizonte.csv"
    df = carregar_dre(caminho)
    print(f"Arquivo: {caminho}  ({df['competencia'].nunique()} meses)\n")
    print("TOP ACHADOS (desvios desfavoráveis materiais):")
    ach = achados(df, materialidade=0.05)
    for _, a in ach.iterrows():
        print(f"  - {a['competencia']} | {a['conta']}: "
              f"{a['variacao_pct']*100:+.1f}%  "
              f"(orçado {a['orcado']:,.0f} -> realizado {a['realizado']:,.0f})")
