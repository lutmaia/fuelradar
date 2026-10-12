"""Relatório reproduzível do backtest: JSON (máquina) e Markdown (leitura)."""

import json
from pathlib import Path

from .models import BASELINES, CANDIDATE

LABELS = {"ultimo_valor": "Último valor", "media_movel_4": "Média móvel de 4 semanas",
          "mesma_semana_ano_anterior": "Mesma semana do ano anterior", CANDIDATE: "LightGBM global (candidato)"}
CHECKS = {
    "melhora_minima_de_5pct_no_mae_ponderado": "melhora de pelo menos 5% no MAE ponderado contra o melhor baseline",
    "sem_regressao_grave_em_grupo": "sem piora grave em produto, nível, horizonte ou porte de município",
    "vies_aceitavel": "viés médio de até 25% do MAE",
    "cobertura_do_intervalo_na_faixa": "cobertura do intervalo de 80% entre 70% e 90%",
    "reprodutivel": "mesmos dados e semente geram previsões idênticas",
    "candidato_avaliado": "candidato com previsões avaliadas",
}


def _fmt(value, spec):
    return "n/d" if value is None else format(value, spec)


def _row(name, s):
    if not s.get("n"):
        return f"| {LABELS[name]} | n/d | n/d | n/d | n/d | n/d | n/d | n/d |"
    return (f"| {LABELS[name]} | {_fmt(s['mae'], '.4f')} | {_fmt(s['wmae'], '.4f')} | {_fmt(s['wape'], '.2%')} | "
            f"{_fmt(s['mase'], '.2f')} | {_fmt(s['bias'], '+.4f')} | {_fmt(s['coverage'], '.1%')} | "
            f"{_fmt(s['interval_width'], '.3f')} |")


def markdown(result):
    summary, decision = result["summary"], result["decision"]
    overall = summary["overall"]
    lines = [
        "# Relatório do backtest (Marco 7)", "",
        f"- **Origem das previsões:** semana de {result['origin_week']:%d/%m/%Y}",
        f"- **Dados:** hash `{result['data_hash'][:16]}…`, {result['uf_rows']} linhas semanais, {result['series']} séries",
        f"- **Código:** `{result['code_sha']}`",
        f"- **Backtest:** {len(result['backtest_origins'])} origens planejadas a cada {result['step']} semanas, "
        f"{len(summary['origins'])} com séries elegíveis; as {result['burn_in']} primeiras só calibram intervalos e "
        f"{len(summary['evaluated_origins'])} são avaliadas. {summary['points']} previsões avaliadas, todas em "
        f"pontos comuns aos quatro modelos",
        "", "## Resultado geral", "",
        "| Modelo | MAE (R$/L) | MAE pond. | WAPE | MASE | Viés | Cobertura 80% | Largura |",
        "|---|---|---|---|---|---|---|---|",
        *[_row(m, overall[m]) for m in (*BASELINES, CANDIDATE)],
        "", "MAE ponderado: pesa cada previsão pelo número de postos da semana prevista. "
        "Viés = previsão − observado (negativo: subestima).", "",
        "## Decisão", "",
        f"**{'Candidato aprovado' if decision['approved'] else 'Candidato NÃO aprovado — o baseline permanece publicado'}.** "
        f"Melhor baseline: {LABELS[decision['best_baseline']]}. "
        f"Variação do MAE ponderado do candidato contra ele: "
        f"{'n/d' if decision['improvement'] is None else f'{-decision['improvement']:+.1%}'} "
        "(negativo = candidato melhor).", "",
        *[f"- [{'x' if ok else ' '}] {CHECKS.get(name, name)}" for name, ok in decision["checks"].items()],
    ]
    if decision.get("regressions"):
        lines += ["", "Grupos em que o candidato piorou mais de 5% contra o melhor baseline: "
                  + ", ".join(decision["regressions"])]
    lines += ["", f"**Modelo publicado:** {LABELS[result['published_model']]}.", "",
              "## Por horizonte (MAE ponderado)", "", "| Horizonte | " + " | ".join(LABELS[m] for m in (*BASELINES, CANDIDATE)) + " |",
              "|---|" + "---|" * 4]
    for h, scores in sorted(summary["by_horizon"].items()):
        lines.append(f"| {h} semana(s) | " + " | ".join(_fmt(scores[m].get('wmae'), '.4f') for m in (*BASELINES, CANDIDATE)) + " |")
    lines += ["", "## Por produto (MAE ponderado)", "",
              "| Produto | " + " | ".join(LABELS[m] for m in (*BASELINES, CANDIDATE)) + " |", "|---|" + "---|" * 4]
    for product, scores in sorted(summary["by_product"].items()):
        lines.append(f"| {product} | " + " | ".join(_fmt(scores[m].get('wmae'), '.4f') for m in (*BASELINES, CANDIDATE)) + " |")
    lines += ["", "## Por nível geográfico e porte do município (MAE ponderado)", "",
              "| Grupo | " + " | ".join(LABELS[m] for m in (*BASELINES, CANDIDATE)) + " |", "|---|" + "---|" * 4]
    for part in ("by_level", "by_group"):
        for key, scores in sorted(summary[part].items()):
            if part == "by_group" and key == "estado":
                continue  # já aparece em "por nível"
            lines.append(f"| {key} | " + " | ".join(_fmt(scores[m].get('wmae'), '.4f') for m in (*BASELINES, CANDIDATE)) + " |")
    eligible = sum(e["eligible"] for e in result["eligibility"])
    lines += ["", "## Publicação", "",
              f"- Séries elegíveis na origem: {eligible} de {len(result['eligibility'])}",
              f"- Previsões gravadas: {len(result['forecasts'])} ({len(result['forecasts']) // 4} séries × 4 horizontes)",
              f"- Variações incomuns nas últimas semanas: {len(result['anomalies'])}", "",
              "Reprodutibilidade verificada: " + ("sim, duas execuções de treino idênticas." if result["reproducible"]
                                                  else "NÃO: as execuções divergiram.")]
    return "\n".join(lines) + "\n"


def write_reports(result, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {k: result[k] for k in ("data_hash", "code_sha", "origin_week", "first_week", "series", "step",
                                      "burn_in", "decision", "published_model", "reproducible", "parameters")}
    payload["backtest_origins"] = result["backtest_origins"]
    payload["summary"] = result["summary"]
    payload["eligible_series"] = sum(e["eligible"] for e in result["eligibility"])
    payload["forecast_rows"] = len(result["forecasts"])
    payload["anomaly_rows"] = len(result["anomalies"])
    json_path, md_path = directory / "backtest.json", directory / "backtest.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
                         encoding="utf-8")
    md_path.write_text(markdown(result), encoding="utf-8")
    return [json_path, md_path]
