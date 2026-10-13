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
ATTRIBUTION = (
    "Fonte dos dados: **Levantamento de Preços de Combustíveis da ANP** (Agência Nacional do Petróleo, "
    "Gás Natural e Biocombustíveis), dados abertos em gov.br/anp. Medianas, comparações, previsões e "
    "demais números são calculados por este projeto, não divulgados pela ANP.")


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
        footer()
    run.__name__ = page.__name__
    return run


def footer():
    """Rodapé de toda página: crédito à ANP e aviso de que os números derivados são do projeto."""
    st.divider()
    st.caption(ATTRIBUTION)


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


# -- Preços por bandeira --------------------------------------------------------------------


def brands_page():
    st.title("Preços por bandeira")
    locations = fetch("locations")
    labels, units = product_labels()
    left, right = st.columns(2)
    with left:
        choice = pick("Município (SP)", _place_options(locations), "municipio", default=STATE_OPTION,
                      help="Escolha o estado ou um município.")
    with right:
        product = pick("Produto", list(labels), "produto", default=DEFAULT_PRODUCT, format_func=labels.get)
    body = fetch("brands", product, None if choice == STATE_OPTION else choice)
    freshness_caption(body)
    st.caption(md(f"Semana de **{fmt.week_range_br(body['week_start'])}** · {fmt.unit_label(units[product])} · "
                  f"mediana de todos os postos do recorte: **{fmt.brl(body['reference_median'])}** "
                  f"({fmt.number_br(body['reference_stations'])} postos)."))
    if not body["items"]:
        st.info(f"Nenhuma bandeira tem {body['min_stations']} postos ou mais neste recorte e semana, então não há "
                "comparação confiável por bandeira.")
        return
    st.plotly_chart(charts.brand_figure(body["items"], body["reference_median"], fmt.unit_label(units[product])),
                    width="stretch")
    show_table([{
        "Bandeira": i["brand"], "Postos": i["stations"], "Mediana": i["median"],
        "Diferença p/ todos": i["difference_to_reference"], "Mínimo": i["min"], "Máximo": i["max"]}
        for i in body["items"]],
        {"Postos": fmt.number_br, "Mediana": fmt.brl, "Diferença p/ todos": fmt.signed_brl,
         "Mínimo": fmt.brl, "Máximo": fmt.brl})
    if body["hidden_brands"]:
        st.caption(f"{body['hidden_brands']} bandeira(s) com menos de {body['min_stations']} postos "
                   f"({fmt.number_br(body['hidden_stations'])} postos no total) não são detalhadas: a mediana de "
                   "poucos postos diz pouco.")
    st.info("**Preço não é qualidade.** A diferença entre bandeiras mostra quanto cada grupo cobra, não a qualidade "
            "do combustível. *Bandeira branca* são postos sem contrato de fornecimento exclusivo com uma "
            "distribuidora, e o preço também reflete localização, volume e margem.")


# -- Previsões ------------------------------------------------------------------------------

STATE_OPTION = "ESTADO DE SÃO PAULO"
REASON_TEXT = {
    "sem_dado_na_semana_de_origem": "não há preço desta série na semana mais recente",
    "menos_de_52_semanas_de_historico": "menos de 52 semanas de histórico",
    "dados_em_menos_de_80pct_das_semanas": "dados em menos de 80% das semanas recentes",
    "mediana_de_postos_abaixo_de_3": "menos de 3 postos por semana, em mediana",
    "cobertura_baixa_recente": "cobertura baixa nas últimas semanas",
    "sem_residuos_suficientes_para_o_intervalo": "histórico de erros insuficiente para calibrar o intervalo",
    "sem_previsao_na_origem": "a série não foi avaliada na última execução",
}


def md(text):
    """Escapa `$`: dois cifrões num markdown do Streamlit viram uma fórmula (LaTeX)."""
    return text.replace("$", "\\$")


def _place_options(locations):
    return [STATE_OPTION] + [loc["municipality"] for loc in locations]


