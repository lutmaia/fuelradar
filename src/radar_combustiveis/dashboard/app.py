"""Ponto de entrada do painel: `streamlit run src/radar_combustiveis/dashboard/app.py`.

Prefira `python scripts/run_dashboard.py`. A API deve estar no ar (RADAR_API_URL).
"""

from pathlib import Path
import sys

# Sem instalação do pacote, o Streamlit executa este arquivo como script; `src` entra no caminho.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from radar_combustiveis.dashboard import views  # noqa: E402


def main():
    st.set_page_config(page_title="Radar de Combustíveis SP", page_icon="⛽", layout="wide",
                       initial_sidebar_state="expanded")
    explore_page = st.Page(views.guarded(views.explore), title="Explorar município", url_path="municipio", icon="🔎")
    home_page = st.Page(views.guarded(lambda: views.home(explore_page)), title="Início", url_path="inicio",
                        icon="🏠", default=True)
    pages = [home_page, explore_page,
             st.Page(views.guarded(views.stations_ranking), title="Postos: mais baratos e mais caros",
                     url_path="postos", icon="⛽"),
             st.Page(views.guarded(views.brands_page), title="Preços por bandeira", url_path="bandeiras", icon="🏷️"),
             st.Page(views.guarded(views.forecasts_page), title="Previsões", url_path="previsoes", icon="🔮"),
             st.Page(views.guarded(views.anomalies_page), title="Variações incomuns", url_path="variacoes", icon="⚠️"),
             st.Page(views.guarded(views.compare), title="Comparar municípios", url_path="comparar", icon="📊"),
             st.Page(views.guarded(views.regions_page), title="Regiões", url_path="regioes", icon="🗺️"),
             st.Page(views.guarded(views.study_page), title="Estudo", url_path="estudo", icon="🔬"),
             st.Page(views.guarded(views.quality), title="Qualidade e metodologia", url_path="qualidade", icon="🧭")]
    st.navigation(pages).run()


main()
