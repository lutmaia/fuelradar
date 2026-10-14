"""Relatórios do estudo: JSON com todos os números (máquina), Markdown por pergunta (leitura) e
figuras em HTML do Plotly. O texto só descreve o que os números dizem e as regras do protocolo."""

from datetime import date
import json
import math

import numpy as np
import plotly.graph_objects as go

from ..dashboard.formatting import brand_label  # mesmo rótulo do painel (só formatação, sem Streamlit)
from .common import PRIMARY_PRODUCT, SECONDARY_PRODUCTS

PRODUCTS = (PRIMARY_PRODUCT,) + SECONDARY_PRODUCTS
LABEL = {"GASOLINA_COMUM": "Gasolina comum", "GASOLINA_ADITIVADA": "Gasolina aditivada",
         "ETANOL_HIDRATADO": "Etanol hidratado", "DIESEL_COMUM": "Diesel comum", "DIESEL_S10": "Diesel S10",
         "GNV": "GNV"}
ROBUST = {"vizinhanca_cep5": "Vizinhança (prefixo do CEP × semana)", "sem_preco_extremo": "Sem `preco_extremo`",
          "subperiodo_a": "Subperíodo A (2022-11 a 2024-06)", "subperiodo_b": "Subperíodo B (2024-07 a 2026-03)",
          "limiar_0_05": "Limiar de mudança R$ 0,05"}


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if not math.isfinite(value) else float(value)
    return value


def num(value, spec=".2f", suffix=""):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/d"
    return format(value, spec).replace(",", "_").replace(".", ",").replace("_", ".") + suffix


def hundred(x):
    return None if x is None else 100 * x


def integer(n):
    return f"{n:,}".replace(",", ".")


def ci(pair, spec=".2f", suffix=""):
    return f"[{num(pair[0], spec, suffix)} ; {num(pair[1], spec, suffix)}]"


def pval(p):
    if p is None or not math.isfinite(p):
        return "n/d"
    return "< 0,001" if p < 0.001 else num(p, ".3f")


def yes(flag):
    return "**sim**" if flag else "**não**"


def header(meta, title):
    h = meta["data_hashes"]
    return [f"# {title}", "",
            f"- **Janela:** semanas de {meta['window'][0]} a {meta['window'][1]} ({meta['weeks_with_data']} com dado); "
            "o teste final (2026-04-05 em diante) não foi lido.",
            f"- **Dados:** {integer(meta['observations'])} observações de {meta['uf']}; hash `{h['combined'][:16]}…` "
            f"(observações `{h['observations'][:12]}…`, municípios `{h['city'][:12]}…`, estado `{h['state'][:12]}…`).",
            f"- **Código:** `{meta['code_sha']}` · **protocolo:** `{meta['protocol_commit']}` · "
            f"semente {meta['seed']} · bootstrap B = {meta['bootstrap_reps']}.",
            "- Método e critérios: [protocolo](../../docs/estudo/protocolo.md), inclusive a tabela de desvios. "
            "Resultados são associações, não efeitos causais.", ""]


# -- Q1 -----------------------------------------------------------------------------------------


def q1_md(meta, r):
    p = r["primary"]
    lines = header(meta, "Q1 — Bandeira branca")
    lines += ["## Desfecho primário (gasolina comum)", "",
              f"No mesmo município e semana, postos de bandeira branca têm preço **{num(p['pct'])}%** em relação aos "
              f"bandeirados (IC 95% {ci(p['pct_ci'], suffix='%')}; p {pval(p['p'])}).",
              f"Amostra: {integer(p['n_obs'])} observações em {integer(p['n_cells'])} células município × semana com os "
              f"dois tipos de posto; {integer(p['n_clusters'])} postos (grupos do erro-padrão).", "",
              f"**Achado estável:** {yes(r['stable'])}.", "",
              "## Robustez", "", "| Checagem | Diferença | IC 95% | Observações |", "|---|---|---|---|"]
    for k, v in r["robustness"].items():
        lines.append(f"| {ROBUST[k]} | {num(v['pct'])}% | {ci(v['pct_ci'], suffix='%')} | {integer(v['n_obs'])} |")
    lines += ["", "## Secundários", "", "Outros produtos (Holm entre os cinco):", "",
              "| Produto | Diferença | IC 95% | p (Holm) | Observações |", "|---|---|---|---|---|"]
    for k, v in r["secondary"].items():
        lines.append(f"| {LABEL[k]} | {num(v['pct'])}% | {ci(v['pct_ci'], suffix='%')} | {pval(v.get('p_holm'))} | "
                     f"{integer(v['n_obs'])} |")
    lines += ["", "Maiores bandeiras contra a branca, gasolina comum (Holm entre as três):", "",
              "| Bandeira | Diferença contra a branca | IC 95% | p (Holm) |", "|---|---|---|---|"]
    for k, v in r["brands"].items():
        lines.append(f"| {brand_label(k)} | {num(v['pct'], '+.2f')}% | {ci(v['pct_ci'], suffix='%')} | {pval(v['p_holm'])} |")
    lines += ["", "## Limitações", "",
              "- A bandeira é a do cadastro atual; postos que trocaram de bandeira estão classificados pela de hoje.",
              "- Ser bandeira branca não é aleatório (localização, porte, público): a diferença é associação, não "
              "efeito da bandeira. Preço não diz nada sobre qualidade do combustível.",
              "- A ANP pesquisa uma amostra de postos; a robustez por prefixo do CEP usa só células com os dois tipos "
              "de posto no mesmo prefixo, uma amostra bem menor.",
              "- Conferência independente: o coeficiente foi recalculado em SQL, sem o código do estudo, como a média "
              "das diferenças dentro de cada célula ponderada por n_branca·n_bandeira/n, e coincidiu."]
    return lines


