"""Testes das métricas SaaS."""
import saas


def test_identidades_saas(saas_df):
    m = saas.metricas(saas_df)
    # LTV/CAC = LTV / CAC ; ARR = MRR × 12
    assert abs(m["ltv_cac"] - m["ltv"] / m["cac"]) < 1e-6
    assert abs(m["arr"] - m["mrr"] * 12) < 1
    # churn e NRR em faixas plausíveis
    assert 0 < m["churn_mensal"] < 0.2
    assert 0.5 < m["nrr_anual"] < 1.5


def test_pico_de_churn(saas_df):
    """O pico de churn plantado é em setembro/2025."""
    assert saas.metricas(saas_df)["churn_pico"] == "2025-09"
