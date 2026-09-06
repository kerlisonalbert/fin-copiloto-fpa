"""
gerar_relatorio.py — Dashboard HTML do Oráculo (a vitrine).

A partir da DRE + Balanço, gera um relatório visual autossuficiente (um único
arquivo, sem dependência externa) com:
  - Faixa de KPIs do mês crítico
  - Painel denso de indicadores com semáforo (forma + cor + rótulo)
  - Gráfico EBITDA orçado x realizado (SVG puro, com tooltip e tabela equivalente)
  - Evolução de margens
  - Cascata do fluxo de caixa (DFC, método indireto)
  - Análise vertical, desvios materiais e a leitura do Oráculo

Números vêm do motor (analise_fpa + indicadores); a IA só narra.

Acessibilidade e visualização seguem uma paleta validada (separação sob
daltonismo), tema claro/escuro selecionado (não é inversão automática), e toda
informação de cor vem acompanhada de forma ou rótulo.

Uso: python src/gerar_relatorio.py dados/dre-<x>.csv dados/balanco-<x>.csv
"""

from __future__ import annotations
import argparse, html, json
from pathlib import Path

import analise_fpa as motor
import copiloto
import indicadores as ind
import saas as saas_mod


# ------------------------------ formatação --------------------------------
def brl(v): return f"R$ {v:,.0f}".replace(",", ".")


def brl_c(v):
    """Formato compacto — evita quebra de linha nos cartões."""
    a = abs(v)
    if a >= 1e6:  return f"R$ {v/1e6:,.2f} mi".replace(".", ",")
    if a >= 1e3:  return f"R$ {v/1e3:,.0f} mil".replace(",", ".")
    return f"R$ {v:,.0f}".replace(",", ".")


def pf(v): return f"{v*100:.1f}%" if v is not None else "—"
def xf(v): return f"{v:.2f}x" if v is not None else "—"
def df_(v): return f"{v:.0f}d" if v is not None else "—"


# ------------------------------ semáforo ----------------------------------
# Estado nunca é comunicado só por cor: cada um tem FORMA e RÓTULO próprios.
FORMA = {"bom": "●", "atencao": "▲", "critico": "■", "": "·"}
ROTULO = {"bom": "bom", "atencao": "atenção", "critico": "crítico", "": "neutro"}


def _sem(v, bom, atencao, maior_melhor=True):
    if v is None: return ""
    if maior_melhor:
        return "bom" if v >= bom else ("atencao" if v >= atencao else "critico")
    return "bom" if v <= bom else ("atencao" if v <= atencao else "critico")


def _cell(rot, valor, estado=""):
    marca = (f'<span class="mk {estado}" role="img" aria-label="{ROTULO[estado]}" '
             f'title="{ROTULO[estado]}">{FORMA[estado]}</span>') if estado else \
            '<span class="mk vazio" aria-hidden="true">·</span>'
    return (f'<div class="cell">{marca}'
            f'<span class="cl">{html.escape(rot)}</span>'
            f'<span class="cv">{html.escape(str(valor))}</span></div>')


def _grupo(titulo, cells):
    return (f'<section class="grupo"><h3>{html.escape(titulo)}</h3>'
            f'<div class="grid-ind">{"".join(cells)}</div></section>')


def _painel(res):
    r = res["rentabilidade"]; lq = res["liquidez"]
    en = res["endividamento"]; cg = res["capital_giro"]; sv = res["solvencia"]
    wacc = r["wacc"]
    mapa = {"Solvente": "bom", "Saudável": "bom", "Cinza": "atencao",
            "Risco": "atencao", "Perigo": "critico", "Insolvência": "critico"}

    rent = [
        _cell("Margem bruta", pf(r["margem_bruta"])),
        _cell("Margem EBITDA", pf(r["margem_ebitda"])),
        _cell("Margem líquida", pf(r["margem_liquida"])),
        _cell("ROE", pf(r["roe"]), _sem(r["roe"], wacc, 0)),
        _cell("ROIC", pf(r["roic"]), _sem(r["roic"], wacc, 0)),
        _cell("ROA", pf(r["roa"])),
        _cell("Giro do ativo", xf(r["giro_ativo"])),
        _cell("EVA", brl_c(r["eva"]), "bom" if r["eva"] > 0 else "critico"),
    ]
    liqu = [
        _cell("Liquidez corrente", xf(lq["liquidez_corrente"]), _sem(lq["liquidez_corrente"], 1.5, 1.0)),
        _cell("Liquidez seca", xf(lq["liquidez_seca"]), _sem(lq["liquidez_seca"], 1.0, 0.7)),
        _cell("Liquidez geral", xf(lq["liquidez_geral"]), _sem(lq["liquidez_geral"], 1.0, 0.8)),
        _cell("Liquidez imediata", xf(lq["liquidez_imediata"])),
    ]
    endi = [
        _cell("Dív. Líq / EBITDA", xf(en["div_liq_ebitda"]), _sem(en["div_liq_ebitda"], 2, 3, maior_melhor=False)),
        _cell("Dívida / PL", xf(en["divida_pl"]), _sem(en["divida_pl"], 1, 2, maior_melhor=False)),
        _cell("Cobertura de juros", xf(en["cobertura_juros"]), _sem(en["cobertura_juros"], 3, 1.5)),
        _cell("% no curto prazo", pf(en["composicao_endiv"])),
    ]
    giro = [
        _cell("Ciclo financeiro", df_(cg["ciclo_financeiro"])),
        _cell("PMR / PME / PMP", f"{cg['pmr']:.0f}/{cg['pme']:.0f}/{cg['pmp']:.0f}d"),
        _cell("NCG", brl_c(cg["ncg"])),
        _cell("Tesouraria (Fleuriet)", brl_c(cg["tesouraria"]), "bom" if cg["tesouraria"] > 0 else "critico"),
    ]
    solv = [
        _cell("Kanitz (insolvência)", f"{sv['kanitz']:.2f}", mapa.get(sv["kanitz_status"], "")),
        _cell("Altman Z' (fechada)", f"{sv['altman_z']:.2f}", mapa.get(sv["altman_status"], "")),
    ]
    return "".join([
        _grupo("Rentabilidade", rent), _grupo("Liquidez", liqu),
        _grupo("Endividamento / alavancagem", endi),
        _grupo("Capital de giro (Fleuriet)", giro), _grupo("Solvência", solv),
    ])


