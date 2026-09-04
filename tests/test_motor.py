"""Testes do motor de análise (analise_fpa)."""
import pandas as pd
import pytest
import analise_fpa as motor


def test_formato_invalido(tmp_path):
    """Planilha sem as colunas obrigatórias deve dar erro claro."""
    p = tmp_path / "x.csv"
    pd.DataFrame({"qualquer": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        motor.carregar_dre(str(p))


def test_identidades_dre(dados):
    """Lucro Bruto = Receita − CMV; EBITDA = LB − Comercial − Administrativa."""
    dre, _ = dados["construtora-horizonte"]
    p = dre.pivot_table(index="competencia", columns="conta", values="realizado")
    assert (abs((p["Receita Líquida"] - p["CMV"]) - p["Lucro Bruto"]) < 1).all()
    assert (abs((p["Lucro Bruto"] - p["Despesas Comerciais"]
                 - p["Despesas Administrativas"]) - p["EBITDA"]) < 1).all()


def test_variacao_percentual(dados):
    """variacao_pct = (realizado − orçado) / orçado."""
    dre, _ = dados["fluxodata"]
    v = motor.variacoes(dre, 0.05).iloc[0]
    esperado = (v["realizado"] - v["orcado"]) / v["orcado"]
    assert abs(v["variacao_pct"] - esperado) < 1e-9


def test_achado_do_aco(dados):
    """O maior desvio desfavorável da Construtora é o estouro de CMV em julho."""
    dre, _ = dados["construtora-horizonte"]
    ach = motor.achados(dre, 0.05, top=1)
    assert ach.iloc[0]["competencia"] == "2025-07"
