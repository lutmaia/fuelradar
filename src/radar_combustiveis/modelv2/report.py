"""Resumos e relatórios da modelagem v2: validação (sem o teste) e final (teste lido uma vez)."""

import json

import numpy as np

from . import metrics
from .decision import brier, calibration_of, model_keys, primary
from .experiment import probabilities
from .spec import HORIZONS, INTERVAL_QUANTILES, LAYERS, MODELS, PRIMARY_HORIZON

NAMES = {"logistica": "logística multinomial", "lightgbm": "LightGBM"}


def best_per_layer(validation_table):
    """Melhor modelo de cada camada pelo BSS da validação (escolha pré-registrada para a ablação)."""
    return {layer: max((f"{layer}_{m}" for m in MODELS), key=lambda k: validation_table[k].get("estimate", -np.inf))
            for layer in LAYERS}


def class_summary(points, keys):
    out = {}
    h2 = points[points["horizon"] == PRIMARY_HORIZON]
    labels = h2["label"].to_numpy()
    for key in ["base"] + keys:
        p = probabilities(h2, key)
        out[key] = {"brier": float(brier(h2, key).mean()), "log_loss": metrics.log_loss(p, labels),
                    "balanced_accuracy": metrics.balanced_accuracy(p, labels), "ece": calibration_of(points, key)}
    persistence = np.tile([0.0, 1.0, 0.0], (len(h2), 1))
    out["persistencia"] = {"brier": float(metrics.brier_points(persistence, labels).mean()),
                           "balanced_accuracy": metrics.balanced_accuracy(persistence, labels)}
    out["class_shares"] = {c: float((labels == i).mean()) for i, c in enumerate(("queda", "estavel", "alta"))}
    return out


def validation_summary(points, selection, meta):
    return {"meta": meta, "points": int(len(points)), "origins": int(points["origin"].nunique()),
            "selection": selection, "best_per_layer": best_per_layer(selection["validation"]),
            "classes": class_summary(points, model_keys())}


def value_summary(points, layers=LAYERS, residual_pool=None):
    """MAE contra o último valor, Diebold–Mariano e cobertura do intervalo conformal (secundário)."""
    out = {}
    origins = points["origin"].to_numpy()
    actual = points["actual"].to_numpy()
    persistence = np.abs(points["last"].to_numpy() - actual)
    for layer in layers:
        pred = points[f"{layer}_valor"].to_numpy()
        err = np.abs(pred - actual)
        res = {"mae": float(err.mean()), "mae_persistencia": float(persistence.mean()),
               "skill": metrics.skill(err, persistence), "dm": metrics.diebold_mariano(origins, persistence, err)}
        if residual_pool is not None:
            lo, hi = _conformal(residual_pool, points, layer)
            inside = (actual >= pred + lo) & (actual <= pred + hi)
            res["interval_coverage"] = float(np.nanmean(np.where(np.isnan(lo), np.nan, inside)))
        out[layer] = res
    return out


def _conformal(pool, points, layer):
    """Quantis 10% e 90% dos resíduos da validação por produto e horizonte (sem eles, por horizonte)."""
    resid = pool["actual"] - pool[f"{layer}_valor"]
    q_lo, q_hi = INTERVAL_QUANTILES
    fine = resid.groupby([pool["product"], pool["horizon"]]).quantile([q_lo, q_hi]).unstack()
    coarse = resid.groupby(pool["horizon"]).quantile([q_lo, q_hi]).unstack()
    lo, hi = np.full(len(points), np.nan), np.full(len(points), np.nan)
    for k, (product, h) in enumerate(zip(points["product"], points["horizon"])):
        row = fine.loc[(product, h)] if (product, h) in fine.index else coarse.loc[h] if h in coarse.index else None
        if row is not None:
            lo[k], hi[k] = row[q_lo], row[q_hi]
    return lo, hi


def final_summary(test_points, valid_summary, decision, sensitivity, valid_points, reads, meta):
    keys = model_keys()
    best = valid_summary["best_per_layer"]
    origins = test_points[test_points["horizon"] == PRIMARY_HORIZON]["origin"].to_numpy()
    h2 = test_points[test_points["horizon"] == PRIMARY_HORIZON]
    base_loss = brier(h2, "base")
    secondary = {"L1_vs_L0": primary(test_points, best["L1"])}
    for prev, cur in (("L1", "L2"), ("L2", "L3")):
        secondary[f"{cur}_vs_{prev}"] = metrics.bootstrap_gain(origins, brier(h2, best[prev]), brier(h2, best[cur]),
                                                               base_loss)
    candidate = decision.get("candidate")
    if candidate:
        for h in HORIZONS:
            if h != PRIMARY_HORIZON:
                secondary[f"candidato_h{h}"] = primary(test_points, candidate, horizon=h)
        for tau, result in sensitivity.items():
            secondary[f"tau_{tau}"] = result
    values = value_summary(test_points, residual_pool=valid_points)
    for layer, res in values.items():
        if res["dm"].get("p") is not None:
            secondary[f"valor_{layer}_dm"] = {"estimate": res["skill"], "p": res["dm"]["p"]}
    adjusted = metrics.holm({k: v["p"] for k, v in secondary.items() if v.get("p") is not None})
    for k, p in adjusted.items():
        secondary[k]["p_holm"] = p
    reference_check = None
    if candidate:
        reference_check = {"vs_taxa_base_mensal": metrics.skill(brier(h2, candidate), base_loss),
                           "vs_taxa_base_produto": metrics.skill(brier(h2, candidate), brier(h2, "base_produto"))}
    return {"meta": meta, "points": int(len(test_points)), "origins": int(test_points["origin"].nunique()),
            "holdout_reads": reads, "candidate": candidate, "decision": decision, "reference_check": reference_check,
            "test": {k: primary(test_points, k) for k in keys}, "secondary": secondary,
            "classes": class_summary(test_points, keys), "values": values, "best_per_layer": best}


