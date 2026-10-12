"""Páginas do painel (arquitetura, seção 16). Cada página é uma função sem argumentos de dados.

Toda informação vem da API por `fetch`, com cache curto. O painel não calcula preços: formata,
destaca limites (cobertura, amostra, datas) e desenha. Previsões e variações incomuns entram no
Marco 7; não há página nem texto que as simule.
"""

from datetime import date, timedelta

import streamlit as st

from . import charts, exports, formatting as fmt, tables
from .client import ApiClient, ApiError, ApiUnavailable

DEFAULT_PRODUCT = "GASOLINA_COMUM"
STALE_AFTER_DAYS = 14
WINDOWS = {"12 semanas": 12, "26 semanas": 26, "52 semanas": 52, "3 anos (máximo)": 156}
FEATURED = ["SAO PAULO", "CAMPINAS", "SANTOS", "GUARULHOS", "RIBEIRAO PRETO", "SOROCABA",
            "SAO JOSE DOS CAMPOS", "SAO BERNARDO DO CAMPO", "SANTO ANDRE", "OSASCO"]
SURVEY_NOTICE = (
    "Os preços vêm da **pesquisa semanal da ANP**: uma amostra de postos, não preços em tempo real "
    "nem todos os postos do município. O valor pode ter mudado depois da coleta. "
    "Municípios sem dado não indicam ausência de postos.")


# -- Acesso à API ---------------------------------------------------------------------------


def make_client():
    return ApiClient.from_env()


@st.cache_resource
def _api():
    return make_client()


@st.cache_data(ttl=120, show_spinner=False)
def fetch(method, *args):
    """Uma consulta da API, em cache por 2 minutos. Os dados mudam no máximo uma vez por semana."""
    return getattr(_api(), method)(*args)


def api_base_url():
    return _api().base_url


def guarded(page):
    """Mostra falhas da API de forma legível em vez de uma pilha de erro."""
    def run():
        try:
            page()
        except ApiUnavailable as exc:
            st.error(f"**Não foi possível consultar a API.** {exc} Verifique se ela está no ar "
                     "(`scripts/run_api.py`) e se `RADAR_API_URL` aponta para ela.")
        except ApiError as exc:
            st.error(f"**A API recusou a consulta:** {exc.message}")
            st.caption(f"Código: {exc.code} · request_id: {exc.request_id or 'n/d'}")
    run.__name__ = page.__name__
    return run


# -- Auxiliares de tela ---------------------------------------------------------------------


def pick(label, options, key, default=None, format_func=str, help=None):
    """Seleção que lembra o valor na URL (`?municipio=...&produto=...`), para compartilhar."""
    wanted = st.query_params.get(key)
    chosen = wanted if wanted in options else default if default in options else options[0]
    value = st.selectbox(label, options, index=options.index(chosen), format_func=format_func, help=help)
    st.query_params[key] = value
    return value


def product_labels():
    products = fetch("products")
    return {p["code"]: p["label"] for p in products}, {p["code"]: p["unit"] for p in products}


def window_start(latest_week, label):
    return (date.fromisoformat(latest_week) - timedelta(weeks=WINDOWS[label] - 1)).isoformat()


def freshness_caption(body):
    st.caption(f"Fonte: ANP · última coleta usada em **{fmt.date_br(body['data_as_of'])}** · "
               f"arquivo baixado em **{fmt.retrieved_text(body['source_retrieved_at'])}**.")


def coverage_notice(sample):
    status = sample["coverage_status"]
    if status == "low":
        ratio = sample.get("coverage_ratio")
        detail = f" ({fmt.percent(ratio, 0, signed=False)} da mediana das 8 semanas anteriores)" if ratio is not None else ""
        st.warning(f"**Cobertura baixa nesta semana**{detail}: poucos postos pesquisados. "
                   "A mediana pode não representar o município e a variação semanal não é calculada.")
    elif status == "no_history":
        st.info("**Sem histórico para comparar:** a série tem menos de 8 semanas anteriores, então a "
                "cobertura não pôde ser avaliada.")


def show_table(rows, formats=None, na_rep=None):
    """Tabela com valores tipados: clicar no cabeçalho ordena por data ou número, não por texto."""
    st.dataframe(tables.styled(rows, formats, na_rep), hide_index=True, width="stretch")


# -- Início ---------------------------------------------------------------------------------


