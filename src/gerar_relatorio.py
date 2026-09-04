"""
gerar_relatorio.py — Dashboard HTML RICO do Oráculo (a vitrine).

A partir da DRE + Balanço, gera um relatório visual autossuficiente com:
  - KPIs do mês crítico
  - Painel denso de indicadores (rentabilidade, liquidez, endividamento,
    capital de giro/Fleuriet, solvência) com SEMÁFORO
  - Gráfico EBITDA orçado x realizado (SVG puro)
  - Análise vertical (DRE % da receita)
  - Achados materiais + leitura do Oráculo

Números vêm do motor (analise_fpa + indicadores); a IA só narra.

Uso: python src/gerar_relatorio.py dados/dre-<x>.csv dados/balanco-<x>.csv
"""

from __future__ import annotations
import argparse, html
from pathlib import Path

import analise_fpa as motor
import copiloto
import indicadores as ind
import saas as saas_mod


# ------------------------------ formatação --------------------------------
def brl(v): return f"R$ {v:,.0f}".replace(",", ".")
def brl_c(v):
    if abs(v) >= 1e6: return f"R$ {v/1e6:.2f} mi".replace(".", ",")
    if abs(v) >= 1e3: return f"R$ {v/1e3:.0f} mil"
    return f"R$ {v:.0f}"
def pf(v): return f"{v*100:.1f}%" if v is not None else "—"
def xf(v): return f"{v:.2f}x" if v is not None else "—"
def df_(v): return f"{v:.0f}d" if v is not None else "—"


# ------------------------------ semáforo ----------------------------------
def _sem(v, bom, atencao, maior_melhor=True):
    if v is None: return ""
    if maior_melhor:
        return "bom" if v >= bom else ("atencao" if v >= atencao else "critico")
    return "bom" if v <= bom else ("atencao" if v <= atencao else "critico")

def _cell(rot, valor, estado=""):
    return (f'<div class="cell"><span class="dot {estado}"></span>'
            f'<span class="cl">{html.escape(rot)}</span>'
            f'<span class="cv">{html.escape(str(valor))}</span></div>')

def _grupo(titulo, cells):
    return (f'<div class="indic-group"><h3>{titulo}</h3>'
            f'<div class="indic-grid">{"".join(cells)}</div></div>')


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
        _grupo("Endividamento / Alavancagem", endi),
        _grupo("Capital de giro (Fleuriet)", giro), _grupo("Solvência", solv),
    ])


# ------------------------------ análise vertical ---------------------------
def _vertical(dre, comp):
    av = ind.analise_vertical(dre, comp)
    linhas = ""
    for c in ["Receita Líquida", "CMV", "Lucro Bruto", "Despesas Comerciais",
              "Despesas Administrativas", "EBITDA"]:
        val = motor.dre_competencia(dre, comp)
        real = {d["conta"]: d["realizado"] for d in val.to_dict("records")}
        linhas += (f"<tr><td>{html.escape(c)}</td><td class='num'>{brl(real.get(c,0))}</td>"
                   f"<td class='num'>{pf(av[c])}</td></tr>")
    return linhas


# ------------------------------ gráfico EBITDA -----------------------------
def _svg_ebitda(df, mes_critico):
    serie = (df[df["conta"] == "EBITDA"].sort_values("competencia")
             [["competencia", "orcado", "realizado"]])
    meses = serie["competencia"].tolist(); orc = serie["orcado"].tolist(); real = serie["realizado"].tolist()
    W, H, PL, PR, PT, PB = 760, 300, 64, 24, 22, 42
    ymax = max(max(orc), max(real)) * 1.12; ymin = min(0, min(real)); n = len(meses)
    X = lambda i: PL + (W-PL-PR)*(i/max(n-1, 1))
    Y = lambda v: PT + (H-PT-PB)*(1-(v-ymin)/(ymax-ymin))
    path = lambda vs: " ".join(("M" if i == 0 else "L")+f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(vs))
    grid = "".join(f"<line x1='{PL}' y1='{Y(ymin+(ymax-ymin)*k/4):.1f}' x2='{W-PR}' y2='{Y(ymin+(ymax-ymin)*k/4):.1f}' class='grid'/>"
                   f"<text x='{PL-10}' y='{Y(ymin+(ymax-ymin)*k/4)+4:.1f}' class='ylab'>R$ {(ymin+(ymax-ymin)*k/4)/1e6:.1f}M</text>" for k in range(5))
    xlab = "".join(f"<text x='{X(i):.1f}' y='{H-14}' class='xlab'>{m[5:]}</text>" for i, m in enumerate(meses) if i % 2 == 0 or i == n-1)
    dcls = lambda m: "dot-crit" if m == mes_critico else "dot-real"
    dots = "".join(f"<circle cx='{X(i):.1f}' cy='{Y(real[i]):.1f}' r='{5 if m==mes_critico else 3.3}' class='{dcls(m)}'><title>{m}: R$ {real[i]:,.0f}</title></circle>" for i, m in enumerate(meses))
    ic = meses.index(mes_critico)
    annot = f"<text x='{X(ic):.1f}' y='{Y(real[ic])-12:.1f}' class='annot'>{mes_critico}</text>"
    return (f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' aria-label='EBITDA orçado vs realizado'>"
            f"{grid}{xlab}<path d='{path(orc)}' class='line-orc'/><path d='{path(real)}' class='line-real'/>{dots}{annot}</svg>")


