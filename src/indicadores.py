"""
indicadores.py — Os ~30 indicadores econômico-financeiros do Oráculo.

Calcula tudo a partir da DRE + Balanço (números do CÓDIGO, nunca da IA).
Baseado nos modelos clássicos (Fleuriet, Kanitz, Altman Z') e nas premissas
parametrizáveis (alíquota de IR, juros, WACC, depreciação).

Cada função devolve um dicionário {indicador: valor}. Fluxos (DRE) são somados
no ano (proxy de LTM); estoques (Balanço) usam a competência de referência.
"""

from __future__ import annotations
import pandas as pd

# Premissas padrão (parametrizáveis via .env no copiloto). Coerentes com o gerador.
PREMISSAS_PADRAO = {"aliquota_ir": 0.34, "juros_mensal": 0.014,
                    "wacc_mensal": 0.010, "deprec_pct_receita": 0.02,
                    "capex_mult": 1.2, "payout": 0.30}


# ------------------------------ acessores ---------------------------------
def _v(df, conta, comp, col="realizado"):
    r = df[(df["conta"] == conta) & (df["competencia"] == comp)]
    return float(r[col].iloc[0]) if not r.empty else 0.0

def _ano(df, conta, col="realizado"):
    return float(df[df["conta"] == conta][col].sum())


# --------------------------- 1) RENTABILIDADE ------------------------------
def rentabilidade(dre, bal, pr, comp):
    rec = _ano(dre, "Receita Líquida");  lb = _ano(dre, "Lucro Bruto")
    ebitda = _ano(dre, "EBITDA")
    dep = rec * pr["deprec_pct_receita"]
    ebit = ebitda - dep
    div_bruta = _v(bal, "Empréstimos CP", comp) + _v(bal, "Empréstimos LP", comp)
    juros = div_bruta * pr["juros_mensal"] * 12
    lair = ebit - juros
    ir = max(lair, 0) * pr["aliquota_ir"]
    rl = lair - ir
    nopat = ebit * (1 - pr["aliquota_ir"])
    pl = _v(bal, "Patrimônio líquido", comp)
    caixa = _v(bal, "Caixa e equivalentes", comp)
    ativo = _v(bal, "Ativo total", comp)
    cap_inv = pl + (div_bruta - caixa)                 # PL + dívida líquida
    wacc_a = (1 + pr["wacc_mensal"]) ** 12 - 1
    return {
        "margem_bruta": lb / rec, "margem_ebitda": ebitda / rec, "margem_liquida": rl / rec,
        "ebitda": ebitda, "ebit": ebit, "resultado_liquido": rl, "nopat": nopat,
        "roe": rl / pl, "roa": rl / ativo, "roic": nopat / cap_inv, "roi": nopat / ativo,
        "giro_ativo": rec / ativo, "wacc": wacc_a, "capital_investido": cap_inv,
        "eva": nopat - wacc_a * cap_inv,
    }


# ------------------------ 2) MARGEM DE CONTRIBUIÇÃO / PE --------------------
def contribuicao_e_pe(dre, comp=None):
    """Margem de contribuição e ponto de equilíbrio contábil (ano)."""
    rec = _ano(dre, "Receita Líquida"); cmv = _ano(dre, "CMV")
    com = _ano(dre, "Despesas Comerciais"); adm = _ano(dre, "Despesas Administrativas")
    # Split simples: 60% das comerciais são variáveis (frete/comissão); adm é fixo
    var = cmv + 0.60 * com
    fixo = adm + 0.40 * com
    mc = rec - var                     # margem de contribuição (R$)
    mc_pct = mc / rec
    pe = fixo / mc_pct if mc_pct else 0.0   # ponto de equilíbrio contábil (R$)
    margem_seg = (rec - pe) / rec if rec else 0.0
    return {"margem_contribuicao": mc, "margem_contribuicao_pct": mc_pct,
            "ponto_equilibrio": pe, "margem_seguranca": margem_seg,
            "custos_fixos": fixo, "custos_variaveis": var}