def forecasts_page():
    st.title("Previsões")
    locations = fetch("locations")
    labels, units = product_labels()
    left, right = st.columns(2)
    with left:
        choice = pick("Município (SP)", _place_options(locations), "municipio", default=STATE_OPTION,
                      help="Escolha o estado para a previsão agregada, ou um município.")
    with right:
        product = pick("Produto", list(labels), "produto", default=DEFAULT_PRODUCT, format_func=labels.get)
    municipality = None if choice == STATE_OPTION else choice

    body = fetch("forecasts", product, municipality)
    freshness_caption(body)
    model, unit = body["model"], fmt.unit_label(units[product])
    backtest = model["backtest"]
    st.caption(f"Previsão feita a partir da semana de **{fmt.week_range_br(body['origin_week_start'])}**, "
               f"modelo **{model['label']}** (versão {model['version']}).")

    if not body["eligible"]:
        reasons = "; ".join(REASON_TEXT.get(r, r.replace("_", " ")) for r in body["reasons"])
        st.warning(f"**Sem previsão para esta série:** {reasons}. Prever com pouco histórico ou amostra pequena "
                   "daria uma falsa impressão de precisão, então o painel não mostra um número.")
        return

    history_start = window_start(body["origin_week_start"], "26 semanas")
    history = fetch("history", product, municipality, history_start, body["origin_week_start"])
    st.plotly_chart(charts.forecast_figure(history["items"], body["items"], choice.title() if municipality else
                                           "Estado de São Paulo", unit, body["interval_level"]), width="stretch")
    first, last = body["items"][0], body["items"][-1]
    cols = st.columns(3)
    cols[0].metric(f"Em 1 semana ({fmt.date_br(first['target_week_start'])})", fmt.brl(first["point"]),
                   help="Previsão central da mediana semanal.")
    cols[1].metric("Faixa em 1 semana (R$)", f"{fmt.decimal_br(first['lower'])} a {fmt.decimal_br(first['upper'])}",
                   help=f"Intervalo de {body['interval_level']:.0%} calibrado nos erros do backtest.")
    cols[2].metric(f"Em 4 semanas ({fmt.date_br(last['target_week_start'])})", fmt.brl(last["point"]))
    show_table([{
        "Horizonte": f"{i['horizon']} semana(s)", "Semana (início)": tables.to_date(i["target_week_start"]),
        "Previsão": i["point"], "Mínimo": i["lower"], "Máximo": i["upper"]} for i in body["items"]],
        {"Semana (início)": tables.day, "Previsão": fmt.brl, "Mínimo": fmt.brl, "Máximo": fmt.brl})
    st.caption(md(f"{body['history_weeks']} semanas de histórico · unidade: {unit} · a previsão é da **mediana "
                  "semanal** da pesquisa da ANP, não do preço de um posto."))

    st.subheader("Quão confiável é")
    if backtest:
        published = backtest["published"]
        st.markdown(md(
            f"No teste com dados passados (**{fmt.number_br(backtest['points'])}** previsões em "
            f"**{backtest['origins']}** datas de corte), o erro médio foi de **{fmt.brl(published['mae'])}** por "
            f"litro e **{fmt.percent(published['interval_coverage'], 0, signed=False)}** dos valores reais ficaram "
            f"dentro do intervalo (meta de {body['interval_level']:.0%})."))
        if model["kind"] == "baseline":
            candidate = backtest["candidate"]
            detail = ""
            if candidate and backtest["candidate_change"] is not None:
                detail = (f" Ele teve erro {fmt.percent(abs(backtest['candidate_change']), 0, signed=False)} "
                          f"{'menor' if backtest['candidate_change'] < 0 else 'maior'} que o baseline"
                          f" (a regra exige ao menos 5% de melhora).")
            st.info(f"**A previsão publicada vem de um modelo simples** ({model['label']}). Um modelo de machine "
                    f"learning (LightGBM) foi testado e **não foi aprovado**: não superou o baseline de forma "
                    f"consistente.{detail} Mais detalhes em *Qualidade e metodologia*.")
        else:
            st.success("Um modelo de machine learning superou o baseline nos critérios de aprovação.")
    st.caption("Previsões são estimativas estatísticas, não garantias. Mudanças de política, câmbio, petróleo e "
               "impostos não entram no modelo.")


# -- Variações incomuns ---------------------------------------------------------------------