def home(shortcut_page=None):
    st.title("Radar de Combustíveis — São Paulo")
    st.markdown("Preços de revenda pesquisados pela ANP em municípios paulistas, com a fonte, as datas e "
                "o tamanho da amostra sempre à vista.")
    st.info(SURVEY_NOTICE)

    fresh = fetch("freshness")
    labels, units = product_labels()
    quality = fetch("data_quality")

    cols = st.columns(4)
    week = fresh["latest_week_start"]
    cols[0].metric("Semana mais recente (início)", fmt.date_br(week),
                   help="Semana da ANP (domingo a sábado) mais recente com preços publicados"
                        f"{': ' + fmt.week_range_br(week) if week else ''}.")
    cols[1].metric("Última coleta", fmt.date_br(fresh["data_as_of"]),
                   help="Data da coleta mais recente entre os preços publicados.")
    cols[2].metric("Arquivo baixado em", fmt.retrieved_short(fresh["source_retrieved_at"]),
                   help=f"Instante do download do arquivo mais recente: {fmt.retrieved_text(fresh['source_retrieved_at'])}. "
                        "Arquivos recebidos manualmente não têm registro.")
    cols[3].metric("Idade do dado", f"{fresh['age_days']} dias" if fresh["age_days"] is not None else fmt.ND,
                   help="Dias entre a última coleta e hoje.")
    st.caption(f"Semana mais recente: **{fmt.week_range_br(week) if week else fmt.ND}**.")
    if fresh["age_days"] is not None and fresh["age_days"] > STALE_AFTER_DAYS:
        st.warning(f"Os dados mais recentes têm {fresh['age_days']} dias. A ANP pode não ter publicado uma semana nova.")
    last = fresh.get("last_load")
    if last and last["status"] == "failed":
        st.warning("A última tentativa de carga de dados falhou; os números abaixo são da última carga bem-sucedida.")

    st.subheader("Estado de São Paulo, por produto")
    rows = []
    for code, label in labels.items():
        try:
            latest = fetch("latest", code, None)
        except ApiError as exc:
            if exc.code == "NO_DATA":
                continue
            raise
        rows.append({
            "Produto": label, "Unidade": fmt.unit_label(units[code]),
            "Mediana": latest["statistics"]["median"],
            "Variação semanal": latest["weekly_change"]["value"],
            "Postos na amostra": latest["sample"]["stations"],
            "Municípios com cobertura baixa": latest["sample"]["low_coverage_municipalities"],
            "Semana (início)": tables.to_date(latest["week_start"]),
        })
    show_table(rows, {"Mediana": fmt.brl, "Variação semanal": fmt.percent, "Postos na amostra": fmt.number_br,
                      "Municípios com cobertura baixa": fmt.number_br, "Semana (início)": tables.day})
    st.caption("Mediana de todas as observações da semana no estado; é um indicador da amostra pesquisada.")

    coverage = quality["coverage"]
    st.subheader("Cobertura da semana mais recente")
    cols = st.columns(4)
    cols[0].metric("Séries (município × produto)", fmt.number_br(coverage["series"]))
    cols[1].metric("Cobertura normal", fmt.number_br(coverage["ok"]))
    cols[2].metric("Cobertura baixa", fmt.number_br(coverage["low"]),
                   help="Séries com menos da metade dos postos que costumavam ser pesquisados.")
    cols[3].metric("Sem histórico", fmt.number_br(coverage["no_history"]),
                   help="Séries novas ou com menos de 8 semanas anteriores.")

    st.subheader("Municípios em destaque")
    available = {loc["municipality"] for loc in fetch("locations")}
    featured = [name for name in FEATURED if name in available]
    default_product = DEFAULT_PRODUCT if DEFAULT_PRODUCT in labels else next(iter(labels), None)
    if shortcut_page is not None and default_product:
        cols = st.columns(4)
        for i, name in enumerate(featured):
            with cols[i % 4]:
                st.page_link(shortcut_page, label=name, query_params={"municipio": name, "produto": default_product})
    else:
        st.write(", ".join(featured) if featured else "Nenhum município em destaque disponível.")
    st.caption("Lista fixa das maiores cidades paulistas presentes nos dados. Use *Explorar município* para os demais.")


# -- Explorar município ---------------------------------------------------------------------