# ---------------------- gráfico MARGENS ao longo do ano --------------------
def _svg_margens(dre):
    piv = dre.pivot_table(index="competencia", columns="conta", values="realizado").sort_index()
    meses = piv.index.tolist()
    mb = (piv["Lucro Bruto"] / piv["Receita Líquida"]).tolist()
    me = (piv["EBITDA"] / piv["Receita Líquida"]).tolist()
    W, H, PL, PR, PT, PB = 760, 260, 46, 70, 18, 40
    ymax = max(max(mb), max(me)) * 1.15; ymin = min(0, min(me)); n = len(meses)
    X = lambda i: PL + (W-PL-PR) * (i/max(n-1, 1))
    Y = lambda v: PT + (H-PT-PB) * (1 - (v-ymin)/(ymax-ymin))
    path = lambda vs: " ".join(("M" if i == 0 else "L")+f"{X(i):.1f} {Y(v):.1f}" for i, v in enumerate(vs))
    grid = "".join(f"<line x1='{PL}' y1='{Y(ymin+(ymax-ymin)*k/4):.1f}' x2='{W-PR}' y2='{Y(ymin+(ymax-ymin)*k/4):.1f}' class='grid'/>"
                   f"<text x='{PL-8}' y='{Y(ymin+(ymax-ymin)*k/4)+4:.1f}' class='ylab'>{(ymin+(ymax-ymin)*k/4)*100:.0f}%</text>" for k in range(5))
    xlab = "".join(f"<text x='{X(i):.1f}' y='{H-13}' class='xlab'>{m[5:]}</text>" for i, m in enumerate(meses) if i % 2 == 0 or i == n-1)
    lbl = (f"<text x='{X(n-1)+6:.1f}' y='{Y(me[-1])+4:.1f}' class='lab-real'>EBITDA {me[-1]*100:.0f}%</text>"
           f"<text x='{X(n-1)+6:.1f}' y='{Y(mb[-1])+4:.1f}' class='lab-bruta'>Bruta {mb[-1]*100:.0f}%</text>")
    return (f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' aria-label='Margens ao longo do ano'>"
            f"{grid}{xlab}<path d='{path(mb)}' class='line-bruta'/><path d='{path(me)}' class='line-real'/>{lbl}</svg>")


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
    return (f'<div class="card"><h2>Métricas SaaS</h2>'
            f'<p class="hint">Unit economics de receita recorrente. Semáforo pelas metas de mercado '
            f'(LTV/CAC ≥ 3, payback ≤ 12m, churn ≤ 3%, NRR ≥ 100%).</p>'
            f'<div class="indic-grid">{"".join(cells)}</div></div>')