# --------------------------- infraestrutura de gráfico ---------------------
def _eixos(W, H, PL, PR, PT, PB, ymin, ymax, meses, fmt_y, n_grid=4):
    """Grade e eixos: hairlines sólidas, um tom acima da superfície (recessivas)."""
    Y = lambda v: PT + (H - PT - PB) * (1 - (v - ymin) / (ymax - ymin))
    X = lambda i: PL + (W - PL - PR) * (i / max(len(meses) - 1, 1))
    g = []
    for k in range(n_grid + 1):
        v = ymin + (ymax - ymin) * k / n_grid
        g.append(f"<line x1='{PL}' y1='{Y(v):.1f}' x2='{W-PR}' y2='{Y(v):.1f}' class='grid'/>")
        g.append(f"<text x='{PL-10}' y='{Y(v)+4:.1f}' class='ylab'>{fmt_y(v)}</text>")
    for i, m in enumerate(meses):
        if i % 2 == 0 or i == len(meses) - 1:
            g.append(f"<text x='{X(i):.1f}' y='{H-14}' class='xlab'>{m[5:]}</text>")
    return "".join(g), X, Y


def _tabela_serie(cabec, linhas):
    """Gêmea em tabela de cada gráfico — nenhum valor existe só no tooltip."""
    th = "".join(f"<th>{html.escape(c)}</th>" for c in cabec)
    tr = "".join("<tr>" + "".join(f"<td class='num'>{c}</td>" for c in ln) + "</tr>" for ln in linhas)
    return (f'<details class="tabela-twin"><summary>Ver os dados em tabela</summary>'
            f'<table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></details>')


# ------------------------------ gráfico EBITDA -----------------------------
def _svg_ebitda(df, mes_critico):
    s = (df[df["conta"] == "EBITDA"].sort_values("competencia")
         [["competencia", "orcado", "realizado"]])
    meses = s["competencia"].tolist(); orc = s["orcado"].tolist(); real = s["realizado"].tolist()
    W, H, PL, PR, PT, PB = 780, 300, 70, 96, 26, 44
    # Domínio ajustado aos dados (não forçado a zero): em gráfico de LINHA a
    # base zero comprime a série e esconde a variação, que é justamente a
    # história. Barra é que exige base zero — linha, não.
    lo, hi = min(min(orc), min(real)), max(max(orc), max(real))
    pad = max((hi - lo) * 0.45, hi * 0.04)
    ymin = max(0.0, lo - pad); ymax = hi + pad * 0.75
    grid, X, Y = _eixos(W, H, PL, PR, PT, PB, ymin, ymax, meses, lambda v: f"R$ {v/1e6:.1f}M")
    path = lambda vs: " ".join(("M" if i == 0 else "L") + f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(vs))

    n = len(meses); ic = meses.index(mes_critico)
    # marcadores >= 8px de diâmetro; alvo de hover bem maior que a marca
    pontos = "".join(
        f"<circle cx='{X(i):.1f}' cy='{Y(real[i]):.1f}' r='{6 if i==ic else 4.5}' "
        f"class='pt {'pt-crit' if i==ic else ''}'/>" for i in range(n))
    # rótulo direto seletivo: só o mês crítico e o ponto final de cada série
    lbl = (f"<text x='{X(ic):.1f}' y='{Y(real[ic])-14:.1f}' class='annot'>{mes_critico}</text>"
           f"<text x='{X(n-1)+10:.1f}' y='{Y(real[-1])+4:.1f}' class='dlab s1'>Realizado</text>"
           f"<text x='{X(n-1)+10:.1f}' y='{Y(orc[-1])+4:.1f}' class='dlab s2'>Orçado</text>")
    dados = json.dumps({
        "x": [X(i) for i in range(n)], "labels": meses,
        "series": [{"nome": "Realizado", "slot": 1, "y": [Y(v) for v in real],
                    "valores": [f"R$ {v:,.0f}".replace(",", ".") for v in real]},
                   {"nome": "Orçado", "slot": 2, "y": [Y(v) for v in orc],
                    "valores": [f"R$ {v:,.0f}".replace(",", ".") for v in orc]}],
        "topo": PT, "base": H - PB})
    svg = (f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' "
           f"aria-label='EBITDA orçado versus realizado ao longo de {n} meses'>"
           f"{grid}<path d='{path(orc)}' class='ln s2'/><path d='{path(real)}' class='ln s1'/>"
           f"{pontos}{lbl}<g class='cross'></g></svg>")
    tab = _tabela_serie(["Competência", "Orçado", "Realizado", "Desvio"],
                        [[m, brl(o), brl(r), f"{(r/o-1)*100:+.1f}%"] for m, o, r in zip(meses, orc, real)])
    return f"<div class='chart-wrap' data-chart='{html.escape(dados)}'>{svg}<div class='tip'></div></div>{tab}"