def explore():
    st.title("Explorar município")
    locations = fetch("locations")
    labels, units = product_labels()
    names = [loc["municipality"] for loc in locations]
    left, right = st.columns(2)
    with left:
        municipality = pick("Município (SP)", names, "municipio", default="CAMPINAS",
                            help="Nomes como a ANP publica, em caixa alta e sem acento.")
    with right:
        product = pick("Produto", list(labels), "produto", default=DEFAULT_PRODUCT, format_func=labels.get)
    window = st.radio("Período do gráfico", list(WINDOWS), index=2, horizontal=True)

    latest = fetch("latest", product, municipality)
    freshness_caption(latest)
    st.caption(f"Semana de **{fmt.week_range_br(latest['week_start'])}** · amostra: "
               f"**{fmt.number_br(latest['sample']['observations'])}** observações em "
               f"**{fmt.number_br(latest['sample']['stations'])}** postos · {fmt.unit_label(units[product])}.")
    if not latest["is_dataset_latest_week"]:
        st.warning("Este município não tem dados na semana mais recente do conjunto; "
                   f"os números são da semana de {fmt.week_range_br(latest['week_start'])}.")
    coverage_notice(latest["sample"])

    start = window_start(latest["week_start"], window)
    history = fetch("history", product, municipality, start, latest["week_start"])
    state_history = fetch("history", product, None, start, latest["week_start"])
    state_by_week = {p["week_start"]: p for p in state_history["items"]}
    state_point = state_by_week.get(latest["week_start"])

    stats = latest["statistics"]
    cols = st.columns(4)
    has_change = latest["weekly_change"]["value"] is not None
    cols[0].metric("Mediana", fmt.brl(stats["median"]),
                   delta=fmt.change_text(latest["weekly_change"]) if has_change else None,
                   delta_color="off", delta_arrow="off",  # a seta automática não entende o sinal "−"
                   delta_description="frente à semana anterior" if has_change else None,
                   help="Preço mediano da semana: metade das observações ficou abaixo e metade acima.")
    cols[1].metric("Média", fmt.brl(stats["mean"]), help="Média simples das observações da semana.")
    # Sem "R$" no valor: cabe no cartão e evita `$` duplo, que o Streamlit leria como fórmula.
    cols[2].metric("Faixa (R$)", f"{fmt.decimal_br(stats['min'])} a {fmt.decimal_br(stats['max'])}",
                   help="Menor e maior preço observados na semana.")
    difference = (stats["median"] - state_point["statistics"]["median"]) if state_point else None
    cols[3].metric("Mediana frente ao estado", fmt.signed_brl(difference),
                   help="Mediana do município menos a mediana de todo o estado na mesma semana.")
    if latest["weekly_change"]["value"] is None:
        st.caption(f"Variação semanal: {fmt.change_text(latest['weekly_change'])}.")

    st.plotly_chart(charts.history_figure(history["items"], municipality, fmt.unit_label(units[product]),
                                          state_history["items"]), width="stretch")
    st.caption(f"{len(history['items'])} semanas com dados no período · a faixa sombreada vai do percentil 25 ao 75 · "
               "× marca semanas de cobertura baixa · lacunas são semanas sem dados.")
    with st.expander("Dados do gráfico"):
        show_table([{
            "Semana (início)": tables.to_date(p["week_start"]), "Mediana": p["statistics"]["median"],
            "p25": p["statistics"]["p25"], "p75": p["statistics"]["p75"],
            "Postos": p["sample"]["stations"], "Observações": p["sample"]["observations"],
            "Cobertura": fmt.coverage_label(p["sample"]["coverage_status"]),
            "Variação semanal": p["weekly_change"]["value"],
            "Sem variação porque": fmt.CHANGE_REASONS.get(p["weekly_change"]["reason"], "")}
            for p in reversed(history["items"])],
            {"Semana (início)": tables.day, "Mediana": fmt.brl, "p25": fmt.brl, "p75": fmt.brl,
             "Postos": fmt.number_br, "Observações": fmt.number_br, "Variação semanal": fmt.percent},
            {"Sem variação porque": ""})

    st.subheader("Postos pesquisados")
    stations = fetch("stations", municipality, product)
    st.caption(f"{fmt.number_br(stations['total'])} postos já pesquisados com preço deste produto (a amostra da "
               f"semana tem {fmt.number_br(latest['sample']['stations'])}). Cada preço é o último registrado para o "
               "posto, **em datas que podem diferir**; confira a coluna de data.")
    show_table([{
        "Posto": s["name"] or s["legal_name"], "Bandeira": s["brand"] or fmt.ND, "Endereço": s["address"] or fmt.ND,
        "Bairro": s["neighborhood"] or fmt.ND, "Último preço": s["latest_price"],
        "Data do preço": tables.to_date(s["latest_price_date"]),
        "Aviso": "preço extremo" if "preco_extremo" in s["latest_price_flags"] else ""} for s in stations["items"]],
        {"Último preço": tables.money3, "Data do preço": tables.day})
    if stations["truncated"]:
        st.warning("A lista foi limitada a 2.000 postos; o arquivo para download também.")

    slug = f"{municipality.lower().replace(' ', '-')}_{product.lower()}_{latest['data_as_of']}"
    cols = st.columns(2)
    cols[0].download_button("Baixar histórico (CSV)", exports.history_csv(history), f"historico_{slug}.csv",
                            "text/csv", help="Série semanal do período mostrado, em CSV para Excel (separador `;`).")
    cols[1].download_button("Baixar postos (CSV)", exports.stations_csv(stations["items"], product),
                            f"postos_{slug}.csv", "text/csv", help="Último preço de cada posto, em CSV para Excel.")