def q1_figure(r):
    names, values, lows, highs = [], [], [], []
    for k in PRODUCTS:
        v = r["primary"] if k == PRIMARY_PRODUCT else r["secondary"][k]
        if None in (v["pct"], *v["pct_ci"]):  # produto sem células comparáveis: fica fora da figura
            continue
        names.append(LABEL[k]), values.append(v["pct"]), lows.append(v["pct_ci"][0]), highs.append(v["pct_ci"][1])
    fig = go.Figure(go.Scatter(x=values, y=names, mode="markers", error_x=dict(
        type="data", symmetric=False, array=[h - v for h, v in zip(highs, values)],
        arrayminus=[v - lo for v, lo in zip(values, lows)])))
    fig.add_vline(x=0, line_dash="dot")
    fig.update_layout(title="Q1 — bandeira branca contra bandeirados, mesmo município e semana (IC 95%)",
                      xaxis_title="Diferença de preço (%)", yaxis=dict(autorange="reversed"), height=380)
    return fig


# -- Q2 -----------------------------------------------------------------------------------------


def q2_md(meta, r):
    p, d = r["primary"], r["descriptive"][PRIMARY_PRODUCT]
    lines = header(meta, "Q2 — Dinâmica do preço no posto")
    lines += ["## Desfecho primário (gasolina comum)", "",
              f"Mediana do tamanho das altas menos mediana do tamanho das quedas: **R$ {num(p['estimate'], '.3f')}/L** "
              f"(IC 95% por bootstrap em blocos de semanas {ci(p['ci'], '.3f')}).",
              f"Medianas: altas R$ {num(d['size_up']['median'], '.3f')}, quedas R$ {num(d['size_down']['median'], '.3f')}.",
              "", f"**Achado estável:** {yes(r['stable'])}.", "",
              "## Robustez (estimativa pontual)", "", "| Checagem | Assimetria (R$/L) |", "|---|---|"]
    for k, v in r["robustness"].items():
        lines.append(f"| {ROBUST[k]} | {num(v, '.3f')} |")
    lines += ["", "## Descritivo por produto", "", "Pares do mesmo posto em semanas consecutivas; mudança se |Δ| ≥ R$ 0,01.",
              "", "| Produto | Pares | Com mudança | Altas | Quedas | Alta mediana (P10–P90) | Queda mediana (P10–P90) "
              "| Duração mediana do preço |", "|---|---|---|---|---|---|---|---|"]
    for k in PRODUCTS:
        s, dur = r["descriptive"].get(k), r["durations"].get(k)
        if not s:
            continue
        up, down = s["size_up"], s["size_down"]
        lines.append(
            f"| {LABEL[k]} | {integer(s['pairs'])} | {num(hundred(s['frac_change']), '.1f')}% | {num(hundred(s['frac_up']), '.1f')}% | "
            f"{num(hundred(s['frac_down']), '.1f')}% | R$ {num(up['median'], '.2f')} ({num(up['p10'], '.2f')}–"
            f"{num(up['p90'], '.2f')}) | R$ {num(down['median'], '.2f')} ({num(down['p10'], '.2f')}–"
            f"{num(down['p90'], '.2f')}) | {num(dur['median_weeks'], '.0f')} semanas |")
    u, da = r["up_minus_down"], r["duration_asymmetry"]
    lines += ["", "## Secundários", "",
              f"- Fração de altas menos fração de quedas (gasolina comum): {num(hundred(u['estimate']), '.1f')} pontos "
              f"percentuais (IC 95% {ci([hundred(x) for x in u['ci']], '.1f')}).",
              f"- Duração mediana depois de uma alta: {num(da['median_after_up'], '.0f')} semanas; depois de uma queda: "
              f"{num(da['median_after_down'], '.0f')} semanas; log-rank p {pval(da['p_logrank'])} (as curvas diferem "
              "mesmo com a mesma mediana).", "",
              "| Produto (assimetria de tamanho) | Estimativa (R$/L) | IC 95% | p (Holm) |", "|---|---|---|---|"]
    for k, v in r["secondary"].items():
        lines.append(f"| {LABEL[k]} | {num(v['estimate'], '.3f')} | {ci(v['ci'], '.3f')} | {pval(v.get('p_holm'))} |")
    lines += ["", "## Limitações", "",
              "- Os preços mudam em degraus (muitas mudanças de exatamente R$ 0,10), então a **mediana** pula de um degrau "
              "para outro: o IC do desfecho primário encosta em zero e o subperíodo B tem assimetria zero. É uma "
              "limitação da medida escolhida no protocolo; trocar de medida agora seria escolher depois de ver os "
              "dados, e fica registrado como sugestão para um estudo futuro pré-registrado.",
              "- Sem proxy de custo, nada aqui testa \"sobe como foguete, cai como pena\"; em período de alta, altas "
              "mais frequentes são esperadas.",
              "- Só entram pares em semanas consecutivas; postos observados de forma intermitente contam menos.",
              "- Conferência independente: pares, altas, quedas e medianas de gasolina comum foram recalculados em SQL "
              "e coincidiram."]
    return lines