# ------------------------- gráfico WATERFALL (DFC) -------------------------
def _svg_waterfall(f):
    steps = [("Lucro líq.", f["lucro_liquido"], "start"),
             ("+ D&A", f["depreciacao"], "flow"),
             ("± Cap.giro", f["var_capital_giro"], "flow"),
             ("= FCO", f["fco"], "subtotal"),
             ("− CAPEX", f["capex"], "flow"),
             ("= FCFF", f["fcff"], "subtotal"),
             ("− Divid.", f["dividendos"], "flow"),
             ("Δ Caixa", f["delta_caixa"], "total")]
    W, H, PL, PR, PT, PB = 760, 290, 40, 16, 18, 50
    run = 0.0; bars = []
    for lab, val, kind in steps:
        if kind in ("start", "subtotal", "total"):
            base, top, run = 0.0, val, val
        else:
            base, top = run, run + val; run += val
        bars.append((lab, base, top, kind, val))
    allv = [b[1] for b in bars] + [b[2] for b in bars]
    ymax = max(allv) * 1.14; ymin = min(0, min(allv))
    Y = lambda v: PT + (H-PT-PB) * (1 - (v-ymin)/(ymax-ymin))
    n = len(steps); slot = (W-PL-PR)/n; bw = slot*0.62
    out = [f"<line x1='{PL}' y1='{Y(0):.1f}' x2='{W-PR}' y2='{Y(0):.1f}' class='grid'/>"]
    for i, (lab, base, top, kind, val) in enumerate(bars):
        x = PL + slot*i + (slot-bw)/2
        y = min(Y(base), Y(top)); h = max(abs(Y(base)-Y(top)), 1.5)
        cls = ({"start": "wf-tot", "subtotal": "wf-sub", "total": "wf-tot"}
               .get(kind, "wf-up" if val >= 0 else "wf-down"))
        mostrar = top if kind in ("start", "subtotal", "total") else val
        out.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{h:.1f}' rx='3' class='{cls}'>"
                   f"<title>{lab}: R$ {val:,.0f}</title></rect>")
        out.append(f"<text x='{x+bw/2:.1f}' y='{Y(max(base,top))-5:.1f}' class='wf-val'>{mostrar/1e6:+.1f}</text>")
        out.append(f"<text x='{x+bw/2:.1f}' y='{H-14}' class='wf-lab'>{lab}</text>")
    return f"<svg viewBox='0 0 {W} {H}' class='chart' role='img' aria-label='Cascata do fluxo de caixa'>{''.join(out)}</svg>"


# ------------------------------ montagem ----------------------------------
def gerar_html(dre, bal, materialidade=0.05, comp_bal="2025-12", saas_metrics=None):
    b = copiloto.montar_briefing(dre, materialidade)
    mes = b["mes_critico"]
    res = ind.resumo(dre, bal, comp=comp_bal)
    dcrit = {d["conta"]: d for d in b["dre_mes_critico"]}

    def pctd(conta):
        d = dcrit.get(conta); return (d["variacao_abs"]/d["orcado"]*100) if d and d["orcado"] else 0.0

    kpi = next((k for k in b["kpis"] if k["competencia"] == mes), {})
    tiles = (_tile("Receita Líquida", brl_c(dcrit["Receita Líquida"]["realizado"]), f"{pctd('Receita Líquida'):+.1f}% vs orçado")
             + _tile("CMV (custo)", brl_c(dcrit["CMV"]["realizado"]), f"{pctd('CMV'):+.1f}% vs orçado", "ruim" if pctd("CMV") > 5 else "")
             + _tile("EBITDA", brl_c(dcrit["EBITDA"]["realizado"]), f"{pctd('EBITDA'):+.1f}% vs orçado", "critico" if pctd("EBITDA") < -5 else "")
             + _tile("Margem EBITDA", f"{(kpi.get('margem_ebitda_real') or 0)*100:.1f}%", f"plano: {(kpi.get('margem_ebitda_orc') or 0)*100:.1f}%",
                     "critico" if (kpi.get('margem_ebitda_real') or 0) < (kpi.get('margem_ebitda_orc') or 0) - 0.02 else ""))

    achados = "".join(f"<tr><td>{a['competencia']}</td><td>{html.escape(a['conta'])}</td>"
                      f"<td class='num'>{brl(a['orcado'])}</td><td class='num'>{brl(a['realizado'])}</td>"
                      f"<td class='num neg'>{a['variacao_pct']*100:+.1f}%</td></tr>" for a in b["achados"][:6])
    narrativa = html.escape(copiloto.narrar_offline(b)).replace("\n", "<br>")

    fx = res["fluxo_caixa"]
    dfc_resumo = (f"FCO {brl_c(fx['fco'])} · FCFF {brl_c(fx['fcff'])} · "
                  f"Δ Caixa {brl_c(fx['delta_caixa'])}")
    return _TEMPLATE.format(
        empresa=html.escape(b["empresa"]), setor=html.escape(b["setor"]), periodo=b["periodo"],
        mes=mes, ref=comp_bal, tiles=tiles, painel=_painel(res), grafico=_svg_ebitda(dre, mes),
        waterfall=_svg_waterfall(fx), dfc_resumo=dfc_resumo, margens=_svg_margens(dre),
        saas=_card_saas(saas_metrics) if saas_metrics else "",
        vertical=_vertical(dre, mes), achados=achados, narrativa=narrativa,
        materialidade=f"{materialidade*100:.0f}")