# ---------------------- gráfico MARGENS ao longo do ano --------------------
def _svg_margens(dre):
    piv = dre.pivot_table(index="competencia", columns="conta", values="realizado").sort_index()
    meses = piv.index.tolist()
    mb = (piv["Lucro Bruto"] / piv["Receita Líquida"]).tolist()
    me = (piv["EBITDA"] / piv["Receita Líquida"]).tolist()
    W, H, PL, PR, PT, PB = 780, 250, 56, 116, 20, 42
    lo, hi = min(min(mb), min(me)), max(max(mb), max(me))
    pad = max((hi - lo) * 0.40, 0.03)
    ymin = max(0.0, lo - pad); ymax = hi + pad * 0.6
    grid, X, Y = _eixos(W, H, PL, PR, PT, PB, ymin, ymax, meses, lambda v: f"{v*100:.0f}%")
    path = lambda vs: " ".join(("M" if i == 0 else "L") + f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(vs))
    n = len(meses)
    lbl = (f"<text x='{X(n-1)+10:.1f}' y='{Y(mb[-1])+4:.1f}' class='dlab s3'>Bruta {mb[-1]*100:.0f}%</text>"
           f"<text x='{X(n-1)+10:.1f}' y='{Y(me[-1])+4:.1f}' class='dlab s1'>EBITDA {me[-1]*100:.0f}%</text>")
    dados = json.dumps({
        "x": [X(i) for i in range(n)], "labels": meses,
        "series": [{"nome": "Margem bruta", "slot": 3, "y": [Y(v) for v in mb],
                    "valores": [f"{v*100:.1f}%" for v in mb]},
                   {"nome": "Margem EBITDA", "slot": 1, "y": [Y(v) for v in me],
                    "valores": [f"{v*100:.1f}%" for v in me]}],
        "topo": PT, "base": H - PB})
    svg = (f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' "
           f"aria-label='Margem bruta e margem EBITDA ao longo do ano'>"
           f"{grid}<path d='{path(mb)}' class='ln s3'/><path d='{path(me)}' class='ln s1'/>"
           f"{lbl}<g class='cross'></g></svg>")
    tab = _tabela_serie(["Competência", "Margem bruta", "Margem EBITDA"],
                        [[m, f"{a*100:.1f}%", f"{b*100:.1f}%"] for m, a, b in zip(meses, mb, me)])
    return f"<div class='chart-wrap' data-chart='{html.escape(dados)}'>{svg}<div class='tip'></div></div>{tab}"


