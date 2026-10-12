"""Gráficos Plotly do painel. Funções puras: recebem os pontos da API e devolvem uma figura.

Cores da paleta Okabe-Ito (distinguíveis por daltônicos); a cobertura baixa também muda o símbolo,
para não depender só de cor. Semanas sem dado viram lacunas, nunca valores preenchidos.
"""

from datetime import date, timedelta

import plotly.graph_objects as go

PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
STATE_COLOR = "#555555"
LOW_COLOR = "#D55E00"


def weekly_axis(points):
    """Pontos indexados por semana e a lista contínua de semanas, para as lacunas aparecerem."""
    by_week = {p["week_start"]: p for p in points}
    if not by_week:
        return by_week, []
    first, last = date.fromisoformat(min(by_week)), date.fromisoformat(max(by_week))
    weeks, day = [], first
    while day <= last:
        weeks.append(day.isoformat())
        day += timedelta(days=7)
    return by_week, weeks


def _series(points, key):
    by_week, weeks = weekly_axis(points)
    values = [None if by_week.get(w) is None else by_week[w]["statistics"][key] for w in weeks]
    return weeks, values, by_week


def _layout(fig, title, y_title):
    fig.update_layout(
        title=title, margin={"l": 10, "r": 10, "t": 50, "b": 90}, hovermode="x unified",
        yaxis={"title": y_title, "tickformat": ",.2f"}, xaxis={"title": "Início da semana"},
        # Legenda abaixo do gráfico: acima ela se sobrepunha ao título.
        legend={"orientation": "h", "yanchor": "top", "y": -0.25, "xanchor": "left", "x": 0},
        separators=",.")
    return fig


def brand_figure(items, reference, unit):
    """Mediana por bandeira (ponto) com a faixa do menor ao maior preço, e a mediana geral como referência.

    Pontos, não barras: o eixo não começa em zero e barras cortadas exagerariam as diferenças."""
    ordered = sorted(items, key=lambda i: i["median"], reverse=True)
    fig = go.Figure(go.Scatter(
        x=[i["median"] for i in ordered], y=[f"{i['brand']} ({i['stations']} postos)" for i in ordered],
        mode="markers", marker={"size": 13, "color": [PALETTE[0] if i["median"] <= reference else PALETTE[1]
                                                      for i in ordered]},
        error_x={"type": "data", "symmetric": False, "color": "#888888", "thickness": 2,
                 "array": [i["max"] - i["median"] for i in ordered],
                 "arrayminus": [i["median"] - i["min"] for i in ordered]},
        customdata=[[i["min"], i["max"]] for i in ordered], name="Mediana",
        hovertemplate="%{y}<br>mediana R$ %{x:.2f} (de %{customdata[0]:.2f} a %{customdata[1]:.2f})<extra></extra>"))
    if reference is not None:
        fig.add_vline(x=reference, line_dash="dash", line_color=STATE_COLOR,
                      annotation_text=f"todos: R$ {reference:.2f}".replace(".", ","), annotation_position="top")
    fig.update_layout(title="Mediana por bandeira (a linha cinza de cada ponto vai do menor ao maior preço)",
                      margin={"l": 10, "r": 10, "t": 60, "b": 40}, showlegend=False,
                      xaxis={"title": unit, "tickformat": ",.2f"}, height=140 + 40 * len(ordered), separators=",.")
    return fig


def forecast_figure(history, forecast, label, unit, level):
    """Histórico recente (mediana) e previsão central com a faixa do intervalo, em semanas à frente."""
    weeks, median, _ = _series(history, "median")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=weeks, y=median, mode="lines+markers", name=f"{label} — observado",
                             line={"color": PALETTE[0], "width": 2}, marker={"size": 5}, connectgaps=False,
                             hovertemplate="%{x}<br>R$ %{y:.2f}<extra>observado</extra>"))
    if forecast and weeks:
        last_week = next((w for w, v in zip(reversed(weeks), reversed(median)) if v is not None), None)
        last_value = next((v for v in reversed(median) if v is not None), None)
        xs = [p["target_week_start"] for p in forecast]
        # A faixa parte do último valor observado: ele não tem incerteza.
        fig.add_trace(go.Scatter(x=[last_week, *xs], y=[last_value, *[p["upper"] for p in forecast]], mode="lines",
                                 line={"width": 0}, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[last_week, *xs], y=[last_value, *[p["lower"] for p in forecast]], mode="lines",
                                 line={"width": 0}, fill="tonexty", fillcolor="rgba(230,159,0,0.25)",
                                 name=f"Intervalo de {level:.0%}", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[last_week, *xs], y=[last_value, *[p["point"] for p in forecast]],
                                 mode="lines+markers", name="Previsão", line={"color": PALETTE[1], "dash": "dash"},
                                 marker={"size": 7, "symbol": "diamond"},
                                 customdata=[[None, None]] + [[p["lower"], p["upper"]] for p in forecast],
                                 hovertemplate="%{x}<br>R$ %{y:.2f} (faixa %{customdata[0]:.2f} a "
                                               "%{customdata[1]:.2f})<extra>previsão</extra>"))
    return _layout(fig, f"{label}: observado e previsão", unit)


