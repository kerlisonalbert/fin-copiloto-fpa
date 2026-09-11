"""
Golden file dos indicadores — a rede de segurança contra o erro que NÃO quebra.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Os outros testes checam **invariantes** (o balanço fecha, a DFC soma, os ciclos
são positivos). Invariante é ótimo, mas não pega denominador trocado: um ROIC
calculado sobre o ativo total em vez do capital investido passa em todos eles —
e mente em silêncio, porque o número continua plausível.

Este arquivo trava o **valor** de cada indicador contra uma empresa-teste cujos
números foram escolhidos redondos de propósito.

A REGRA DE OURO DESTE ARQUIVO
-----------------------------
Os valores esperados abaixo foram calculados **à mão, a partir da definição de
cada indicador** — NÃO copiados da saída do código. Um golden file gerado
rodando o próprio código não testa nada: ele congela o bug junto com o acerto.
Cada bloco traz a derivação em comentário, para qualquer pessoa auditar sem
executar nada.

Se um destes testes falhar, a pergunta certa é "a fórmula mudou de propósito?".
Se sim, refaça a conta à mão e atualize o número aqui — nunca cole a saída nova.

A EMPRESA-TESTE  (tests/dados_golden/)
--------------------------------------
Dois meses idênticos (2026-01 e 2026-02), competência de referência 2026-02.
DRE de cada mês:  Receita 1.000.000 · CMV 600.000 · Lucro Bruto 400.000 ·
Comerciais 100.000 · Administrativas 150.000 · EBITDA 150.000
=> Totais do período (2 meses): Receita 2.000.000 · CMV 1.200.000 ·
   Lucro Bruto 800.000 · Comerciais 200.000 · Administrativas 300.000 ·
   EBITDA 300.000

Balanço em 2026-02: Caixa 200.000 · Receber 500.000 · Estoques 300.000 ·
Impostos a recuperar 100.000 · AC 1.100.000 · ANC 900.000 · Ativo 2.000.000 ·
Fornecedores 250.000 · Trabalhistas 80.000 · Tributárias 70.000 ·
Empréstimos CP 100.000 · PC 500.000 · Empréstimos LP 400.000 · PNC 400.000 ·
PL 1.100.000 · Passivo 2.000.000

Premissas padrão: IR 34% · juros 1,4% a.m. · WACC 1,0% a.m. ·
depreciação 2% da receita · capex 1,2× D&A · payout 30%
"""
import pathlib
import pytest
import pandas as pd

import analise_fpa as motor
import indicadores as ind

GOLDEN = pathlib.Path(__file__).parent / "dados_golden"
COMP = "2026-02"
PR = ind.PREMISSAS_PADRAO

# Tolerância relativa: a aritmética é exata, então só absorve ruído de float.
REL = 1e-9


@pytest.fixture(scope="module")
def golden():
    dre = motor.carregar_dre(str(GOLDEN / "dre-golden.csv"))
    bal = motor.carregar_dre(str(GOLDEN / "balanco-golden.csv"))
    return dre, bal


# ---------------------------------------------------------------- premissas
def test_premissas_nao_mudaram():
    """As premissas são a base de TODA derivação abaixo. Se mudarem, os números
    esperados deste arquivo deixam de valer — e o teste tem que avisar."""
    assert PR["aliquota_ir"] == 0.34
    assert PR["juros_mensal"] == 0.014
    assert PR["wacc_mensal"] == 0.010
    assert PR["deprec_pct_receita"] == 0.02
    assert PR["capex_mult"] == 1.2
    assert PR["payout"] == 0.30