# ------------------------- gráfico WATERFALL (DFC) -------------------------
def _svg_waterfall(f):
    steps = [("Lucro líq.", f["lucro_liquido"], "start"),
             ("+ D&A", f["depreciacao"], "flow"),
             ("± Cap. giro", f["var_capital_giro"], "flow"),
             ("= FCO", f["fco"], "subtotal"),
             ("− CAPEX", f["capex"], "flow"),
             ("= FCFF", f["fcff"], "subtotal"),
             ("− Dividendos", f["dividendos"], "flow"),
             ("Δ Caixa", f["delta_caixa"], "total")]
    W, H, PL, PR, PT, PB = 780, 300, 62, 20, 26, 54
    run = 0.0; bars = []
    for lab, val, kind in steps:
        if kind in ("start", "subtotal", "total"):
            base, top, run = 0.0, val, val
        else:
            base, top = run, run + val; run += val
        bars.append((lab, base, top, kind, val))
    allv = [b[1] for b in bars] + [b[2] for b in bars]
    ymax = max(allv) * 1.18; ymin = min(0, min(allv))
    Y = lambda v: PT + (H - PT - PB) * (1 - (v - ymin) / (ymax - ymin))
    n = len(steps); slot = (W - PL - PR) / n; bw = slot * 0.58
    out = [f"<line x1='{PL}' y1='{Y(0):.1f}' x2='{W-PR}' y2='{Y(0):.1f}' class='axis'/>"]
    for k in range(4):
        v = ymin + (ymax - ymin) * k / 3
        out.append(f"<line x1='{PL}' y1='{Y(v):.1f}' x2='{W-PR}' y2='{Y(v):.1f}' class='grid'/>")
        out.append(f"<text x='{PL-10}' y='{Y(v)+4:.1f}' class='ylab'>R$ {v/1e6:.1f}M</text>")
    for i, (lab, base, top, kind, val) in enumerate(bars):
        x = PL + slot * i + (slot - bw) / 2
        y = min(Y(base), Y(top)); h = max(abs(Y(base) - Y(top)), 2.0)
        cls = "wf-sub" if kind in ("start", "subtotal", "total") else ("wf-pos" if val >= 0 else "wf-neg")
        mostrar = top if kind in ("start", "subtotal", "total") else val
        sinal = "" if kind in ("start", "subtotal", "total") else ("+" if val >= 0 else "−")
        out.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{h:.1f}' rx='4' class='{cls}'>"
                   f"<title>{html.escape(lab)}: R$ {val:,.0f}</title></rect>")
        out.append(f"<text x='{x+bw/2:.1f}' y='{min(Y(base),Y(top))-7:.1f}' class='wf-val'>"
                   f"{sinal}{abs(mostrar)/1e6:.1f}</text>")
        out.append(f"<text x='{x+bw/2:.1f}' y='{H-16}' class='wf-lab'>{html.escape(lab)}</text>")
    svg = (f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' "
           f"aria-label='Cascata do fluxo de caixa, do lucro líquido à variação de caixa'>"
           f"{''.join(out)}</svg>")
    tab = _tabela_serie(["Etapa", "Valor", "Efeito"],
                        [[l, brl(v), ("entra" if v >= 0 else "sai") if k == "flow" else "subtotal"]
                         for l, v, k in steps])
    leg = ("<div class='legenda'>"
           "<span><i class='sw wf-pos'></i>entra no caixa (+)</span>"
           "<span><i class='sw wf-neg'></i>sai do caixa (−)</span>"
           "<span><i class='sw wf-sub'></i>subtotal</span></div>")
    return f"{leg}<div class='chart-wrap'>{svg}</div>{tab}"


# ------------------------------ card SaaS ---------------------------------
def _card_saas(m):
    cells = [
        _cell("Clientes", f"{m['clientes']:,}".replace(",", ".")),
        _cell("MRR", brl_c(m["mrr"])), _cell("ARR", brl_c(m["arr"])),
        _cell("ARPA (R$/cliente)", f"R$ {m['arpa']:.0f}"),
        _cell("CAC", f"R$ {m['cac']:.0f}"), _cell("LTV", brl_c(m["ltv"])),
        _cell("LTV / CAC", f"{m['ltv_cac']:.1f}x", _sem(m["ltv_cac"], 3, 1)),
        _cell("Payback (meses)", f"{m['payback_meses']:.1f}", _sem(m["payback_meses"], 12, 18, maior_melhor=False)),
        _cell("Churn mensal", pf(m["churn_mensal"]), _sem(m["churn_mensal"], 0.03, 0.05, maior_melhor=False)),
        _cell("Churn anual", pf(m["churn_anual"])),
        _cell("NRR (anual)", pf(m["nrr_anual"]), _sem(m["nrr_anual"], 1.0, 0.9)),
        _cell("Pico de churn", m["churn_pico"]),
    ]
    return (f'<article class="card"><header class="card-h"><h2>Métricas SaaS</h2>'
            f'<p class="hint">Unit economics de receita recorrente. Semáforo pelas metas de '
            f'mercado (LTV/CAC ≥ 3, payback ≤ 12m, churn ≤ 3%, NRR ≥ 100%).</p></header>'
            f'<div class="grid-ind">{"".join(cells)}</div></article>')


# ------------------------------ análise vertical ---------------------------
def _vertical(dre, comp):
    av = ind.analise_vertical(dre, comp)
    val = motor.dre_competencia(dre, comp)
    real = {d["conta"]: d["realizado"] for d in val.to_dict("records")}
    linhas = ""
    for c in ["Receita Líquida", "CMV", "Lucro Bruto", "Despesas Comerciais",
              "Despesas Administrativas", "EBITDA"]:
        linhas += (f"<tr><td>{html.escape(c)}</td>"
                   f"<td class='num'>{brl(real.get(c, 0))}</td>"
                   f"<td class='num'>{pf(av[c])}</td></tr>")
    return linhas


# ------------------------------ montagem ----------------------------------
def _tile(rot, val, sub, estado=""):
    marca = (f'<span class="mk {estado}" aria-label="{ROTULO[estado]}" title="{ROTULO[estado]}">'
             f'{FORMA[estado]}</span>') if estado else ""
    return (f'<div class="tile {estado}"><div class="tile-lab">{html.escape(rot)}{marca}</div>'
            f'<div class="tile-val">{html.escape(val)}</div>'
            f'<div class="tile-sub">{html.escape(sub)}</div></div>')


