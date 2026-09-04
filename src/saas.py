"""
saas.py — Métricas SaaS (só p/ empresas de receita recorrente, ex.: FluxoData).

Calcula CAC, LTV, LTV/CAC, churn, MRR/ARR, NRR e payback a partir dos dados
operacionais (clientes, novos, perdidos, marketing, MRR). Números do código.
"""

from __future__ import annotations
import pandas as pd

MARGEM_BRUTA_SAAS = 0.80   # margem bruta típica de SaaS (usada no LTV)


def carregar(caminho):
    return pd.read_csv(caminho)


def metricas(df, margem=MARGEM_BRUTA_SAAS):
    novos = df["novos_clientes"].sum()
    mkt = df["marketing"].sum()
    cac = mkt / novos if novos else 0                     # custo de aquisição
    churn_m = df["churn_rate"].mean()                     # churn mensal médio
    arpa = df["arpa"].iloc[-1]                             # receita média por cliente/mês
    ltv = arpa * margem / churn_m if churn_m else 0       # valor do tempo de vida
    payback = cac / (arpa * margem) if arpa else 0        # meses p/ recuperar o CAC
    mrr = df["mrr"].iloc[-1]
    nrr_m = (1 - df["churn_rate"] + df["expansion_mrr"] / df["mrr"]).mean()  # NRR mensal
    return {
        "clientes": int(df["clientes_fim"].iloc[-1]),
        "mrr": mrr, "arr": mrr * 12, "arpa": arpa,
        "cac": cac, "ltv": ltv, "ltv_cac": ltv / cac if cac else 0,
        "payback_meses": payback,
        "churn_mensal": churn_m, "churn_anual": 1 - (1 - churn_m) ** 12,
        "nrr_mensal": nrr_m, "nrr_anual": nrr_m ** 12,
        "churn_pico": df.loc[df["churn_rate"].idxmax(), "competencia"],
    }