# ----------------------------- 3) LIQUIDEZ ---------------------------------
def liquidez(bal, comp):
    ac = _v(bal, "Ativo circulante", comp); pc = _v(bal, "Passivo circulante", comp)
    pnc = _v(bal, "Passivo não circulante", comp)
    est = _v(bal, "Estoques", comp); caixa = _v(bal, "Caixa e equivalentes", comp)
    return {
        "liquidez_corrente": ac / pc,
        "liquidez_seca": (ac - est) / pc,
        "liquidez_imediata": caixa / pc,
        "liquidez_geral": ac / (pc + pnc),
    }


# ------------------------- 4) ENDIVIDAMENTO / ALAVANCAGEM -------------------
def endividamento(dre, bal, pr, comp):
    div_cp = _v(bal, "Empréstimos CP", comp); div_lp = _v(bal, "Empréstimos LP", comp)
    div_bruta = div_cp + div_lp
    caixa = _v(bal, "Caixa e equivalentes", comp); pl = _v(bal, "Patrimônio líquido", comp)
    div_liq = div_bruta - caixa
    ebitda = _ano(dre, "EBITDA")
    ebit = ebitda - _ano(dre, "Receita Líquida") * pr["deprec_pct_receita"]
    juros = div_bruta * pr["juros_mensal"] * 12
    return {
        "divida_bruta": div_bruta, "divida_liquida": div_liq,
        "div_liq_ebitda": div_liq / ebitda if ebitda else None,
        "divida_pl": div_bruta / pl if pl else None,
        "composicao_endiv": div_cp / div_bruta if div_bruta else None,   # % no curto prazo
        "cobertura_juros": ebit / juros if juros else None,
    }


# ------------------- 5) CAPITAL DE GIRO (FLEURIET) + CICLOS -----------------
def capital_giro(dre, bal, comp):
    cr = _v(bal, "Contas a receber", comp); est = _v(bal, "Estoques", comp)
    imp = _v(bal, "Impostos a recuperar", comp); forn = _v(bal, "Fornecedores", comp)
    trab = _v(bal, "Obrigações trabalhistas", comp); trib = _v(bal, "Obrigações tributárias", comp)
    ac_op = cr + est + imp                    # ativo circulante operacional
    pc_op = forn + trab + trib                # passivo circulante operacional
    ncg = ac_op - pc_op                        # Necessidade de Capital de Giro
    cdg = (_v(bal, "Patrimônio líquido", comp) + _v(bal, "Passivo não circulante", comp)
           - _v(bal, "Ativo não circulante", comp))     # Capital de Giro
    tesouraria = cdg - ncg                     # Saldo de Tesouraria (Fleuriet)
    # ciclos (usa fluxos do mês de referência)
    rec_m = _v(dre, "Receita Líquida", comp); cmv_m = _v(dre, "CMV", comp)
    pmr = cr / rec_m * 30 if rec_m else 0
    pme = est / cmv_m * 30 if cmv_m else 0
    pmp = forn / cmv_m * 30 if cmv_m else 0
    return {"ncg": ncg, "cdg": cdg, "tesouraria": tesouraria,
            "pmr": pmr, "pme": pme, "pmp": pmp,
            "ciclo_operacional": pmr + pme, "ciclo_financeiro": pmr + pme - pmp}


# ---------------------------- 6) SOLVÊNCIA ---------------------------------
def solvencia(dre, bal, pr, comp):
    ac = _v(bal, "Ativo circulante", comp); pc = _v(bal, "Passivo circulante", comp)
    pnc = _v(bal, "Passivo não circulante", comp); est = _v(bal, "Estoques", comp)
    pl = _v(bal, "Patrimônio líquido", comp); ativo = _v(bal, "Ativo total", comp)
    exig = pc + pnc
    ebitda = _ano(dre, "EBITDA"); ebit = ebitda - _ano(dre, "Receita Líquida") * pr["deprec_pct_receita"]
    rec = _ano(dre, "Receita Líquida")
    div_bruta = _v(bal, "Empréstimos CP", comp) + _v(bal, "Empréstimos LP", comp)
    juros = div_bruta * pr["juros_mensal"] * 12
    rl = (ebit - juros); rl = rl - max(rl, 0) * pr["aliquota_ir"]
    # Kanitz
    I1 = rl / pl; I2 = ac / exig; I3 = (ac - est) / pc; I4 = ac / pc; I5 = exig / pl
    kanitz = 0.05*I1 + 1.65*I2 + 3.55*I3 - 1.06*I4 - 0.33*I5
    # Altman Z' (empresas fechadas)
    wc = ac - pc
    X1 = wc / ativo; X2 = rl / ativo; X3 = ebit / ativo; X4 = pl / exig; X5 = rec / ativo
    altman = 0.717*X1 + 0.847*X2 + 3.107*X3 + 0.420*X4 + 0.998*X5
    return {"kanitz": kanitz, "kanitz_status": "Solvente" if kanitz > 0 else "Risco",
            "altman_z": altman,
            "altman_status": "Saudável" if altman > 2.9 else ("Cinza" if altman > 1.23 else "Perigo")}