def gerar_html(dre, bal, materialidade=0.05, comp_bal="2025-12", saas_metrics=None):
    b = copiloto.montar_briefing(dre, materialidade)
    mes = b["mes_critico"]
    res = ind.resumo(dre, bal, comp=comp_bal)
    dcrit = {d["conta"]: d for d in b["dre_mes_critico"]}

    def pctd(conta):
        d = dcrit.get(conta)
        return (d["variacao_abs"] / d["orcado"] * 100) if d and d["orcado"] else 0.0

    kpi = next((k for k in b["kpis"] if k["competencia"] == mes), {})
    m_real = (kpi.get("margem_ebitda_real") or 0); m_orc = (kpi.get("margem_ebitda_orc") or 0)
    tiles = (
        _tile("Receita líquida", brl_c(dcrit["Receita Líquida"]["realizado"]),
              f"{pctd('Receita Líquida'):+.1f}% vs orçado",
              _sem(pctd("Receita Líquida"), -2, -8)) +
        _tile("CMV (custo)", brl_c(dcrit["CMV"]["realizado"]),
              f"{pctd('CMV'):+.1f}% vs orçado",
              _sem(pctd("CMV"), 2, 8, maior_melhor=False)) +
        _tile("EBITDA", brl_c(dcrit["EBITDA"]["realizado"]),
              f"{pctd('EBITDA'):+.1f}% vs orçado",
              _sem(pctd("EBITDA"), -2, -15)) +
        _tile("Margem EBITDA", f"{m_real*100:.1f}%", f"plano: {m_orc*100:.1f}%",
              _sem(m_real - m_orc, -0.01, -0.05))
    )

    achados = "".join(
        f"<tr><td>{a['competencia']}</td><td>{html.escape(a['conta'])}</td>"
        f"<td class='num'>{brl(a['orcado'])}</td><td class='num'>{brl(a['realizado'])}</td>"
        f"<td class='num neg'>{a['variacao_pct']*100:+.1f}%</td></tr>" for a in b["achados"][:8])
    narrativa = html.escape(copiloto.narrar_offline(b)).replace("\n", "<br>")

    fx = res["fluxo_caixa"]
    dfc_resumo = (f"FCO {brl_c(fx['fco'])} · FCFF {brl_c(fx['fcff'])} · "
                  f"Δ Caixa {brl_c(fx['delta_caixa'])}")
    return _TEMPLATE.format(
        empresa=html.escape(b["empresa"]), setor=html.escape(b["setor"]), periodo=b["periodo"],
        mes=mes, ref=comp_bal, tiles=tiles, painel=_painel(res),
        grafico=_svg_ebitda(dre, mes), waterfall=_svg_waterfall(fx), dfc_resumo=dfc_resumo,
        margens=_svg_margens(dre), saas=_card_saas(saas_metrics) if saas_metrics else "",
        vertical=_vertical(dre, mes), achados=achados, narrativa=narrativa,
        materialidade=f"{materialidade*100:.0f}")


_TEMPLATE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oráculo — {empresa}</title>
<style>
/* ---- Paleta validada (separação sob daltonismo). Tema claro é a base;
       o escuro tem passos próprios, não é uma inversão automática. ------- */
:root{{
  color-scheme: light;
  --plano:#f3f3f0; --surf:#fcfcfb; --surf2:#f7f7f4;
  --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --neg:#e34948;
  --bom:#0ca30c; --atencao:#fab219; --critico:#d03b3b;
  --shadow:0 1px 2px rgba(11,11,11,.05),0 4px 14px rgba(11,11,11,.05);
}}
@media (prefers-color-scheme: dark){{
  :root:where(:not([data-theme="light"])){{
    color-scheme: dark;
    --plano:#0d0d0d; --surf:#1a1a19; --surf2:#212120;
    --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --neg:#e66767;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"]{{
  color-scheme: dark;
  --plano:#0d0d0d; --surf:#1a1a19; --surf2:#212120;
  --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --neg:#e66767;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.35);
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--plano);color:var(--ink);
  font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:1160px;margin:0 auto;padding:0 20px 56px}}

/* ---- topo ---- */
/* Sem position:sticky de propósito: o relatório é capturado inteiro em PNG
   para o Telegram, e um cabeçalho fixo se sobrepõe ao conteúdo na captura. */
.top{{background:var(--surf);border-bottom:1px solid var(--ring);margin-bottom:22px}}
.top-in{{max-width:1160px;margin:0 auto;padding:16px 20px;display:flex;
  align-items:flex-end;gap:20px;flex-wrap:wrap}}
.brand{{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}
h1{{font-size:22px;margin:2px 0 3px;font-weight:650;letter-spacing:-.01em}}
.sub{{color:var(--ink2);font-size:13px}}
.sub b{{color:var(--ink);font-weight:600}}
.top-sp{{flex:1}}
.tema{{display:flex;gap:2px;background:var(--surf2);border:1px solid var(--ring);
  border-radius:8px;padding:3px}}
.tema button{{border:0;background:none;color:var(--ink2);font:inherit;font-size:12px;
  padding:5px 10px;border-radius:6px;cursor:pointer}}
.tema button[aria-pressed="true"]{{background:var(--surf);color:var(--ink);
  box-shadow:var(--shadow);font-weight:600}}

/* ---- KPIs ---- */
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:14px;margin-bottom:20px}}
.tile{{background:var(--surf);border:1px solid var(--ring);border-radius:12px;
  padding:15px 17px;box-shadow:var(--shadow)}}
