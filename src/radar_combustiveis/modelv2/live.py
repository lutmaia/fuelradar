"""Avaliação ao vivo (Marcos 10b e 11; docs/estudo/protocolo-ao-vivo.md).

O modelo do Marco 10 (L2 + LightGBM), calibrado por temperatura na validação, prevê toda semana a
classe da mudança. Cada previsão vai para um registro imutável antes de o valor real existir; quando
a semana-alvo é publicada, ela é pontuada. A decisão (experimental → oficial) só acontece com 26
origens vencidas em h = 2.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from ..forecasting.panel import eligibility
from . import calibration, metrics
from .experiment import _model_columns, probabilities, training_pairs
from .features import labels, size_of
from .models import BaseRate, LightGBMClass
from .spec import HORIZONS, MIN_GROUP_BSS, MIN_GROUP_POINTS, MIN_TRAIN_ROWS, PRIMARY_HORIZON, TAU

LAYER, MODEL = "L2", "lightgbm"
MODEL_KEY = f"{LAYER}_{MODEL}"
MODEL_NAME = "classe_l2_lightgbm_calibrado"
DECISION_ORIGINS = 26
ALERT_ORIGINS = 13
MAX_ECE = 0.05
LEDGER_COLUMNS = ["origin_week", "location", "product", "horizon", "target_week", "size", "last", "p0", "p1", "p2",
                  "base_p0", "base_p1", "base_p2", "temperature", "model"]


# -- Calibração --------------------------------------------------------------------------------


def fit_temperatures(valid_points):
    """Um T por horizonte, ajustado nas previsões da validação; e o erro de calibração antes e depois."""
    out = {}
    for h, part in valid_points.groupby("horizon"):
        raw = probabilities(part, MODEL_KEY)
        y = part["label"].to_numpy()
        t = calibration.fit(raw, y)
        out[int(h)] = {"temperature": t, "points": int(len(part)),
                       "ece_before": metrics.ece(raw, y), "ece_after": metrics.ece(calibration.apply(raw, t), y),
                       "log_loss_before": metrics.log_loss(raw, y),
                       "log_loss_after": metrics.log_loss(calibration.apply(raw, t), y)}
    return out


# -- Treino de produção e previsão da semana ---------------------------------------------------


def train(panel, features, cutoff=None, horizons=HORIZONS):
    """Um modelo e uma taxa-base por horizonte, com todos os pares de alvo conhecido no corte."""
    cutoff = panel.last if cutoff is None else cutoff
    cols, out = _model_columns(LAYER), {}
    for h in horizons:
        lab = labels(panel, h)
        ts, ti = training_pairs(lab, h, cutoff)
        if len(ts) < MIN_TRAIN_ROWS:
            continue
        frame = features.frame(LAYER, ts, ti, h)
        y = lab[ts, ti]
        out[h] = (LightGBMClass().fit(frame[cols], y), BaseRate().fit(frame["product"], frame["target_month"], y))
    return out


def predict(panel, features, models, temperatures, origin=None):
    """Previsões da origem (padrão: a semana mais recente) para as séries elegíveis."""
    origin = panel.last if origin is None else origin
    series = np.array([s for s in range(len(panel.keys)) if eligibility(panel, s, origin)[0]])
    frames = []
    for h, (model, base) in sorted(models.items()):
        if series.size == 0:
            continue
        origins = np.full(len(series), origin)
        frame = features.frame(LAYER, series, origins, h)
        t = temperatures[h]
        p = calibration.apply(model.predict(frame[_model_columns(LAYER)]), t)
        b = base.predict(frame["product"], frame["target_month"])
        frames.append(pd.DataFrame({
            "origin_week": panel.weeks[origin], "location": [panel.keys[s][0] for s in series],
            "product": [panel.keys[s][1] for s in series], "horizon": h,
            "target_week": panel.weeks[origin] + timedelta(weeks=h),
            "size": [size_of(panel, s, origin) for s in series], "last": panel.y[series, origin],
            "p0": p[:, 0], "p1": p[:, 1], "p2": p[:, 2], "base_p0": b[:, 0], "base_p1": b[:, 1], "base_p2": b[:, 2],
            "temperature": t, "model": MODEL_NAME}))
    return pd.concat(frames, ignore_index=True)[LEDGER_COLUMNS] if frames else pd.DataFrame(columns=LEDGER_COLUMNS)


# -- Registro imutável -------------------------------------------------------------------------


def ledger_text(frame):
    ordered = frame.sort_values(["horizon", "product", "location"], kind="stable")
    return ordered.to_csv(index=False, float_format="%.6f", lineterminator="\n")


def write_ledger(frame, directory, now=None):
    """Grava `<origem>.csv` e uma linha no manifesto. Se a origem já existe, nada muda (imutável)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    origin = frame["origin_week"].iloc[0]
    path = directory / f"{origin.isoformat()}.csv"
    if path.exists():
        return {"status": "existente", "path": path}
    data = ledger_text(frame).encode("utf-8")
    with open(path, "xb") as fh:
        fh.write(data)
    manifest = directory / "manifesto.csv"
    new = not manifest.exists()
    with open(manifest, "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write("origin_week,file,sha256,rows,created_at\n")
        stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        fh.write(f"{origin.isoformat()},{path.name},{hashlib.sha256(data).hexdigest()},{len(frame)},{stamp}\n")
    return {"status": "gravado", "path": path, "rows": len(frame)}


def read_ledgers(directory):
    files = sorted(Path(directory).glob("????-??-??.csv"))
    if not files:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    frame = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    for col in ("origin_week", "target_week"):
        frame[col] = pd.to_datetime(frame[col]).dt.date
    return frame


def check_manifest(directory):
    """Confere o SHA-256 de cada arquivo do registro contra o manifesto (arquivo alterado = erro)."""
    directory = Path(directory)
    manifest = directory / "manifesto.csv"
    if not manifest.exists():
        return []
    problems = []
    for row in pd.read_csv(manifest).itertuples():
        path = directory / row.file
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != row.sha256:
            problems.append(row.file)
    return problems


# -- Pontuação e placar -----------------------------------------------------------------------


def score(ledger, panel, tau=TAU):
    """Previsões vencidas (semana-alvo com mediana publicada), com a classe real."""
    if ledger.empty:
        return ledger.assign(label=pd.Series(dtype=int))
    position = {k: i for i, k in enumerate(panel.keys)}
    actual = []
    for row in ledger.itertuples():
        s = position.get((row.location, row.product))
        t = (row.target_week - panel.weeks[0]).days // 7
        value = panel.y[s, t] if s is not None and 0 <= t <= panel.last else np.nan
        actual.append(value)
    out = ledger.assign(actual=actual).dropna(subset=["actual"]).copy()
    delta = out["actual"] - out["last"]
    out["label"] = np.where(delta <= -tau + 1e-9, 0, np.where(delta >= tau - 1e-9, 2, 1))
    out["origin"] = [(w - panel.weeks[0]).days // 7 for w in out["origin_week"]]
    return out


def _bss(part, **bootstrap):
    model = metrics.brier_points(part[["p0", "p1", "p2"]].to_numpy(), part["label"].to_numpy())
    base = metrics.brier_points(part[["base_p0", "base_p1", "base_p2"]].to_numpy(), part["label"].to_numpy())
    return metrics.bootstrap_skill(part["origin"].to_numpy(), model, base, **bootstrap)


def scoreboard(scored, **bootstrap):
    """Placar por horizonte, alerta de degradação e a situação da decisão (seção 4)."""
    board = {"horizons": {}, "alert": None, "decision": {"status": "pendente", "origins_needed": DECISION_ORIGINS}}
    for h, part in scored.groupby("horizon"):
        board["horizons"][int(h)] = {
            "origins": int(part["origin"].nunique()), "points": int(len(part)), **_bss(part, **bootstrap),
            "ece": metrics.ece(part[["p0", "p1", "p2"]].to_numpy(), part["label"].to_numpy())}
    h2 = scored[scored["horizon"] == PRIMARY_HORIZON]
    origins = sorted(h2["origin"].unique())
    board["decision"]["origins_matured"] = len(origins)
    if len(origins) >= ALERT_ORIGINS:
        recent = h2[h2["origin"].isin(origins[-ALERT_ORIGINS:])]
        board["alert"] = {"bss_recent": _bss(recent, **bootstrap)["estimate"], "origins": ALERT_ORIGINS}
        board["alert"]["degraded"] = board["alert"]["bss_recent"] < 0
    if len(origins) >= DECISION_ORIGINS:
        board["decision"] = decide(decision_points(scored, origins[:DECISION_ORIGINS]), **bootstrap)
    return board


def decision_points(scored, chosen):
    """Os pontos da checagem única: as origens escolhidas, só com o que já estava conferido quando a última
    delas venceu em h = 2. Os horizontes mais longos dessas origens que vencem depois ficam fora, para a
    decisão não mudar nas semanas seguintes (protocolo ao vivo, seção 5, esclarecimento de 2026-10-16)."""
    h2 = scored[(scored["horizon"] == PRIMARY_HORIZON) & (scored["origin"] == chosen[-1])]
    cutoff = h2["target_week"].max()
    return scored[scored["origin"].isin(chosen) & (scored["target_week"] <= cutoff)]


def decide(scored, **bootstrap):
    h2 = scored[scored["horizon"] == PRIMARY_HORIZON]
    primary = _bss(h2, **bootstrap)
    ece = metrics.ece(h2[["p0", "p1", "p2"]].to_numpy(), h2["label"].to_numpy())
    groups = {}
    for column, frame in (("product", h2), ("size", h2), ("horizon", scored)):
        for value, part in frame.groupby(column):
            if len(part) >= MIN_GROUP_POINTS:
                groups[f"{column}:{value}"] = _bss(part, reps=200)["estimate"]
    checks = {"ganho_com_ic_acima_de_zero": primary["estimate"] > 0 and primary["ci"][0] > 0,
              "calibracao": ece <= MAX_ECE,
              "sem_piora_em_grupo": bool(groups) and all(v >= MIN_GROUP_BSS for v in groups.values())}
    return {"status": "oficial" if all(checks.values()) else "reprovado", "checks": checks, "primary": primary,
            "ece": ece, "groups": groups, "origins_used": int(scored["origin"].nunique())}
