"""As três fontes externas: endereço, licença, crédito e regra de disponibilidade (`available_at`)."""

from dataclasses import dataclass
from datetime import date, timedelta

ANP_TERMS = "https://www.gov.br/anp/pt-br/acesso-a-informacao/termos-de-uso-privacidade-e-seguranca-1"
ANP_PRICES = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos"
HISTORY_START = date(2022, 11, 1)  # o banco começa em 2022-11-13; um pouco antes cobre a primeira semana


@dataclass(frozen=True)
class Source:
    source_id: str
    publisher: str
    title: str
    page_url: str
    license: str
    terms_url: str
    cadence: str
    lag_rule: str


DOLLAR = Source(
    "bcb_sgs_1", "Banco Central do Brasil", "Taxa de câmbio livre, dólar americano (venda), diária — SGS 1",
    "https://dadosabertos.bcb.gov.br/dataset/1-taxa-de-cambio---livre---dolar-americano-venda---diario",
    "ODbL (Open Database License)", "https://opendatacommons.org/licenses/odbl/", "diária",
    "disponível no dia seguinte à cotação")
PRODUCERS = Source(
    "anp_produtores", "ANP", "Preços médios ponderados semanais de produtores e importadores",
    ANP_PRICES + "/precos-de-produtores-e-importadores-de-derivados-de-petroleo-e-biodiesel",
    "Termos de uso do portal da ANP: reprodução sem fins lucrativos, com citação da fonte", ANP_TERMS,
    "semanal (segunda a domingo)", "12 dias depois do fim da semana (estimativa da ANP)")
DISTRIBUTION = Source(
    "anp_distribuicao", "ANP", "Preços médios semanais de distribuição de combustíveis líquidos",
    ANP_PRICES + "/precos-de-distribuicao-de-combustiveis",
    "Termos de uso do portal da ANP: reprodução sem fins lucrativos, com citação da fonte", ANP_TERMS,
    "semanal (domingo a sábado)", "último dia do mês seguinte ao fim da semana (prazo da ANP)")
SOURCES = {s.source_id: s for s in (DOLLAR, PRODUCERS, DISTRIBUTION)}

DOLLAR_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json&dataInicial={start}&dataFinal={end}"
PRODUCERS_URL = ANP_PRICES + "/ppidp/precos-medios-ponderados-semanais-2013.xls"
DISTRIBUTION_URL = ANP_PRICES + "/pdc/semanal/{name}.xlsx"
DISTRIBUTION_FILES = ("combustiveis-liquidos-estados", "combustiveis-liquidos-municipios-ago2020_a_dez2023",
                      "combustiveis-liquidos-municipios_desde2024")

# Produtos da distribuição -> códigos do projeto (os mesmos da pesquisa nos postos).
DISTRIBUTION_PRODUCTS = {
    "GASOLINA C COMUM": "GASOLINA_COMUM",
    "GASOLINA C COMUM ADITIVADA": "GASOLINA_ADITIVADA",
    "ETANOL HIDRATADO COMUM": "ETANOL_HIDRATADO",
    "OLEO DIESEL B S10 - COMUM": "DIESEL_S10",
    "OLEO DIESEL B S500 - COMUM": "DIESEL_COMUM",
}
# Produtos de produtores usados como custo (antes da mistura de etanol ou biodiesel).
PRODUCER_PRODUCTS = {
    "GASOLINA A COMUM (R$/LITRO)": "GASOLINA_A_COMUM",
    "GASOLINA A PREMIUM (R$/LITRO)": "GASOLINA_A_PREMIUM",
    "OLEO DIESEL S-10 (R$/LITRO)": "DIESEL_A_S10",
    "OLEO DIESEL S-500 (R$/LITRO)": "DIESEL_A_S500",
    "BIODIESEL B-100 (R$/LITRO)": "BIODIESEL_B100",
}
PRODUCER_REGIONS = ("NORTE", "NORDESTE", "CENTRO-OESTE", "SUL", "SUDESTE", "BRASIL")


def _month_end(year, month):
    return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)


def rule_available_at(source_id, period_end):
    """Data a partir da qual o valor podia ser conhecido, pela regra publicada de cada fonte."""
    if source_id == DOLLAR.source_id:
        return period_end + timedelta(days=1)
    if source_id == PRODUCERS.source_id:
        return period_end + timedelta(days=12)
    if source_id == DISTRIBUTION.source_id:
        return _month_end(period_end.year + period_end.month // 12, period_end.month % 12 + 1)
    raise ValueError(f"Fonte desconhecida: {source_id}")


def available_at(source_id, period_end, first_seen):
    """O mais cedo entre a regra da fonte e o dia em que o projeto viu o valor pela primeira vez.

    Sem histórico de publicação, a regra é o que protege as previsões do passado; um valor que o
    projeto baixou antes do prazo da regra já existia naquele dia."""
    rule = rule_available_at(source_id, period_end)
    return min(rule, first_seen) if first_seen else rule