def history_figure(points, label, unit, state_points=None):
    """Mediana semanal com a faixa entre p25 e p75; a mediana do estado como referência."""
    weeks, median, by_week = _series(points, "median")
    _, p25, _ = _series(points, "p25")
    _, p75, _ = _series(points, "p75")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=weeks, y=p75, mode="lines", line={"width": 0}, hoverinfo="skip",
                             showlegend=False, connectgaps=False))
    fig.add_trace(go.Scatter(x=weeks, y=p25, mode="lines", line={"width": 0}, fill="tonexty",
                             fillcolor="rgba(0,114,178,0.15)", name="Faixa entre p25 e p75", hoverinfo="skip",
                             connectgaps=False))
    details = []
    for week in weeks:
        point = by_week.get(week)
        details.append("sem dados" if point is None else
                       f"{point['sample']['stations']} postos · {point['sample']['observations']} observações")
    fig.add_trace(go.Scatter(
        x=weeks, y=median, mode="lines+markers", name=f"Mediana — {label}", line={"color": PALETTE[0], "width": 3},
        marker={"size": 6}, customdata=details, connectgaps=False,
        hovertemplate="%{y:,.2f} — %{customdata}<extra>Mediana</extra>"))
    low = [w for w in weeks if by_week.get(w) and by_week[w]["sample"]["coverage_status"] == "low"]
    if low:
        fig.add_trace(go.Scatter(
            x=low, y=[by_week[w]["statistics"]["median"] for w in low], mode="markers",
            name="Cobertura baixa", marker={"symbol": "x", "size": 11, "color": LOW_COLOR, "line": {"width": 2}},
            hovertemplate="Cobertura baixa nesta semana<extra></extra>"))
    if state_points:
        s_weeks, s_median, _ = _series(state_points, "median")
        fig.add_trace(go.Scatter(x=s_weeks, y=s_median, mode="lines", name="Mediana — estado de SP",
                                 line={"color": STATE_COLOR, "width": 2, "dash": "dash"}, connectgaps=False,
                                 hovertemplate="%{y:,.2f}<extra>Estado</extra>"))
    return _layout(fig, f"{label}: preço semanal", unit)


def comparison_figures(series, unit):
    """(valores absolutos, índice base 100, semana-base) para até 5 municípios. `series`: {nome: pontos}.

    O índice usa a primeira semana em que todos os municípios têm dados; sem semana comum, o
    gráfico normalizado fica sem linhas (a página explica)."""
    absolute, normalized = go.Figure(), go.Figure()
    common = None
    for points in series.values():
        weeks = {p["week_start"] for p in points if p["statistics"]["median"] is not None}
        common = weeks if common is None else common & weeks
    base_week = min(common) if common else None
    for i, (name, points) in enumerate(series.items()):
        color = PALETTE[i % len(PALETTE)]
        weeks, median, _ = _series(points, "median")
        absolute.add_trace(go.Scatter(
            x=weeks, y=median, mode="lines+markers", name=name, connectgaps=False,
            line={"color": color, "width": 2}, hovertemplate="%{y:,.2f}<extra>%{fullData.name}</extra>"))
        base = next((p["statistics"]["median"] for p in points if p["week_start"] == base_week), None)
        if base:
            normalized.add_trace(go.Scatter(
                x=weeks, y=[None if v is None else v / base * 100 for v in median], mode="lines+markers", name=name,
                connectgaps=False, line={"color": color, "width": 2},
                hovertemplate="%{y:,.1f}<extra>%{fullData.name}</extra>"))
    _layout(absolute, "Mediana semanal (valores absolutos)", unit)
    _layout(normalized, "Mediana semanal (índice, primeira semana comum = 100)", "Índice")
    normalized.update_layout(yaxis={"title": "Índice", "tickformat": ",.1f"})
    return absolute, normalized, base_week
