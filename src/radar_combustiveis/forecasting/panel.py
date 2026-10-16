"""Séries semanais de mediana de preço em formato de matriz, mais as regras de elegibilidade.

Cada série é um par (localidade, produto); a localidade `ESTADO` é o agregado estadual. Semanas
sem dado ficam como NaN: nunca são preenchidas nem interpoladas (arquitetura, seção 14.5).
Tudo aqui é determinístico: a mesma entrada produz o mesmo painel e o mesmo `data_hash`.
"""

from dataclasses import dataclass
from datetime import timedelta
import hashlib

import numpy as np

STATE = "ESTADO"

# Elegibilidade inicial (arquitetura, seção 14.2). Os valores são o ponto de partida do documento.
MIN_WEEKS = 52              # semanas com dado, no histórico até a origem
MIN_SHARE = 0.80            # proporção de semanas com dado na janela recente
SHARE_WINDOW = 104          # a "janela" do critério de 80%: as últimas 104 semanas
MIN_MEDIAN_STATIONS = 3     # mediana de postos por semana (só municípios)
STATIONS_WINDOW = 26        # semanas usadas para essa mediana
RECENT_COVERAGE_WEEKS = 4   # sem cobertura baixa nas semanas mais recentes


@dataclass
class Panel:
    weeks: list        # calendário contínuo de domingos (date)
    keys: list         # [(localidade, produto)]
    y: np.ndarray      # (séries, semanas) mediana; NaN = sem dado
    stations: np.ndarray
    low: np.ndarray    # (séries, semanas) bool: cobertura baixa (sinalizada pela qualidade)

    def index_of(self, week):
        return (week - self.weeks[0]).days // 7

    @property
    def last(self):
        return len(self.weeks) - 1

    def is_state(self, s):
        return self.keys[s][0] == STATE


def load_rows(conn, uf):
    """Linhas semanais (municípios e estado) lidas do PostgreSQL já carregado."""
    cities = conn.execute("""
        SELECT m.week_start, l.municipality_name_normalized, p.canonical_name, m.price_median,
               m.station_count, m.quality_flag = 'cobertura_baixa'
        FROM mart_weekly_city_price m
        JOIN dim_location l USING (location_id) JOIN dim_product p USING (product_id)
        WHERE l.uf = %s AND p.active AND p.category = 'automotivo'""", (uf,)).fetchall()
    states = conn.execute("""
        SELECT m.week_start, %s, p.canonical_name, m.price_median, m.station_count, false
        FROM mart_weekly_state_price m JOIN dim_product p USING (product_id)
        WHERE m.uf = %s AND p.active AND p.category = 'automotivo'""", (STATE, uf)).fetchall()
    return [(w, loc, prod, float(med), int(n), bool(low)) for w, loc, prod, med, n, low in cities + states]


def build_panel(rows):
    if not rows:
        raise ValueError("Nenhuma linha semanal para montar o painel")
    first = min(r[0] for r in rows)
    last = max(r[0] for r in rows)
    weeks = [first + timedelta(weeks=i) for i in range((last - first).days // 7 + 1)]
    keys = sorted({(r[1], r[2]) for r in rows})
    position = {k: i for i, k in enumerate(keys)}
    shape = (len(keys), len(weeks))
    y, stations, low = np.full(shape, np.nan), np.full(shape, np.nan), np.zeros(shape, dtype=bool)
    for week, loc, prod, median, n, flag in rows:
        s, t = position[(loc, prod)], (week - first).days // 7
        y[s, t], stations[s, t], low[s, t] = median, n, flag
    return Panel(weeks, keys, y, stations, low)


def data_hash(rows):
    """SHA-256 das linhas em ordem canônica: identifica o conjunto de dados de um experimento."""
    digest = hashlib.sha256()
    for week, loc, prod, median, n, low in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
        digest.update(f"{week.isoformat()}|{loc}|{prod}|{median:.4f}|{n}|{int(low)}\n".encode("utf-8"))
    return digest.hexdigest()


def eligibility(panel, s, i):
    """(elegível, [motivos]) da série `s` com uma origem na semana `i`, usando só dados até `i`."""
    y = panel.y[s, : i + 1]
    seen = ~np.isnan(y)
    reasons = []
    if not seen[i]:
        reasons.append("sem_dado_na_semana_de_origem")
    if seen.sum() < MIN_WEEKS:
        reasons.append("menos_de_52_semanas_de_historico")
    window = seen[max(0, i + 1 - SHARE_WINDOW): i + 1]
    start = int(np.argmax(seen)) if seen.any() else i
    span = min(len(window), i + 1 - start)
    if span == 0 or window[-span:].mean() < MIN_SHARE:
        reasons.append("dados_em_menos_de_80pct_das_semanas")
    if not panel.is_state(s):
        recent = panel.stations[s, max(0, i + 1 - STATIONS_WINDOW): i + 1]
        recent = recent[~np.isnan(recent)]
        if recent.size == 0 or np.median(recent) < MIN_MEDIAN_STATIONS:
            reasons.append("mediana_de_postos_abaixo_de_3")
    if panel.low[s, max(0, i + 1 - RECENT_COVERAGE_WEEKS): i + 1].any():
        reasons.append("cobertura_baixa_recente")
    return not reasons, reasons