def anomalies_page():
    st.title("Variações incomuns")
    st.markdown(
        "Semanas em que a mediana de um município ou do estado **saiu muito do que se esperava** frente à semana "
        "anterior. É um **sinal estatístico** para olhar com atenção, não uma conclusão sobre os postos: pode "
        "refletir reajuste real, mudança na amostra pesquisada ou erro de coleta.")
    locations = fetch("locations")
    labels, units = product_labels()
    left, middle, right = st.columns(3)
    with left:
        product_choice = st.selectbox("Produto", ["Todos"] + list(labels), format_func=lambda c: labels.get(c, c))
    with middle:
        place_choice = st.selectbox("Local", ["Todos"] + _place_options(locations),
                                    help="Todos, o estado ou um município.")
    with right:
        weeks = st.radio("Período", [4, 8, 12], horizontal=True, format_func=lambda n: f"{n} semanas")
    product = None if product_choice == "Todos" else product_choice
    municipality = None if place_choice in ("Todos", STATE_OPTION) else place_choice
    body = fetch("anomalies", product, municipality, weeks)
    freshness_caption(body)
    items = body["items"]
    if place_choice == STATE_OPTION:
        items = [i for i in items if i["location"]["municipality"] is None]
    st.caption(f"Desde a semana de **{fmt.week_range_br(body['since_week_start'])}** · modelo de referência: "
               f"{body['model_version']}.")
    if not items:
        st.info("Nenhuma variação incomum no período e nos filtros escolhidos.")
        return
    st.markdown(f"**{fmt.number_br(len(items))}** variação(ões) incomum(ns).")
    show_table([{
        "Semana (início)": tables.to_date(i["week_start"]),
        "Local": i["location"]["municipality"] or "Estado de São Paulo",
        "Produto": labels.get(i["product"], i["product"]), "Observado": i["observed"], "Esperado": i["expected"],
        "Diferença": i["difference"], "Faixa usual": f"{fmt.decimal_br(i['lower'])} a {fmt.decimal_br(i['upper'])}",
        "Sentido": i["direction"], "Postos": i["stations"]} for i in items],
        {"Semana (início)": tables.day, "Observado": fmt.brl, "Esperado": fmt.brl, "Diferença": fmt.signed_brl,
         "Postos": fmt.number_br})
    st.caption(md("**Como é definida:** a mediana da semana ficou fora da faixa usual de 99% de variação de uma "
                  "semana para outra (calculada nos erros do teste com dados passados, por produto e nível), a "
                  "diferença é de ao menos R$ 0,15 e a amostra tem 3 postos ou mais. Séries com cobertura baixa "
                  "ficam de fora."))


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


def model_section():
    """Modelo publicado e resultado do backtest (a API devolve o mesmo resumo em qualquer série)."""
    st.subheader("Modelo de previsão e validação")
    try:
        body = fetch("forecasts", DEFAULT_PRODUCT, None)
    except ApiError as exc:
        if exc.code != "NO_PUBLISHED_MODEL":
            raise
        st.info("Ainda não há modelo de previsão publicado.")
        return
    model, backtest = body["model"], body["model"]["backtest"]
    st.markdown(f"**Modelo publicado:** {model['label']} · versão {model['version']} · "
                f"{'baseline (modelo simples de referência)' if model['kind'] == 'baseline' else 'candidato aprovado'}.")
    if not backtest:
        return
    rows = [{"Modelo": f"{model['label']} (publicado)", "Erro médio (R$/L)": backtest["published"]["mae"],
             "Erro ponderado (R$/L)": backtest["published"]["weighted_mae"],
             "Viés (R$/L)": backtest["published"]["bias"],
             "Cobertura do intervalo": backtest["published"]["interval_coverage"]}]
    if backtest["candidate"]:
        rows.append({"Modelo": "LightGBM global (candidato)", "Erro médio (R$/L)": backtest["candidate"]["mae"],
                     "Erro ponderado (R$/L)": backtest["candidate"]["weighted_mae"],
                     "Viés (R$/L)": backtest["candidate"]["bias"],
                     "Cobertura do intervalo": backtest["candidate"]["interval_coverage"]})
    show_table(rows, {"Erro médio (R$/L)": fmt.brl, "Erro ponderado (R$/L)": fmt.brl,
                      "Viés (R$/L)": fmt.signed_brl, "Cobertura do intervalo": tables.percent0})
    verdict = ("foi **aprovado**" if backtest["candidate_approved"]
               else "**não foi aprovado**, então o baseline permanece publicado")
    st.markdown(f"O candidato de machine learning {verdict}. Critérios (arquitetura, seção 14.8):")
    for check, ok in backtest["checks"].items():
        st.markdown(f"- {'✅' if ok else '❌'} {CHECK_TEXT.get(check, check.replace('_', ' '))}")
    st.caption(f"Backtest com origem deslizante: {fmt.number_br(backtest['points'])} previsões em "
               f"{backtest['origins']} datas de corte, todas avaliadas só com dados anteriores a cada corte. "
               "Relatório completo em `reports/forecasting/backtest.md`.")


CHECK_TEXT = {
    "melhora_minima_de_5pct_no_mae_ponderado": "melhora de pelo menos 5% no erro ponderado contra o melhor baseline",
    "sem_regressao_grave_em_grupo": "sem piora grave em produto, nível ou porte de município",
    "vies_aceitavel": "viés médio de até 25% do erro",
    "cobertura_do_intervalo_na_faixa": "cobertura do intervalo entre 70% e 90%",
    "reprodutivel": "mesmos dados e semente geram as mesmas previsões",
    "candidato_avaliado": "candidato avaliado",
}


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

    model_section()
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
* **Previsões** são da mediana semanal, de 1 a 4 semanas, com intervalo calibrado nos erros do teste com
  dados passados; só séries com histórico e amostra suficientes têm previsão. Não incluem política de preços,
  câmbio nem petróleo.
* **Variação incomum** é um sinal estatístico (fora de uma faixa de 99%), não indica irregularidade de postos.
* Nomes de municípios aparecem como a ANP os publica (caixa alta, sem acento).
"""
