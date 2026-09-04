"""Configuração dos testes: coloca src/ no path e carrega os dados sintéticos."""
import sys
import pathlib
import pytest
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DADOS = ROOT / "dados"
EMPRESAS = ["construtora-horizonte", "fluxodata", "rede-bompreco"]


@pytest.fixture(scope="session")
def dados():
    """Devolve {slug: (dre_df, balanco_df)} das 3 empresas."""
    return {s: (pd.read_csv(DADOS / f"dre-{s}.csv"),
                pd.read_csv(DADOS / f"balanco-{s}.csv")) for s in EMPRESAS}


@pytest.fixture(scope="session")
def saas_df():
    return pd.read_csv(DADOS / "saas-fluxodata.csv")
