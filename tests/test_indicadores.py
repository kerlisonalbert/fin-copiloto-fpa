"""Testes dos indicadores econômico-financeiros."""
import indicadores as ind


def test_balanco_sempre_fecha(dados):
    """Invariante contábil: Ativo total = Passivo total, em todo mês."""
    for dre, bal in dados.values():
        p = bal.pivot_table(index="competencia", columns="conta", values="realizado")
        assert (abs(p["Ativo total"] - p["Passivo total"]) < 1).all()


def test_liquidez_corrente(dados):
    """Liquidez corrente = Ativo circulante / Passivo circulante."""
    _, bal = dados["rede-bompreco"]
    lq = ind.liquidez(bal, "2025-12")
    p = bal[bal["competencia"] == "2025-12"].set_index("conta")["realizado"]
    assert abs(lq["liquidez_corrente"] - p["Ativo circulante"] / p["Passivo circulante"]) < 1e-6


def test_dfc_identidades(dados):
    """A cascata da DFC tem que somar: FCO -> FCFF -> Δ Caixa."""
    dre, bal = dados["construtora-horizonte"]
    f = ind.fluxo_caixa(dre, bal)
    assert abs(f["fco"] - (f["lucro_liquido"] + f["depreciacao"] + f["var_capital_giro"])) < 1
    assert abs(f["fcff"] - (f["fco"] + f["capex"])) < 1
    assert abs(f["delta_caixa"] - (f["fcff"] + f["dividendos"])) < 1


def test_ciclos_positivos(dados):
    """Prazos médios (PMR/PME/PMP) devem ser positivos e coerentes."""
    dre, bal = dados["construtora-horizonte"]
    cg = ind.capital_giro(dre, bal, "2025-12")
    assert cg["pmr"] > 0 and cg["pme"] > 0 and cg["pmp"] > 0
    assert cg["ciclo_financeiro"] == cg["pmr"] + cg["pme"] - cg["pmp"]


def test_solvencia_faixas(dados):
    """Os modelos de solvência devem devolver um status conhecido."""
    dre, bal = dados["fluxodata"]
    sv = ind.solvencia(dre, bal, ind.PREMISSAS_PADRAO, "2025-12")
    assert sv["kanitz_status"] in ("Solvente", "Risco")
    assert sv["altman_status"] in ("Saudável", "Cinza", "Perigo")