def _tile(rot, val, sub, estado=""):
    return (f'<div class="tile {estado}"><div class="tile-lab">{html.escape(rot)}</div>'
            f'<div class="tile-val">{html.escape(val)}</div><div class="tile-sub">{html.escape(sub)}</div></div>')


_TEMPLATE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório FP&A — {empresa}</title>
<style>
  :root {{
    --bg:#f5f7fa; --surface:#ffffff; --surface2:#fbfcfe; --ink:#16202e; --muted:#5b6b80;
    --border:#e4e9f0; --accent:#215f9a; --plan:#9aa8bb; --serie-b:#0d8a8a;
    --bom:#1f8a4c; --atencao:#c98a10; --critico:#c0392b; --crit-bg:#fbeceb;
    --shadow:0 1px 2px rgba(20,32,46,.04), 0 10px 28px rgba(20,32,46,.07);
  }}
  @media (prefers-color-scheme:dark){{ :root{{
    --bg:#0e1620; --surface:#172232; --surface2:#141d2b; --ink:#e7eef7; --muted:#93a3b8;
    --border:#25334a; --accent:#5ea0da; --plan:#5f7186; --serie-b:#43b5b5;
    --bom:#3fca77; --atencao:#e4b64e; --critico:#e2695a; --crit-bg:#2a1a19;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 12px 30px rgba(0,0,0,.4);
  }}}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",system-ui,sans-serif;line-height:1.5}}
  .wrap{{max-width:960px;margin:0 auto;padding:32px 20px 56px}}
  .eyebrow{{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}}
  h1{{font-size:1.7rem;margin:.3em 0 .1em}} .sub{{color:var(--muted);font-size:.95rem;margin-bottom:22px}}
  .tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:18px 0}}
  .tile{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:15px 17px;box-shadow:var(--shadow)}}
  .tile-lab{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
  .tile-val{{font-size:1.45rem;font-weight:700;margin:.12em 0;font-variant-numeric:tabular-nums}}
  .tile-sub{{font-size:.8rem;color:var(--muted)}}
  .tile.critico{{border-color:var(--critico);background:var(--crit-bg)}} .tile.critico .tile-val,.tile.ruim .tile-val{{color:var(--critico)}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px 22px;box-shadow:var(--shadow);margin:18px 0}}
  .card h2{{font-size:1.05rem;margin:0 0 4px}} .card .hint{{color:var(--muted);font-size:.82rem;margin:0 0 14px}}
  /* painel de indicadores */
  .indic-group{{margin-bottom:16px}} .indic-group:last-child{{margin-bottom:0}}
  .indic-group h3{{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 8px;font-weight:700}}
  .indic-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px}}
  .cell{{display:flex;align-items:center;gap:8px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;padding:9px 11px}}
  .cell .cl{{font-size:.82rem;color:var(--muted);flex:1}}
  .cell .cv{{font-size:.95rem;font-weight:700;font-variant-numeric:tabular-nums}}
  .dot{{width:9px;height:9px;border-radius:50%;background:var(--muted);flex:none}}
  .dot.bom{{background:var(--bom)}} .dot.atencao{{background:var(--atencao)}} .dot.critico{{background:var(--critico)}}
  .chart{{width:100%;height:auto}} .grid{{stroke:var(--border);stroke-width:1}}
  .ylab{{fill:var(--muted);font-size:11px;text-anchor:end}} .xlab{{fill:var(--muted);font-size:11px;text-anchor:middle}}
  .line-orc{{fill:none;stroke:var(--plan);stroke-width:2;stroke-dasharray:5 4}} .line-real{{fill:none;stroke:var(--accent);stroke-width:2.5}}
  .dot-real{{fill:var(--accent)}} .dot-crit{{fill:var(--critico);stroke:var(--surface);stroke-width:2}}
  .annot{{fill:var(--critico);font-size:11px;font-weight:700;text-anchor:middle}}
  .wf-up{{fill:var(--bom)}} .wf-down{{fill:var(--critico)}} .wf-sub{{fill:var(--accent)}} .wf-tot{{fill:var(--ink)}}
  .wf-lab{{fill:var(--muted);font-size:10.5px;text-anchor:middle}}
  .wf-val{{fill:var(--ink);font-size:10.5px;font-weight:700;text-anchor:middle;font-variant-numeric:tabular-nums}}
  .line-bruta{{fill:none;stroke:var(--serie-b);stroke-width:2;stroke-dasharray:5 4}}
  .lab-real{{fill:var(--accent);font-size:11px;font-weight:700}} .lab-bruta{{fill:var(--serie-b);font-size:11px;font-weight:700}}
  .legend{{display:flex;gap:16px;font-size:.8rem;color:var(--muted);margin-top:8px}} .legend span{{display:inline-flex;align-items:center;gap:6px}}
  .swatch{{width:15px;height:3px;border-radius:2px;display:inline-block}}
  table{{width:100%;border-collapse:collapse;font-size:.9rem}}
  th,td{{padding:8px 10px;border-bottom:1px solid var(--border);text-align:left}}
  th{{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}} td.neg{{color:var(--critico);font-weight:600;text-align:right}}
  .narr{{font-size:.94rem}}
  footer{{margin-top:22px;padding-top:16px;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem}}
  .selo{{display:inline-block;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.2em .7em;font-size:.72rem;color:var(--muted)}}