# --------------------- 7) ANÁLISE VERTICAL / HORIZONTAL --------------------
def analise_vertical(dre, comp):
    rec = _v(dre, "Receita Líquida", comp)
    out = {}
    for c in ["Receita Líquida", "CMV", "Lucro Bruto", "Despesas Comerciais",
              "Despesas Administrativas", "EBITDA"]:
        out[c] = _v(dre, c, comp) / rec if rec else 0.0
    return out

def analise_horizontal(dre, conta):
    s = (dre[dre["conta"] == conta].sort_values("competencia"))
    vals = s["realizado"].tolist(); meses = s["competencia"].tolist()
    out = []
    for i in range(1, len(vals)):
        var = (vals[i] - vals[i-1]) / vals[i-1] if vals[i-1] else 0.0
        out.append({"competencia": meses[i], "valor": vals[i], "var_mensal": var})
    return out


# ------------------- 8) FLUXO DE CAIXA (DFC — método indireto) --------------
def fluxo_caixa(dre, bal, pr=None):
    """DFC indireta (ano): parte do lucro líquido, soma D&A, ajusta capital de giro.
    FCO (operacional) -> FCFF (livre, após CAPEX) -> Δ Caixa (após financiamento)."""
    pr = pr or PREMISSAS_PADRAO
    meses = sorted(dre["competencia"].unique()); ini, fim = meses[0], meses[-1]
    rec = _ano(dre, "Receita Líquida")
    da = rec * pr["deprec_pct_receita"]
    ebit = _ano(dre, "EBITDA") - da
    div_bruta = _v(bal, "Empréstimos CP", fim) + _v(bal, "Empréstimos LP", fim)
    juros = div_bruta * pr["juros_mensal"] * 12
    lair = ebit - juros; ni = lair - max(lair, 0) * pr["aliquota_ir"]

    def d(conta):                       # variação Jan -> Dez de uma conta
        return _v(bal, conta, fim) - _v(bal, conta, ini)
    d_ncg = ((d("Contas a receber") + d("Estoques") + d("Impostos a recuperar"))
             - (d("Fornecedores") + d("Obrigações trabalhistas") + d("Obrigações tributárias")))
    fco = ni + da - d_ncg               # NCG cresceu => consumiu caixa
    capex = da * pr["capex_mult"]
    fcff = fco - capex                  # fluxo de caixa livre para a firma
    dividendos = max(ni, 0) * pr["payout"]
    delta_caixa = fcff - dividendos
    return {"lucro_liquido": ni, "depreciacao": da, "var_capital_giro": -d_ncg,
            "fco": fco, "capex": -capex, "fcff": fcff, "dividendos": -dividendos,
            "delta_caixa": delta_caixa}


# ------------------------------ RESUMO ------------------------------------
def resumo(dre, bal, pr=None, comp="2025-12"):
    """Junta todos os grupos num só dicionário para o dashboard."""
    pr = pr or PREMISSAS_PADRAO
    return {
        "rentabilidade": rentabilidade(dre, bal, pr, comp),
        "contribuicao": contribuicao_e_pe(dre, comp),
        "liquidez": liquidez(bal, comp),
        "endividamento": endividamento(dre, bal, pr, comp),
        "capital_giro": capital_giro(dre, bal, comp),
        "solvencia": solvencia(dre, bal, pr, comp),
        "vertical": analise_vertical(dre, comp),
        "fluxo_caixa": fluxo_caixa(dre, bal, pr),
    }