.tile-lab{{font-size:11px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);display:flex;align-items:center;gap:6px}}
.tile-val{{font-size:29px;font-weight:660;margin:5px 0 2px;letter-spacing:-.02em}}
.tile-sub{{font-size:12px;color:var(--ink2)}}
.tile.critico{{border-color:color-mix(in srgb,var(--critico) 45%,var(--ring))}}
.tile.atencao{{border-color:color-mix(in srgb,var(--atencao) 45%,var(--ring))}}

/* ---- cartões ---- */
.card{{background:var(--surf);border:1px solid var(--ring);border-radius:12px;
  padding:18px 20px 20px;box-shadow:var(--shadow);margin-bottom:18px}}
.card-h{{margin-bottom:14px}}
h2{{font-size:15px;margin:0;font-weight:640;letter-spacing:-.005em}}
h3{{font-size:10.5px;margin:0 0 7px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);font-weight:600}}
.hint{{color:var(--ink2);font-size:12.5px;margin:5px 0 0}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
@media(max-width:860px){{.cols{{grid-template-columns:1fr}}}}

/* ---- indicadores ---- */
.grupo{{margin-bottom:14px}}
.grid-ind{{display:grid;grid-template-columns:repeat(auto-fit,minmax(212px,1fr));gap:7px}}
.cell{{display:flex;align-items:center;gap:8px;background:var(--surf2);
  border:1px solid var(--ring);border-radius:8px;padding:8px 11px}}
.cl{{flex:1;color:var(--ink2);font-size:12.5px}}
.cv{{font-weight:640;font-variant-numeric:tabular-nums}}
.mk{{font-size:10px;line-height:1;width:11px;text-align:center}}
.mk.bom{{color:var(--bom)}} .mk.atencao{{color:var(--atencao)}}
.mk.critico{{color:var(--critico)}} .mk.vazio{{color:var(--axis)}}
.legenda-sem{{display:flex;gap:15px;flex-wrap:wrap;color:var(--ink2);
  font-size:12px;margin-top:12px;padding-top:12px;border-top:1px solid var(--ring)}}

/* ---- gráficos ---- */
.chart-wrap{{position:relative}}
.chart{{width:100%;height:auto;display:block;overflow:visible}}
.grid{{stroke:var(--grid);stroke-width:1}}
.axis{{stroke:var(--axis);stroke-width:1}}
.ylab,.xlab{{fill:var(--muted);font-size:10.5px;font-variant-numeric:tabular-nums}}
.ylab{{text-anchor:end}} .xlab{{text-anchor:middle}}
.ln{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}
.ln.s1{{stroke:var(--s1)}} .ln.s2{{stroke:var(--s2)}} .ln.s3{{stroke:var(--s3)}}
.pt{{fill:var(--s1);stroke:var(--surf);stroke-width:2}}
.pt-crit{{fill:var(--critico)}}
.annot{{fill:var(--critico);font-size:11px;font-weight:650;text-anchor:middle}}
.dlab{{font-size:11.5px;font-weight:620;dominant-baseline:middle}}
.dlab.s1{{fill:var(--s1)}} .dlab.s2{{fill:var(--s2)}} .dlab.s3{{fill:var(--s3)}}
/* Subtotais em cinza neutro nos dois temas: são as barras maiores, e se
   levarem cor viram o elemento mais alto E mais chamativo, roubando a atenção
   dos fluxos, que são a informação nova. */
.wf-pos{{fill:var(--s1)}} .wf-neg{{fill:var(--neg)}} .wf-sub{{fill:var(--muted)}}
.wf-val{{fill:var(--ink2);font-size:10.5px;text-anchor:middle;font-variant-numeric:tabular-nums}}
.wf-lab{{fill:var(--muted);font-size:10.5px;text-anchor:middle}}
.cross line{{stroke:var(--axis);stroke-width:1}}
.legenda{{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:12px;margin-bottom:8px}}
.legenda span{{display:flex;align-items:center;gap:6px}}
.sw{{width:11px;height:11px;border-radius:3px;display:inline-block}}
i.sw.wf-pos{{background:var(--s1)}} i.sw.wf-neg{{background:var(--neg)}}
i.sw.wf-sub{{background:var(--muted)}}
.tip{{position:absolute;pointer-events:none;opacity:0;transition:opacity .09s;
  background:var(--surf);border:1px solid var(--ring);border-radius:8px;
  box-shadow:var(--shadow);padding:8px 11px;font-size:12px;min-width:150px;z-index:5}}
.tip b{{display:block;margin-bottom:4px;font-size:11px;color:var(--muted);
  letter-spacing:.05em;text-transform:uppercase}}
.tip .row{{display:flex;align-items:center;gap:7px;justify-content:space-between}}
.tip .row span:last-child{{font-weight:640;font-variant-numeric:tabular-nums}}
.tip i{{width:9px;height:9px;border-radius:50%;display:inline-block;flex:0 0 auto}}

/* ---- tabelas ---- */
.tbl{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:8px}}
.tbl th{{text-align:left;color:var(--muted);font-weight:600;font-size:10.5px;
  letter-spacing:.07em;text-transform:uppercase;padding:7px 9px;
  border-bottom:1px solid var(--axis);white-space:nowrap}}