</style></head><body><div class="wrap">
  <div class="eyebrow">Oráculo · Copiloto de FP&amp;A</div>
  <h1>Relatório de Desempenho — {empresa}</h1>
  <div class="sub">{setor} · período {periodo} · mês crítico <b>{mes}</b> · indicadores em {ref}</div>

  <div class="tiles">{tiles}</div>

  <div class="card"><h2>Painel de indicadores</h2>
    <p class="hint">Semáforo: <span style="color:var(--bom)">●</span> bom · <span style="color:var(--atencao)">●</span> atenção · <span style="color:var(--critico)">●</span> crítico. (Ano 2025; balanço em {ref}.)</p>
    {painel}
  </div>

  {saas}

  <div class="card"><h2>EBITDA — Orçado vs Realizado</h2>
    <p class="hint">Linha cheia = realizado; tracejada = orçado; ponto vermelho = mês crítico.</p>
    {grafico}
    <div class="legend"><span><i class="swatch" style="background:var(--accent)"></i>Realizado</span>
      <span><i class="swatch" style="background:var(--plan)"></i>Orçado</span>
      <span><i class="swatch" style="background:var(--critico)"></i>Mês crítico</span></div>
  </div>

  <div class="card"><h2>Margens ao longo do ano</h2>
    <p class="hint">Margem bruta (tracejada) e margem EBITDA (cheia), realizado, como % da receita.</p>
    {margens}
  </div>

  <div class="card"><h2>Fluxo de Caixa (DFC — método indireto)</h2>
    <p class="hint">Do lucro líquido ao caixa: {dfc_resumo}. Barras verdes entram caixa, vermelhas saem; azuis são subtotais.</p>
    {waterfall}
  </div>

  <div class="card"><h2>Análise vertical — DRE do mês crítico ({mes})</h2>
    <p class="hint">Cada linha como % da Receita Líquida (realizado).</p>
    <table><thead><tr><th>Conta</th><th>Realizado</th><th>% da RL</th></tr></thead><tbody>{vertical}</tbody></table>
  </div>

  <div class="card"><h2>Achados — desvios materiais desfavoráveis</h2>
    <p class="hint">Somente desvios acima de {materialidade}% (materialidade).</p>
    <table><thead><tr><th>Competência</th><th>Conta</th><th>Orçado</th><th>Realizado</th><th>Desvio</th></tr></thead><tbody>{achados}</tbody></table>
  </div>

  <div class="card"><h2>Leitura do Oráculo</h2><p class="narr">{narrativa}</p></div>

  <footer><span class="selo">Números calculados por código · rastreáveis</span>
    &nbsp; Dados sintéticos para fins de portfólio. Não constitui recomendação de investimento.</footer>
</div></body></html>"""


def main():
    p = argparse.ArgumentParser(description="Dashboard rico do Oráculo")
    p.add_argument("dre"); p.add_argument("balanco")
    p.add_argument("--saas", default=None, help="CSV de dados SaaS (opcional)")
    p.add_argument("--saida", default=None); p.add_argument("--materialidade", type=float, default=0.05)
    a = p.parse_args()
    dre = motor.carregar_dre(a.dre); bal = motor.carregar_dre(a.balanco)
    sm = saas_mod.metricas(saas_mod.carregar(a.saas)) if a.saas else None
    doc = gerar_html(dre, bal, a.materialidade, saas_metrics=sm)
    saida = a.saida or f"exemplos/relatorio-{Path(a.dre).stem.replace('dre-','')}.html"
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    Path(saida).write_text(doc, encoding="utf-8")
    print(f"Relatório gerado: {saida}")


if __name__ == "__main__":
    main()