def q2_figure(r):
    names = [LABEL[k] for k in PRODUCTS if k in r["descriptive"]]
    fig = go.Figure()
    for key, label in (("frac_up", "Altas"), ("frac_down", "Quedas")):
        fig.add_bar(name=label, x=names, y=[hundred(r["descriptive"][k][key]) for k in PRODUCTS if k in r["descriptive"]])
    fig.update_layout(title="Q2 — fração de semanas com alta e com queda no mesmo posto", barmode="group",
                      yaxis_title="% dos pares de semanas consecutivas", height=380)
    return fig


# -- Q3 -----------------------------------------------------------------------------------------


def q3_md(meta, r):
    p = r["primary"]
    lines = header(meta, "Q3 — Difusão entre municípios")
    lines += [f"Líderes (grandes): {', '.join(r['leaders'])}. Seguidores (médios): {len(r['followers'])} municípios.", "",
              "## Desfecho primário (gasolina comum)", "",
              "Fração de seguidores em que as variações dos líderes nas duas semanas anteriores melhoram a previsão da "
              "variação do seguidor (teste F, Holm a 5%), e o controle reverso:", "",
              "| Janela | Seguidores testáveis | Líderes → seguidor | Seguidor → líderes (controle) |", "|---|---|---|---|",
              f"| Janela inteira | {p['testable']} | {num(hundred(p['share_forward']), '.1f')}% | "
              f"{num(hundred(p['share_reverse']), '.1f')}% |"]
    for k, v in r["subperiods"].items():
        lines.append(f"| {ROBUST[k]} | {v['testable']} | {num(hundred(v['share_forward']), '.1f')}% | "
                     f"{num(hundred(v['share_reverse']), '.1f')}% |")
    lines += ["", "Critério de estabilidade: ao menos 25% na janela inteira e mais que o controle reverso na janela "
              "inteira e em cada subperíodo.", "", f"**Achado estável:** {yes(r['stable'])}.", ""]
    ev, df = r["events"], r["diffusion"]
    lags = {}
    for v in r["cross_correlation"].values():
        lags[v["best_lag"]] = lags.get(v["best_lag"], 0) + 1
    lines += ["## Secundários", "",
              f"**Tempo até acompanhar eventos estaduais:** {ev['count']} eventos ({ev['up']} altas com limiar "
              f"R$ {num(ev['threshold_up'])}, {ev['down']} quedas com limiar R$ {num(ev['threshold_down'])}"
              + ("; as quedas usaram o limiar reserva de R$ 0,05 por terem menos de 5 eventos a R$ 0,10" if
                 ev["threshold_down"] < 0.1 else "") + ").", "",
              "| Grupo | Casos | Acompanharam em até 8 semanas | Semanas até acompanhar (mediana) |", "|---|---|---|---|"]
    for k, label in (("grande", "Grandes"), ("medio", "Médios"), ("alta", "Eventos de alta"), ("queda", "Eventos de queda")):
        v = df[k]
        lines.append(f"| {label} | {integer(v['cases'])} | {integer(v['followed'])} | {num(v['median_weeks'], '.0f')} |")
    lines += ["", f"Grandes × médios, log-rank p {pval(df['p_logrank_porte'])}. Com outros limiares de evento: "
              + "; ".join(f"R$ {k.split('_')[1].replace('.', ',')}: {v['events']} eventos, mediana grandes "
                          f"{num(v['grande']['median_weeks'], '.0f')} e médios {num(v['medio']['median_weeks'], '.0f')} "
                          f"semanas, log-rank p {pval(v['p_logrank_porte'])}"
                          for k, v in r["diffusion_robustness"].items()) + ".", "",
              "**Defasagem de maior correlação** entre a variação de cada seguidor e a dos líderes (positiva = líderes "
              "antes): " + ", ".join(f"{k} semana(s): {n}" for k, n in sorted(lags.items(), key=lambda x: (x[0] is None, x[0])))
              + ".", "",
              f"**Etanol hidratado** (repetição do primário): líderes → seguidor {num(hundred(r['ethanol']['share_forward']), '.1f')}%, "
              f"controle {num(hundred(r['ethanol']['share_reverse']), '.1f')}% de {r['ethanol']['testable']} testáveis.", "",
              "## Limitações", "",
              "- Precedência temporal não é causa: um choque comum que aparece antes nos grandes produz o mesmo padrão.",
              "- A semana é a menor resolução; a maioria dos municípios tem a maior correlação na **mesma** semana dos "
              "líderes, o que é compatível com movimentos simultâneos ou mais rápidos que uma semana.",
              "- O subperíodo A tem 65 das 86 semanas com dado (lacunas de publicação da ANP em 2022–2023); com duas "
              "defasagens, cada lacuna remove até três semanas do teste, o que reduz o poder ali.",
              "- A mediana de um município médio oscila com a amostra de postos da semana."]
    return lines