.tbl th.ord{{cursor:pointer;user-select:none}}
.tbl th.ord:hover{{color:var(--ink)}}
.tbl td{{padding:7px 9px;border-bottom:1px solid var(--grid)}}
.tbl .num{{text-align:right;font-variant-numeric:tabular-nums}}
.tbl .neg{{color:var(--critico);font-weight:620}}
.tabela-twin{{margin-top:12px}}
.tabela-twin summary{{cursor:pointer;color:var(--ink2);font-size:12px;
  padding:6px 0;user-select:none}}
.tabela-twin summary:hover{{color:var(--ink)}}
.scroll-x{{overflow-x:auto}}

.narr{{background:var(--surf2);border:1px solid var(--ring);border-left:3px solid var(--s1);
  border-radius:8px;padding:14px 16px;color:var(--ink2);font-size:13px;line-height:1.65}}
footer{{color:var(--muted);font-size:11.5px;margin-top:24px;line-height:1.7;
  border-top:1px solid var(--ring);padding-top:16px}}
@media print{{.tema{{display:none}} .card{{break-inside:avoid}}}}
</style></head><body>

<div class="top"><div class="top-in">
  <div>
    <div class="brand">Oráculo · copiloto de FP&amp;A</div>
    <h1>{empresa}</h1>
    <div class="sub">{setor} · período {periodo} · mês crítico <b>{mes}</b> · balanço em {ref}</div>
  </div>
  <div class="top-sp"></div>
  <div class="tema" role="group" aria-label="Tema">
    <button data-t="auto" aria-pressed="true">Auto</button>
    <button data-t="light" aria-pressed="false">Claro</button>
    <button data-t="dark" aria-pressed="false">Escuro</button>
  </div>
</div></div>

<div class="wrap">

<div class="kpis">{tiles}</div>

<article class="card">
  <header class="card-h"><h2>Painel de indicadores</h2>
  <p class="hint">Calculados sobre o balanço de {ref} e a DRE do ano.</p></header>
  {painel}
  <div class="legenda-sem">
    <span><span class="mk bom">●</span> bom</span>
    <span><span class="mk atencao">▲</span> atenção</span>
    <span><span class="mk critico">■</span> crítico</span>
    <span>Forma e cor juntas — o estado nunca depende só da cor.</span>
  </div>
</article>

<article class="card">
  <header class="card-h"><h2>EBITDA — orçado × realizado</h2>
  <p class="hint">Duas séries no mesmo eixo. O ponto destacado é o mês crítico.</p></header>
  {grafico}
</article>

<article class="card">
  <header class="card-h"><h2>Margens ao longo do ano</h2>
  <p class="hint">Realizado, como percentual da receita líquida.</p></header>
  {margens}
</article>

<article class="card">
  <header class="card-h"><h2>Fluxo de caixa — DFC (método indireto)</h2>
  <p class="hint">Do lucro líquido ao caixa. {dfc_resumo}</p></header>
  {waterfall}
</article>

{saas}

<div class="cols">
  <article class="card">
    <header class="card-h"><h2>Análise vertical — DRE de {mes}</h2>
    <p class="hint">Cada linha como percentual da receita líquida (realizado).</p></header>
    <div class="scroll-x"><table class="tbl"><thead><tr>
      <th class="ord">Conta</th><th class="ord num">Realizado</th><th class="ord num">% da RL</th>
    </tr></thead><tbody>{vertical}</tbody></table></div>
  </article>

  <article class="card">
    <header class="card-h"><h2>Desvios materiais</h2>
    <p class="hint">Acima de {materialidade}% e desfavoráveis, do maior para o menor.</p></header>
    <div class="scroll-x"><table class="tbl"><thead><tr>
      <th class="ord">Compet.</th><th class="ord">Conta</th><th class="ord num">Orçado</th>
      <th class="ord num">Realizado</th><th class="ord num">Desvio</th>
    </tr></thead><tbody>{achados}</tbody></table></div>
  </article>
</div>

<article class="card">
  <header class="card-h"><h2>Leitura do Oráculo</h2>
  <p class="hint">Texto gerado a partir dos números acima — nenhum valor foi estimado.</p></header>
  <div class="narr">{narrativa}</div>
</article>

<footer>
  Dados <b>100% sintéticos</b>, gerados de forma determinística para demonstração —
  não representam empresa real.<br>
  Todos os números vêm de cálculo em Python, rastreáveis por competência e conta.
  Conteúdo educacional e gerencial: <b>não constitui recomendação de investimento</b>.
</footer>
</div>