# ------------------------------------------------------------ rentabilidade
def test_rentabilidade(golden):
    """Derivação:
    D&A       = 2.000.000 × 2%              =    40.000
    EBIT      = 300.000 − 40.000            =   260.000
    Dív.bruta = 100.000 + 400.000           =   500.000
    Juros     = 500.000 × 1,4% × 12         =    84.000
    LAIR      = 260.000 − 84.000            =   176.000
    IR        = 176.000 × 34%               =    59.840
    Lucro líq = 176.000 − 59.840            =   116.160
    NOPAT     = 260.000 × (1 − 34%)         =   171.600
    Cap.inv.  = PL 1.100.000 + (500.000 − 200.000 de caixa) = 1.400.000
    WACC anual= 1,01^12 − 1                 = 0,126825030131969…
    EVA       = 171.600 − 0,12682503… × 1.400.000 = −5.955,0421847…
    """
    dre, bal = golden
    r = ind.rentabilidade(dre, bal, PR, COMP)

    assert r["ebit"] == pytest.approx(260_000, rel=REL)
    assert r["resultado_liquido"] == pytest.approx(116_160, rel=REL)
    assert r["nopat"] == pytest.approx(171_600, rel=REL)
    assert r["capital_investido"] == pytest.approx(1_400_000, rel=REL)

    assert r["margem_bruta"] == pytest.approx(0.40, rel=REL)        # 800k / 2.000k
    assert r["margem_ebitda"] == pytest.approx(0.15, rel=REL)       # 300k / 2.000k
    assert r["margem_liquida"] == pytest.approx(0.05808, rel=REL)   # 116.160 / 2.000k

    assert r["roe"] == pytest.approx(0.10560, rel=REL)              # 116.160 / 1.100k
    assert r["roa"] == pytest.approx(0.05808, rel=REL)              # 116.160 / 2.000k
    assert r["roic"] == pytest.approx(171_600 / 1_400_000, rel=REL)
    assert r["roi"] == pytest.approx(0.0858, rel=REL)               # 171.600 / 2.000k
    assert r["giro_ativo"] == pytest.approx(1.0, rel=REL)           # 2.000k / 2.000k
    assert r["wacc"] == pytest.approx(0.1268250301319697, rel=1e-12)
    assert r["eva"] == pytest.approx(-5_955.042184757582, rel=1e-9)


def test_eva_negativo_quando_roic_abaixo_do_wacc(golden):
    """Sanidade econômica, não só aritmética: ROIC 12,26% < WACC 12,68%,
    logo a empresa DESTRÓI valor no período e o EVA tem que ser negativo."""
    dre, bal = golden
    r = ind.rentabilidade(dre, bal, PR, COMP)
    assert r["roic"] < r["wacc"]
    assert r["eva"] < 0


# ------------------------------------------ margem de contribuição / ponto de equilíbrio
def test_contribuicao_e_ponto_de_equilibrio(golden):
    """O modelo trata 60% das despesas comerciais como variáveis e 40% como fixas.
    Variáveis = CMV 1.200.000 + 60% × 200.000        = 1.320.000
    Fixos     = Administrativas 300.000 + 40% × 200.000 =   380.000
    MC        = 2.000.000 − 1.320.000                =   680.000  (34,0%)
    PE contábil = 380.000 / 0,34                     = 1.117.647,0588…
    Margem de segurança = (2.000.000 − PE) / 2.000.000 = 0,441176470588…
    """
    dre, _ = golden
    c = ind.contribuicao_e_pe(dre, COMP)
    assert c["custos_variaveis"] == pytest.approx(1_320_000, rel=REL)
    assert c["custos_fixos"] == pytest.approx(380_000, rel=REL)
    assert c["margem_contribuicao"] == pytest.approx(680_000, rel=REL)
    assert c["margem_contribuicao_pct"] == pytest.approx(0.34, rel=REL)
    assert c["ponto_equilibrio"] == pytest.approx(380_000 / 0.34, rel=REL)
    assert c["margem_seguranca"] == pytest.approx(1 - (380_000 / 0.34) / 2_000_000, rel=REL)


# ----------------------------------------------------------------- liquidez
def test_liquidez(golden):
    """Corrente = AC / PC             = 1.100.000 / 500.000 = 2,20
    Seca       = (AC − Estoques) / PC =   800.000 / 500.000 = 1,60
    Imediata   = Caixa / PC           =   200.000 / 500.000 = 0,40
    Geral      = AC / (PC + PNC)      = 1.100.000 / 900.000 = 1,2222…

    ⚠️ LIMITAÇÃO CONHECIDA: a liquidez geral clássica é
    (AC + Realizável a Longo Prazo) / (PC + PNC). Este modelo usa só o AC no
    numerador porque o plano de contas do projeto não tem RLP. Para uma empresa
    COM realizável a longo prazo, este número sairia subestimado. Está declarado
    na seção de limitações do README — e este teste existe para que a
    simplificação seja uma escolha visível, não um esquecimento silencioso.
    """
    _, bal = golden
    lq = ind.liquidez(bal, COMP)
    assert lq["liquidez_corrente"] == pytest.approx(2.20, rel=REL)
    assert lq["liquidez_seca"] == pytest.approx(1.60, rel=REL)
    assert lq["liquidez_imediata"] == pytest.approx(0.40, rel=REL)
    assert lq["liquidez_geral"] == pytest.approx(1_100_000 / 900_000, rel=REL)