def _pct(v):
    return "—" if v is None else f"{v:+.3f}".replace(".", ",")


def _ci(r):
    return "—" if not r.get("n") and "ci" not in r else f"[{r['ci'][0]:+.3f} ; {r['ci'][1]:+.3f}]".replace(".", ",")


def _header(meta):
    return (f"- **Dados:** hash `{meta['data_hash'][:16]}…`, {meta['series']} séries, semanas de {meta['first_week']} "
            f"a {meta['last_week']}.\n- **Código:** `{meta.get('code_sha') or 'n/d'}` · **protocolo:** "
            f"`{meta.get('protocol_commit') or 'n/d'}` · semente {meta['seed']} · bootstrap B = {meta['bootstrap_reps']}.\n"
            "- Método e critérios: [protocolo da modelagem](../../docs/estudo/protocolo-modelagem.md).\n")


def validation_markdown(summary):
    sel, table = summary["selection"], summary["selection"]["validation"]
    lines = ["# Modelagem v2 — validação", "", _header(summary["meta"]),
             f"Validação: {summary['origins']} origens, {summary['points']} pontos (todos os horizontes). "
             "O teste final **não** foi lido.", "",
             "## Desfecho primário (h = 2): Brier skill contra a taxa-base", "",
             "| Camada | Modelo | BSS | IC 95% | Pontos |", "|---|---|---|---|---|"]
    for key in model_keys():
        layer, model = key.split("_", 1)
        r = table[key]
        lines.append(f"| {layer} | {NAMES[model]} | {_pct(r.get('estimate'))} | {_ci(r)} | {r.get('n', 0)} |")
    cls = summary["classes"]
    lines += ["", f"**Candidato:** {sel['candidate'] or 'nenhum (nenhum IC acima de zero)'}.", "",
              f"Classes em h = 2: queda {cls['class_shares']['queda']:.1%}, estável {cls['class_shares']['estavel']:.1%}, "
              f"alta {cls['class_shares']['alta']:.1%}. Brier da taxa-base {cls['base']['brier']:.4f}; da persistência "
              f"(sempre \"estável\") {cls['persistencia']['brier']:.4f}.", ""]
    return "\n".join(lines) + "\n"


def final_markdown(summary):
    d, cand = summary["decision"], summary["candidate"]
    lines = ["# Modelagem v2 — resultado final", "", _header(summary["meta"]),
             f"Teste final: {summary['origins']} origens, {summary['points']} pontos; lido "
             f"{len(summary['holdout_reads'])} vez(es) (registro em `holdout_access`).", "",
             "## Decisão", "",
             (f"Candidato escolhido na validação: **{cand}**. " if cand else "Nenhum candidato passou na validação. ")
             + ("**Aprovado**: as probabilidades passam a ser publicadas." if d.get("approved")
                else "**Não aprovado**: nada muda no produto."), ""]
    for check, ok in d.get("checks", {}).items():
        lines.append(f"- {'✅' if ok else '❌'} {check.replace('_', ' ')}")
    lines += ["", "## Todos os modelos no teste (h = 2)", "", "| Camada | Modelo | BSS | IC 95% |", "|---|---|---|---|"]
    for key in model_keys():
        layer, model = key.split("_", 1)
        r = summary["test"][key]
        lines.append(f"| {layer} | {NAMES[model]} | {_pct(r.get('estimate'))} | {_ci(r)} |")
    lines += ["", "## Secundários (Holm)", "", "| Medida | Estimativa | IC 95% | p (Holm) |", "|---|---|---|---|"]
    for name, r in summary["secondary"].items():
        p = r.get("p_holm")
        lines.append(f"| {name} | {_pct(r.get('estimate'))} | {_ci(r) if 'ci' in r else '—'} | "
                     f"{'—' if p is None else ('< 0,001' if p < 0.001 else f'{p:.3f}'.replace('.', ','))} |")
    check = summary.get("reference_check")
    if check:
        lines += ["", f"**Verificação da referência:** BSS do candidato {_pct(check['vs_taxa_base_mensal'])} contra a "
                      f"taxa-base por produto e mês e {_pct(check['vs_taxa_base_produto'])} contra a taxa-base só por "
                      "produto."]
    lines += ["", "## Valor (secundário): LightGBM de cada camada contra o último valor", "",
              "| Camada | MAE | MAE do último valor | Skill | Cobertura do intervalo de 80% |", "|---|---|---|---|---|"]
    for layer, r in summary["values"].items():
        cov = r.get("interval_coverage")
        lines.append(f"| {layer} | {r['mae']:.4f} | {r['mae_persistencia']:.4f} | {_pct(r['skill'])} | "
                     f"{'—' if cov is None else f'{cov:.1%}'} |".replace(".", ","))
    return "\n".join(lines) + "\n"


def dumps(obj):
    def default(v):
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, np.bool_):
            return bool(v)
        raise TypeError(type(v))
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=default)