# -- Postos mais baratos e mais caros -------------------------------------------------------


def station_rows(stations, with_warning):
    """Preço e data vêm logo depois do nome: se a tabela não couber, o que corta é o endereço."""
    rows = []
    for position, s in enumerate(stations, 1):
        row = {"Posição": position, "Posto": s["name"] or s["legal_name"], "Preço": s["latest_price"],
               "Data do preço": tables.to_date(s["latest_price_date"])}
        if with_warning:  # as duas tabelas ficam com as mesmas colunas
            row["Aviso"] = "preço extremo" if "preco_extremo" in s["latest_price_flags"] else ""
        row["Bandeira"] = s["brand"] or fmt.ND
        row["Endereço"] = ", ".join(part for part in (s["address"], s["neighborhood"]) if part) or fmt.ND
        rows.append(row)
    return rows


def stations_ranking():
    st.title("Postos mais baratos e mais caros")
    locations = fetch("locations")
    labels, units = product_labels()
    names = [loc["municipality"] for loc in locations]
    left, right = st.columns(2)
    with left:
        municipality = pick("Município (SP)", names, "municipio", default="CAMPINAS",
                            help="Nomes como a ANP publica, em caixa alta e sem acento.")
    with right:
        product = pick("Produto", list(labels), "produto", default=DEFAULT_PRODUCT, format_func=labels.get)

    cheapest = fetch("station_ranking", municipality, product, True)
    priciest = fetch("station_ranking", municipality, product, False)
    freshness_caption(cheapest)
    week = cheapest["latest_week_start"]
    st.caption(f"Só entram postos com preço coletado na semana mais recente do conjunto "
               f"(**{fmt.week_range_br(week)}**), em {fmt.unit_label(units[product])}. Postos cujo último preço é de "
               "semanas anteriores ficam de fora: a data do preço é a da coleta, e um preço antigo pode não ter "
               "sido reajustado.")

    total = cheapest["total"]
    if total == 0:
        st.warning(f"**Nenhum posto de {municipality.title()} tem preço de {labels[product].lower()} na semana de "
                   f"{fmt.week_range_br(week)}.** Em *Explorar município* há o histórico e os postos já pesquisados.")
        return
    st.markdown(f"**{fmt.number_br(total)}** posto(s) com preço nesta semana.")
    if total < 3:
        st.info("**Amostra muito pequena:** com menos de 3 postos, o ranking diz pouco sobre o município.")
    elif total < 2 * len(cheapest["items"]):
        st.caption(f"Com {total} postos, as duas listas têm postos em comum.")

    formats = {"Posição": tables.rank, "Preço": tables.money3, "Data do preço": tables.day}
    with_warning = any("preco_extremo" in s["latest_price_flags"] for s in cheapest["items"] + priciest["items"])
    st.subheader("Mais baratos")
    show_table(station_rows(cheapest["items"], with_warning), formats)
    st.subheader("Mais caros")
    show_table(station_rows(priciest["items"], with_warning), formats)
    if with_warning:
        st.caption("**Preço extremo:** valor fora da faixa usual do conjunto; foi mantido, mas pode ser erro "
                   "de digitação. Veja *Qualidade e metodologia*.")


# -- Comparar localidades -------------------------------------------------------------------