# ------------------------------------------------------------ endividamento
def test_endividamento(golden):
    """Dív. bruta   = 100.000 + 400.000        = 500.000
    Dív. líquida    = 500.000 − caixa 200.000  = 300.000
    Dív.Líq/EBITDA  = 300.000 / 300.000        = 1,00×
    Dívida/PL       = 500.000 / 1.100.000      = 0,4545…
    % no curto prazo= 100.000 / 500.000        = 20%
    Cobertura juros = EBIT 260.000 / juros 84.000 = 3,0952…
    """
    dre, bal = golden
    e = ind.endividamento(dre, bal, PR, COMP)
    assert e["divida_bruta"] == pytest.approx(500_000, rel=REL)
    assert e["divida_liquida"] == pytest.approx(300_000, rel=REL)
    assert e["div_liq_ebitda"] == pytest.approx(1.0, rel=REL)
    assert e["divida_pl"] == pytest.approx(500_000 / 1_100_000, rel=REL)
    assert e["composicao_endiv"] == pytest.approx(0.20, rel=REL)
    assert e["cobertura_juros"] == pytest.approx(260_000 / 84_000, rel=REL)


# ------------------------------------------- capital de giro (Fleuriet) e ciclos
def test_capital_giro_fleuriet(golden):
    """AC operacional = Receber 500.000 + Estoques 300.000 + Impostos 100.000 = 900.000
    PC operacional   = Fornec. 250.000 + Trab. 80.000 + Trib. 70.000          = 400.000
    NCG              = 900.000 − 400.000                                      = 500.000
    CDG              = PL 1.100.000 + PNC 400.000 − ANC 900.000               = 600.000
    Tesouraria       = CDG − NCG = 600.000 − 500.000                          = 100.000  (positiva)

    Ciclos (sobre os fluxos do mês de referência: receita 1.000.000, CMV 600.000):
    PMR = 500.000 / 1.000.000 × 30 = 15 dias
    PME = 300.000 /   600.000 × 30 = 15 dias
    PMP = 250.000 /   600.000 × 30 = 12,5 dias
    Ciclo operacional = 15 + 15        = 30 dias
    Ciclo financeiro  = 15 + 15 − 12,5 = 17,5 dias
    """
    dre, bal = golden
    cg = ind.capital_giro(dre, bal, COMP)
    assert cg["ncg"] == pytest.approx(500_000, rel=REL)
    assert cg["cdg"] == pytest.approx(600_000, rel=REL)
    assert cg["tesouraria"] == pytest.approx(100_000, rel=REL)
    assert cg["pmr"] == pytest.approx(15.0, rel=REL)
    assert cg["pme"] == pytest.approx(15.0, rel=REL)
    assert cg["pmp"] == pytest.approx(12.5, rel=REL)
    assert cg["ciclo_operacional"] == pytest.approx(30.0, rel=REL)
    assert cg["ciclo_financeiro"] == pytest.approx(17.5, rel=REL)


def test_identidade_fleuriet(golden):
    """A identidade que define o modelo: T = CDG − NCG. Se algum dia alguém
    mexer numa das três, esta linha denuncia."""
    dre, bal = golden
    cg = ind.capital_giro(dre, bal, COMP)
    assert cg["tesouraria"] == pytest.approx(cg["cdg"] - cg["ncg"], rel=REL)


# ---------------------------------------------------------------- solvência
def test_kanitz(golden):
    """Fator de insolvência de Kanitz = 0,05·I1 + 1,65·I2 + 3,55·I3 − 1,06·I4 − 0,33·I5
    I1 = Lucro líq / PL          = 116.160 / 1.100.000   = 0,10560
    I2 = AC / Exigível total     = 1.100.000 / 900.000   = 1,22222…
    I3 = (AC − Estoques) / PC    =   800.000 / 500.000   = 1,60
    I4 = AC / PC                 = 1.100.000 / 500.000   = 2,20
    I5 = Exigível total / PL     =   900.000 / 1.100.000 = 0,81818…

    0,05×0,10560  =  0,005280
    1,65×1,22222… =  2,016666…
    3,55×1,60     =  5,680000
    −1,06×2,20    = −2,332000
    −0,33×0,81818…= −0,270000
    Soma          =  5,099946666…   → faixa de solvência (> 0)
    """
    dre, bal = golden
    s = ind.solvencia(dre, bal, PR, COMP)
    assert s["kanitz"] == pytest.approx(5.099946666666667, rel=1e-9)
    assert s["kanitz_status"] == "Solvente"