<script>
(function(){{
  /* ---------- tema: auto (sistema) / claro / escuro ---------- */
  var root=document.documentElement, bts=document.querySelectorAll('.tema button');
  function aplicar(t){{
    if(t==='auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme',t);
    bts.forEach(function(b){{b.setAttribute('aria-pressed', b.dataset.t===t?'true':'false');}});
    try{{localStorage.setItem('oraculo-tema',t);}}catch(e){{}}
  }}
  var salvo='auto';
  try{{salvo=localStorage.getItem('oraculo-tema')||'auto';}}catch(e){{}}
  aplicar(salvo);
  bts.forEach(function(b){{b.addEventListener('click',function(){{aplicar(b.dataset.t);}});}});

  /* ---------- tooltip com crosshair nos gráficos de linha ---------- */
  var CORES={{1:'--s1',2:'--s2',3:'--s3'}};
  document.querySelectorAll('.chart-wrap[data-chart]').forEach(function(w){{
    var d; try{{d=JSON.parse(w.dataset.chart);}}catch(e){{return;}}
    var svg=w.querySelector('svg'), tip=w.querySelector('.tip'), cross=svg.querySelector('.cross');
    var vb=svg.viewBox.baseVal;
    function idx(px){{
      var i=0,melhor=1e9;
      d.x.forEach(function(x,k){{var v=Math.abs(x-px); if(v<melhor){{melhor=v;i=k;}}}});
      return i;
    }}
    function mover(ev){{
      var r=svg.getBoundingClientRect();
      var px=(ev.clientX-r.left)/r.width*vb.width;
      var i=idx(px);
      cross.innerHTML="<line x1='"+d.x[i]+"' y1='"+d.topo+"' x2='"+d.x[i]+"' y2='"+d.base+"'/>";
      var linhas=d.series.map(function(s){{
        return "<div class='row'><span><i style='background:var("+CORES[s.slot]+")'></i>"+
               s.nome+"</span><span>"+s.valores[i]+"</span></div>";
      }}).join('');
      tip.innerHTML="<b>"+d.labels[i]+"</b>"+linhas;
      tip.style.opacity=1;
      var xr=d.x[i]/vb.width*r.width;
      tip.style.left=Math.min(Math.max(xr-tip.offsetWidth/2,0),r.width-tip.offsetWidth)+'px';
      tip.style.top='4px';
    }}
    function sair(){{tip.style.opacity=0;cross.innerHTML='';}}
    svg.addEventListener('mousemove',mover);
    svg.addEventListener('mouseleave',sair);
    svg.addEventListener('touchmove',function(e){{mover(e.touches[0]);}},{{passive:true}});
  }});

  /* ---------- tabelas ordenáveis ---------- */
  document.querySelectorAll('th.ord').forEach(function(th){{
    th.addEventListener('click',function(){{
      var tb=th.closest('table'), corpo=tb.tBodies[0];
      var col=Array.prototype.indexOf.call(th.parentNode.children,th);
      var asc=th.dataset.asc!=='1'; th.dataset.asc=asc?'1':'0';
      var num=function(s){{
        var v=parseFloat(s.replace(/[^0-9,.\\-−+]/g,'').replace(/\\./g,'').replace(',','.').replace('−','-'));
        return isNaN(v)?null:v;
      }};
      var linhas=Array.prototype.slice.call(corpo.rows);
      linhas.sort(function(a,b){{
        var x=a.cells[col].textContent.trim(), y=b.cells[col].textContent.trim();
        var nx=num(x), ny=num(y);
        var c=(nx!==null&&ny!==null)?nx-ny:x.localeCompare(y,'pt-BR');
        return asc?c:-c;
      }});
      linhas.forEach(function(l){{corpo.appendChild(l);}});
    }});
  }});
}})();
</script>
</body></html>"""


def main():
    p = argparse.ArgumentParser(description="Dashboard do Oráculo")
    p.add_argument("dre"); p.add_argument("balanco")
    p.add_argument("--saas", default=None, help="CSV de dados SaaS (opcional)")
    p.add_argument("--saida", default=None)
    p.add_argument("--materialidade", type=float, default=0.05)
    a = p.parse_args()
    dre = motor.carregar_dre(a.dre); bal = motor.carregar_dre(a.balanco)
    sm = saas_mod.metricas(saas_mod.carregar(a.saas)) if a.saas else None
    doc = gerar_html(dre, bal, a.materialidade, saas_metrics=sm)

    # A saída é ancorada na PASTA DO PROJETO, não na pasta de onde o comando foi
    # chamado. Sem isso, um agente que roda o script de outro diretório espalha
    # relatórios pelo disco — e o caminho relativo que ele informa não resolve.
    dre_path = Path(a.dre).resolve()
    raiz = dre_path.parent.parent if dre_path.parent.name == "dados" else dre_path.parent
    nome = f"relatorio-{dre_path.stem.replace('dre-', '')}.html"
    saida = (Path(a.saida).resolve() if a.saida else (raiz / "exemplos" / nome))
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(doc, encoding="utf-8")
    # Caminho ABSOLUTO: é o que o agente precisa para anexar o arquivo no chat.
    print(f"Relatório gerado: {saida}")


if __name__ == "__main__":
    main()