def compare():
    st.title("Comparar municípios")
    locations = fetch("locations")
    labels, units = product_labels()
    names = [loc["municipality"] for loc in locations]
    present = [n for n in FEATURED if n in names]
    selected = st.multiselect("Municípios (de 2 a 5)", names, default=present[:3], max_selections=5)
    product = pick("Produto", list(labels), "produto", default=DEFAULT_PRODUCT, format_func=labels.get)
    window = st.radio("Período dos gráficos", list(WINDOWS), index=2, horizontal=True)
    if len(selected) < 2:
        st.info("Escolha pelo menos dois municípios para comparar.")
        return

    state_latest = fetch("latest", product, None)
    start = window_start(state_latest["week_start"], window)
    state_history = fetch("history", product, None, start, state_latest["week_start"])
    weeks = [p["week_start"] for p in reversed(state_history["items"])]
    week = st.selectbox("Semana da comparação", weeks, format_func=fmt.week_range_br)

    body = fetch("compare", product, selected, week)
    freshness_caption(body)
    histories = {name: fetch("history", product, name, start, state_latest["week_start"]) for name in selected}
    change_by_name = {}
    for name, hist in histories.items():
        point = next((p for p in hist["items"] if p["week_start"] == week), None)
        change_by_name[name] = point["weekly_change"] if point else None

    rows = []
    for item in body["items"]:
        name = item["location"]["municipality"]
        s, sample = item["statistics"], item["sample"]
        change = change_by_name.get(name)
        rows.append({
            "Posição": item["rank"], "Município": name,
            "Mediana": s["median"] if s else None,
            "Diferença p/ estado": item["difference_to_state"],
            "Variação semanal": change["value"] if change else None,
            "Postos": sample["stations"], "Observações": sample["observations"],
            "Cobertura": fmt.coverage_label(sample["coverage_status"])})
    ref = body["reference"]
    rows.append({
        "Posição": None, "Município": "ESTADO DE SP (referência)",
        "Mediana": ref["statistics"]["median"] if ref["statistics"] else None,
        "Diferença p/ estado": None, "Variação semanal": None, "Postos": ref["sample"]["stations"],
        "Observações": ref["sample"]["observations"],
        "Cobertura": fmt.coverage_label(ref["sample"]["coverage_status"])})
    st.subheader(f"{labels[product]} — semana de {fmt.week_range_br(week)}")
    show_table(rows, {"Posição": tables.rank, "Mediana": fmt.brl, "Diferença p/ estado": fmt.signed_brl,
                      "Variação semanal": fmt.percent, "Postos": fmt.number_br, "Observações": fmt.number_br},
               {"Posição": "—", "Diferença p/ estado": "—"})
    st.caption("A posição ordena pela menor mediana e só inclui municípios com dados e cobertura normal ou sem "
               "histórico; cobertura baixa fica de fora do ranking. Empates dividem a posição.")
    if any(i["sample"]["coverage_status"] == "low" for i in body["items"]):
        st.warning("Há municípios com **cobertura baixa** nesta semana: sem posição e sem variação semanal.")

    absolute, normalized, base_week = charts.comparison_figures(
        {name: hist["items"] for name, hist in histories.items()}, fmt.unit_label(units[product]))
    st.plotly_chart(absolute, width="stretch")
    if base_week:
        st.plotly_chart(normalized, width="stretch")
        st.caption(f"No índice, **{fmt.date_br(base_week)}** (primeira semana com dados em todos os municípios) vale 100. "
                   "Ele mostra a variação relativa, não o nível do preço.")
    else:
        st.info("Os municípios escolhidos não têm nenhuma semana em comum no período; o índice não pode ser calculado.")


# -- Qualidade e metodologia ----------------------------------------------------------------