def test_altman_z_linha(golden):
    """Altman Z' (variante de empresa fechada):
    Z' = 0,717·X1 + 0,847·X2 + 3,107·X3 + 0,420·X4 + 0,998·X5
    X1 = Capital circulante líq / Ativo = 600.000 / 2.000.000   = 0,30000
    X2 = Lucro líquido / Ativo          = 116.160 / 2.000.000   = 0,05808
    X3 = EBIT / Ativo                   = 260.000 / 2.000.000   = 0,13000
    X4 = PL / Exigível total            = 1.100.000 / 900.000   = 1,22222…
    X5 = Receita / Ativo                = 2.000.000 / 2.000.000 = 1,00000

    0,717×0,30000 = 0,215100
    0,847×0,05808 = 0,049194  (0,04919376)
    3,107×0,13000 = 0,403910
    0,420×1,22222…= 0,513333…
    0,998×1,00000 = 0,998000
    Z'            = 2,179537093…  → faixa CINZA (entre 1,23 e 2,90)

    Os coeficientes são os da variante Z' para empresa de capital FECHADO.
    Trocá-los pelos do Z original (companhia aberta) é um erro clássico —
    este teste existe para pegá-lo.
    """
    dre, bal = golden
    s = ind.solvencia(dre, bal, PR, COMP)
    assert s["altman_z"] == pytest.approx(2.1795370933333333, rel=1e-9)
    assert s["altman_status"] == "Cinza"


# --------------------------------------------------------- análise vertical
def test_analise_vertical(golden):
    """Cada conta do mês como % da receita líquida do mês (1.000.000)."""
    dre, _ = golden
    av = ind.analise_vertical(dre, COMP)
    assert av["Receita Líquida"] == pytest.approx(1.00, rel=REL)
    assert av["CMV"] == pytest.approx(0.60, rel=REL)
    assert av["Lucro Bruto"] == pytest.approx(0.40, rel=REL)
    assert av["Despesas Comerciais"] == pytest.approx(0.10, rel=REL)
    assert av["Despesas Administrativas"] == pytest.approx(0.15, rel=REL)
    assert av["EBITDA"] == pytest.approx(0.15, rel=REL)


# -------------------------------------------------- fluxo de caixa (DFC indireta)
def test_fluxo_de_caixa(golden):
    """Δ das contas operacionais de jan → fev:
    Receber   +50.000 · Estoques +20.000 · Impostos a recuperar +10.000  = +80.000
    Fornec.   +10.000 · Trabalhistas +5.000 · Tributárias +5.000         = +20.000
    Δ NCG = 80.000 − 20.000 = 60.000  (a NCG cresceu ⇒ CONSUMIU caixa)

    Lucro líquido       =  116.160
    + D&A               =   40.000
    − Δ NCG             =  −60.000
    = FCO               =   96.160
    − CAPEX (1,2 × D&A) =  −48.000
    = FCFF              =   48.160
    − Dividendos (30%)  =  −34.848
    = Δ Caixa           =   13.312
    """
    dre, bal = golden
    f = ind.fluxo_caixa(dre, bal, PR)
    assert f["lucro_liquido"] == pytest.approx(116_160, rel=REL)
    assert f["depreciacao"] == pytest.approx(40_000, rel=REL)
    assert f["var_capital_giro"] == pytest.approx(-60_000, rel=REL)
    assert f["fco"] == pytest.approx(96_160, rel=REL)
    assert f["capex"] == pytest.approx(-48_000, rel=REL)
    assert f["fcff"] == pytest.approx(48_160, rel=REL)
    assert f["dividendos"] == pytest.approx(-34_848, rel=REL)
    assert f["delta_caixa"] == pytest.approx(13_312, rel=REL)


def test_cascata_da_dfc_fecha(golden):
    """A cascata tem que somar: cada degrau é o anterior mais o ajuste."""
    dre, bal = golden
    f = ind.fluxo_caixa(dre, bal, PR)
    assert f["fco"] == pytest.approx(
        f["lucro_liquido"] + f["depreciacao"] + f["var_capital_giro"], rel=REL)
    assert f["fcff"] == pytest.approx(f["fco"] + f["capex"], rel=REL)
    assert f["delta_caixa"] == pytest.approx(f["fcff"] + f["dividendos"], rel=REL)


# ------------------------------------------------------------------ resumo
def test_resumo_traz_todos_os_grupos(golden):
    """O dashboard consome o resumo. Se um grupo sumir, o painel quebra em
    silêncio — melhor falhar aqui."""
    dre, bal = golden
    r = ind.resumo(dre, bal, PR, comp=COMP)
    esperados = {"rentabilidade", "contribuicao", "liquidez", "endividamento",
                 "capital_giro", "solvencia", "vertical", "fluxo_caixa"}
    assert esperados.issubset(r.keys())
    # e os valores do resumo têm que bater com as chamadas diretas
    assert r["rentabilidade"]["eva"] == pytest.approx(
        ind.rentabilidade(dre, bal, PR, COMP)["eva"], rel=REL)