def q3_figure(r):
    lags = {}
    for v in r["cross_correlation"].values():
        if v["best_lag"] is not None:
            lags[v["best_lag"]] = lags.get(v["best_lag"], 0) + 1
    xs = list(range(-4, 5))
    fig = go.Figure(go.Bar(x=xs, y=[lags.get(x, 0) for x in xs]))
    fig.update_layout(title="Q3 — defasagem de maior correlação com os líderes, por seguidor",
                      xaxis_title="Semanas (positivo = líderes antes)", yaxis_title="Municípios", height=380)
    return fig


# -- Resumo -------------------------------------------------------------------------------------


def summary_md(meta, results, verdict):
    q1, q2, q3 = results["q1"]["primary"], results["q2"]["primary"], results["q3"]["primary"]
    lines = header(meta, "Estudo exploratório — resumo (Q1 a Q3)")
    lines += ["| Pergunta | Desfecho primário (gasolina comum) | Resultado | Achado estável |", "|---|---|---|---|",
              f"| [Q1 — bandeira branca](q1.md) | diferença da branca contra bandeirados, mesmo município e semana | "
              f"{num(q1['pct'])}% {ci(q1['pct_ci'], suffix='%')} | {yes(results['q1']['stable'])} |",
              f"| [Q2 — dinâmica](q2.md) | mediana das altas − mediana das quedas | R$ {num(q2['estimate'], '.3f')} "
              f"{ci(q2['ci'], '.3f')} | {yes(results['q2']['stable'])} |",
              f"| [Q3 — difusão](q3.md) | seguidores com precedência dos líderes (controle reverso) | "
              f"{num(hundred(q3['share_forward']), '.1f')}% ({num(hundred(q3['share_reverse']), '.1f')}%) | "
              f"{yes(results['q3']['stable'])} |", "",
              f"## Gate G1: {'passou' if verdict['passed'] else 'não passou'}", "",
              f"Achados estáveis: {', '.join(s.upper() for s in verdict['stable']) or 'nenhum'} "
              f"({len(verdict['stable'])} de 3; o protocolo exige {verdict['required']}).",
              "Pelo protocolo, o resultado é publicado como está e o escopo da modelagem (Marco 10) é reavaliado com o "
              "usuário antes de seguir; nada foi refeito para passar." if not verdict["passed"] else
              "Pelo protocolo, a modelagem (Marco 10) segue como desenhada.", "",
              "Figuras: [Q1](q1.html), [Q2](q2.html), [Q3](q3.html). Todos os números: [resultados.json](resultados.json)."]
    return lines


def write_reports(meta, results, verdict, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    data = jsonable(dict(meta=meta, g1=verdict, **results))
    meta, results = data["meta"], {k: data[k] for k in ("q1", "q2", "q3")}
    paths = [out_dir / "resultados.json"]
    paths[0].write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, lines in (("resumo.md", summary_md(meta, results, verdict)), ("q1.md", q1_md(meta, results["q1"])),
                        ("q2.md", q2_md(meta, results["q2"])), ("q3.md", q3_md(meta, results["q3"]))):
        path = out_dir / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    for name, figure in (("q1.html", q1_figure), ("q2.html", q2_figure), ("q3.html", q3_figure)):
        path = out_dir / name
        figure(results[name[:2]]).write_html(path, include_plotlyjs="cdn", full_html=True)
        paths.append(path)
    return paths
