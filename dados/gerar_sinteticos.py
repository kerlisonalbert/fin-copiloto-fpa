"""
gerar_sinteticos.py — Gera DRE + BALANÇO sintéticos (fictícios) das 3 empresas.

Por que sintético? Portfólio nunca usa dado real. Aqui geramos:
  - DRE mensal (orçado x realizado) com um "achado" plantado por empresa
  - Balanço Patrimonial coerente (recebíveis ~ PMR, estoques ~ PME, fornecedores ~ PMP)

O Balanço destrava os indicadores ricos: liquidez, capital de giro (Fleuriet/NCG),
ciclos (PMR/PME/PMP), alavancagem (dívida líq/EBITDA), ROIC, EVA, solvência.

Tudo determinístico (semente fixa) -> reprodutível (importante p/ os testes).

Saída (formato longo: competencia, conta, orcado, realizado):
  dre-<empresa>.csv       e   balanco-<empresa>.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
MESES = pd.period_range("2025-01", "2025-12", freq="M").astype(str).tolist()

CONTAS_DRE = ["Receita Líquida", "CMV", "Lucro Bruto",
              "Despesas Comerciais", "Despesas Administrativas", "EBITDA"]

CONTAS_BAL = [
    # Ativo
    "Caixa e equivalentes", "Contas a receber", "Estoques", "Impostos a recuperar",
    "Ativo circulante", "Imobilizado", "Intangível", "Ativo não circulante", "Ativo total",
    # Passivo
    "Fornecedores", "Empréstimos CP", "Obrigações trabalhistas", "Obrigações tributárias",
    "Passivo circulante", "Empréstimos LP", "Passivo não circulante",
    "Patrimônio líquido", "Passivo total",
]


def _ruido(escala=0.02):
    return RNG.normal(0, escala)


def gerar_dre_mensal(mes_i, p, achado):
    """Retorna dict com todas as linhas da DRE (orçado e realizado) de um mês."""
    fator = ((1 + p["crescimento"]) ** mes_i) * p["sazonalidade"][mes_i]
    mes = MESES[mes_i]

    rec_o = p["receita_base"] * fator
    cmv_o = rec_o * p["cmv_pct"]
    com_o = rec_o * p["com_pct"]
    adm_o = p["receita_base"] * p["adm_pct"]

    rec_r = rec_o * (1 + _ruido())
    cmv_r = cmv_o * (1 + _ruido())
    com_r = com_o * (1 + _ruido())
    adm_r = adm_o * (1 + _ruido())

    if mes == achado["mes"]:                      # achado plantado (só no realizado)
        rec_r *= achado.get("receita_mult", 1.0)
        cmv_r *= achado.get("cmv_mult", 1.0)
        com_r *= achado.get("com_mult", 1.0)

    return {
        "mes": mes,
        "rec_o": rec_o, "rec_r": rec_r, "cmv_o": cmv_o, "cmv_r": cmv_r,
        "com_o": com_o, "com_r": com_r, "adm_o": adm_o, "adm_r": adm_r,
        "lb_o": rec_o - cmv_o, "lb_r": rec_r - cmv_r,
        "ebitda_o": (rec_o - cmv_o) - com_o - adm_o,
        "ebitda_r": (rec_r - cmv_r) - com_r - adm_r,
    }


def dre_para_long(m):
    v = {
        "Receita Líquida": (m["rec_o"], m["rec_r"]),
        "CMV": (m["cmv_o"], m["cmv_r"]),
        "Lucro Bruto": (m["lb_o"], m["lb_r"]),
        "Despesas Comerciais": (m["com_o"], m["com_r"]),
        "Despesas Administrativas": (m["adm_o"], m["adm_r"]),
        "EBITDA": (m["ebitda_o"], m["ebitda_r"]),
    }
    return [(m["mes"], c, round(v[c][0], 2), round(v[c][1], 2)) for c in CONTAS_DRE]


def balanco_para_long(m, p):
    """Balanço coerente com a DRE do mês (recebíveis~PMR, estoques~PME, fornec~PMP)."""
    def lado(rec, cmv, com):
        caixa = p["caixa_base"] * (1 + _ruido(0.05))
        receber = rec * p["pmr"] / 30
        estoques = cmv * p["pme"] / 30
        imp_rec = rec * 0.03
        ativo_circ = caixa + receber + estoques + imp_rec
        imob, intang = p["imobilizado"], p["intangivel"]
        ativo_nc = imob + intang
        ativo_total = ativo_circ + ativo_nc

        fornec = cmv * p["pmp"] / 30
        emp_cp, emp_lp = p["emp_cp"], p["emp_lp"]
        obrig_trab = com * 0.30
        obrig_trib = rec * 0.05
        passivo_circ = fornec + emp_cp + obrig_trab + obrig_trib
        passivo_nc = emp_lp
        pl = ativo_total - passivo_circ - passivo_nc   # plug -> ativo = passivo
        return {
            "Caixa e equivalentes": caixa, "Contas a receber": receber,
            "Estoques": estoques, "Impostos a recuperar": imp_rec,
            "Ativo circulante": ativo_circ, "Imobilizado": imob, "Intangível": intang,
            "Ativo não circulante": ativo_nc, "Ativo total": ativo_total,
            "Fornecedores": fornec, "Empréstimos CP": emp_cp,
            "Obrigações trabalhistas": obrig_trab, "Obrigações tributárias": obrig_trib,
            "Passivo circulante": passivo_circ, "Empréstimos LP": emp_lp,
            "Passivo não circulante": passivo_nc, "Patrimônio líquido": pl,
            "Passivo total": passivo_circ + passivo_nc + pl,
        }

    o = lado(m["rec_o"], m["cmv_o"], m["com_o"])
    r = lado(m["rec_r"], m["cmv_r"], m["com_r"])
    return [(m["mes"], c, round(o[c], 2), round(r[c], 2)) for c in CONTAS_BAL]


def gerar_empresa(p):
    dre, bal = [], []
    for i in range(len(MESES)):
        m = gerar_dre_mensal(i, p, p["achado"])
        dre += [(p["nome"], p["setor"], *linha) for linha in dre_para_long(m)]
        bal += [(p["nome"], p["setor"], *linha) for linha in balanco_para_long(m, p)]
    cols = ["empresa", "setor", "competencia", "conta", "orcado", "realizado"]
    return pd.DataFrame(dre, columns=cols), pd.DataFrame(bal, columns=cols)


# ---------------------------------------------------------------------------
# Parâmetros das 3 empresas (cada uma com perfil e "achado" distintos)
# ---------------------------------------------------------------------------
EMPRESAS = [
    dict(nome="Construtora Horizonte", setor="Construção Civil",
         receita_base=3_000_000, cmv_pct=0.70, com_pct=0.05, adm_pct=0.10,
         crescimento=0.008, sazonalidade=[1.0]*12,
         achado={"mes": "2025-07", "cmv_mult": 1.18},
         pmr=85, pme=110, pmp=55,               # obra: recebe e estoca devagar
         imobilizado=8_000_000, intangivel=500_000,
         emp_cp=3_000_000, emp_lp=6_000_000, caixa_base=1_500_000),
    dict(nome="FluxoData", setor="SaaS / Tech",
         receita_base=900_000, cmv_pct=0.20, com_pct=0.18, adm_pct=0.12,
         crescimento=0.02, sazonalidade=[1.0]*12,
         achado={"mes": "2025-09", "receita_mult": 0.88, "com_mult": 1.20},
         pmr=32, pme=2, pmp=28,                 # SaaS: quase sem estoque, giro rápido
         imobilizado=1_200_000, intangivel=2_500_000,
         emp_cp=300_000, emp_lp=800_000, caixa_base=2_500_000),
    dict(nome="Rede BomPreço", setor="Varejo",
         receita_base=6_000_000, cmv_pct=0.65, com_pct=0.08, adm_pct=0.07,
         crescimento=0.005,
         sazonalidade=[0.9, 0.85, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.35, 1.5],
         achado={"mes": "2025-11", "receita_mult": 1.08, "cmv_mult": 1.15},
         pmr=22, pme=48, pmp=42,                # varejo: recebe rápido, estoca médio
         imobilizado=5_000_000, intangivel=300_000,
         emp_cp=2_500_000, emp_lp=4_000_000, caixa_base=1_800_000),
]

# Premissas financeiras (usadas pelo motor de indicadores)
PREMISSAS = {"aliquota_ir": 0.34, "juros_mensal": 0.014, "wacc_mensal": 0.010,
             "deprec_pct_receita": 0.02}


def gerar_saas():
    """Dados operacionais de SaaS (só FluxoData): clientes, churn, MRR, marketing.
    Achado: churn dispara em set/2025 (menos novos, mais gasto de retenção)."""
    clientes = 1200; arpa = 720.0           # ticket médio R$/cliente/mês
    linhas = []
    for i, mes in enumerate(MESES):
        crise = (mes == "2025-09")
        churn_rate = 0.025 + (0.045 if crise else 0.0) + RNG.normal(0, 0.003)
        novos = int(90 * (1.02 ** i) * (0.55 if crise else 1.0) + RNG.normal(0, 5))
        churned = int(clientes * churn_rate)
        cli_ini = clientes; cli_fim = cli_ini + novos - churned
        arpa_m = arpa * (1.005 ** i)
        mrr = cli_fim * arpa_m
        marketing = 180_000 * (1.01 ** i) + (130_000 if crise else 0) + RNG.normal(0, 6_000)
        expansion_mrr = mrr * 0.02           # upsell/expansão
        churn_mrr = cli_ini * churn_rate * arpa_m
        linhas.append({
            "competencia": mes, "clientes_inicio": cli_ini, "novos_clientes": novos,
            "clientes_perdidos": churned, "clientes_fim": cli_fim,
            "churn_rate": round(churn_rate, 4), "arpa": round(arpa_m, 2),
            "mrr": round(mrr, 2), "marketing": round(marketing, 2),
            "expansion_mrr": round(expansion_mrr, 2), "churn_mrr": round(churn_mrr, 2),
        })
        clientes = cli_fim
    return pd.DataFrame(linhas)


def _slug(nome):
    return (nome.lower().replace(" ", "-")
            .replace("ç", "c").replace("é", "e").replace("ã", "a"))


def main():
    saida = Path(__file__).parent
    for p in EMPRESAS:
        dre, bal = gerar_empresa(p)
        dre.to_csv(saida / f"dre-{_slug(p['nome'])}.csv", index=False, encoding="utf-8")
        bal.to_csv(saida / f"balanco-{_slug(p['nome'])}.csv", index=False, encoding="utf-8")
        print(f"Gerado: {_slug(p['nome'])}  (DRE {len(dre)} + Balanço {len(bal)} linhas)")
    # Camada SaaS (só FluxoData) — gerada após as empresas para não alterar o RNG delas
    gerar_saas().to_csv(saida / "saas-fluxodata.csv", index=False, encoding="utf-8")
    print("Gerado: saas-fluxodata.csv (métricas SaaS)")
    print("\nAchados plantados: Construtora=jul (aço) | FluxoData=set (churn) | BomPreço=nov (margem)")


if __name__ == "__main__":
    main()