def quality():
    st.title("Qualidade dos dados e metodologia")
    fresh = fetch("freshness")
    dq = fetch("data_quality")
    labels, _ = product_labels()

    st.subheader("Fonte e atualização")
    st.markdown(f"**Fonte:** {fresh['source']}.")
    cols = st.columns(3)
    cols[0].metric("Última coleta", fmt.date_br(fresh["data_as_of"]))
    cols[1].metric("Arquivo baixado em", fmt.retrieved_short(fresh["source_retrieved_at"]),
                   help=f"Instante do download: {fmt.retrieved_text(fresh['source_retrieved_at'])}.")
    loaded = fresh["last_successful_load_at"]
    cols[2].metric("Última carga bem-sucedida", fmt.retrieved_short(loaded) if loaded else fmt.ND,
                   help=f"Instante: {fmt.datetime_br(loaded)}.")
    last = dq["last_load"]
    if last:
        st.caption(f"Última tentativa de carga: **{last['status']}** · decisão de qualidade: "
                   f"**{last['quality_decision'] or fmt.ND}** · {fmt.number_br(last['rows_accepted'])} linhas aceitas, "
                   f"{fmt.number_br(last['rows_quarantined'])} em quarentena.")

    obs = dq["observations"]
    st.subheader("Observações")
    cols = st.columns(3)
    cols[0].metric("Publicadas", fmt.number_br(obs["observations_published"]))
    cols[1].metric("Com aviso", fmt.number_br(obs["observations_with_warning"]),
                   help="Publicadas, mas marcadas (por exemplo, preço fora do padrão da semana). Nenhuma foi removida.")
    cols[2].metric("Em quarentena", fmt.number_br(obs["observations_quarantined"]),
                   help="Linhas suspeitas preservadas fora das estatísticas, com o motivo registrado.")
    if obs["warning_counts"]:
        show_table([{"Aviso": k.replace("_", " "), "Observações": v} for k, v in obs["warning_counts"].items()],
                   {"Observações": fmt.number_br})
    if obs["quarantine_reasons"]:
        show_table([{"Motivo": k.replace("_", " "), "Linhas": v} for k, v in obs["quarantine_reasons"].items()],
                   {"Linhas": fmt.number_br})

    coverage = dq["coverage"]
    st.subheader("Cobertura reduzida")
    st.markdown(f"Semana de **{fmt.week_range_br(coverage['week_start'])}**: {fmt.number_br(coverage['low'])} de "
                f"{fmt.number_br(coverage['series'])} séries com cobertura baixa." if coverage["week_start"]
                else "Sem semana disponível.")
    low = dq["low_coverage"]
    if low["items"]:
        show_table([{
            "Município": i["location"]["municipality"], "Produto": labels.get(i["product"], i["product"]),
            "Postos na semana": i["stations"], "Mediana de postos (8 semanas)": i["baseline_median_stations"],
            "Razão": i["coverage_ratio"]} for i in low["items"]],
            {"Postos na semana": fmt.number_br, "Mediana de postos (8 semanas)": tables.decimal1,
             "Razão": tables.percent0})
        if low["total"] > len(low["items"]):
            st.caption(f"Mostrando {len(low['items'])} de {low['total']} séries.")

    st.subheader("Como ler os números")
    st.markdown(METHODOLOGY)
    st.subheader("Limitações conhecidas")
    st.markdown(LIMITATIONS)
    st.caption(f"Documentação interativa da API: {api_base_url()}/docs")


METHODOLOGY = """
* **Mediana semanal** é o indicador principal: metade das observações da semana ficou abaixo e metade acima.
  É menos sensível a valores extremos do que a média, que também é mostrada.
* **Semana** é a da ANP, de domingo a sábado. Cada ponto dos gráficos é uma semana.
* **Amostra**: número de observações (um preço de um posto em um dia) e de postos distintos na semana.
* **Variação semanal** = mediana da semana ÷ mediana da semana anterior − 1. Fica `N/D` sem semana anterior
  imediata ou quando a cobertura de uma das duas semanas é baixa.
* **Cobertura baixa**: menos da metade da mediana de postos das 8 semanas anteriores (com ao menos 3 postos
  na base). Séries com menos de 8 semanas anteriores aparecem como *sem histórico*.
* **Diesel comum** reúne os rótulos `DIESEL` e `DIESEL S500` da ANP; o **S10** é separado.
* Linhas suspeitas ficam em **quarentena** com o motivo registrado; preços extremos recebem **aviso** e são mantidos.
"""

LIMITATIONS = """
* É uma **pesquisa por amostragem**: não representa todos os postos nem preços em tempo real.
* O preço do posto é o registrado na coleta; pode ter mudado depois.
* Hoje só **São Paulo** é publicado; a estrutura prevê outras UFs.
* Alguns arquivos foram recebidos manualmente e não têm registro de download (aparece como
  "sem registro de download").
* Não há previsões nem detecção de variações incomuns ainda; elas dependem de validação contra
  modelos de referência e entram em uma etapa futura.
* Nomes de municípios aparecem como a ANP os publica (caixa alta, sem acento).
"""
