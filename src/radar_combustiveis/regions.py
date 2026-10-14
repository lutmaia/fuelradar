"""Regiões de SP usadas no estudo descritivo (Marco 8b) e na página Regiões do painel.

Capital, metropolitana (os outros municípios da RMSP), litoral e interior. Nomes como a ANP publica
(caixa alta, sem acento, `municipality_name_normalized`); as listas foram escritas à mão.
"""

CAPITAL = "SAO PAULO"
# Região Metropolitana de São Paulo: 39 municípios, a capital tratada à parte. Nomes como a ANP
# publica (caixa alta, sem acento); a lista foi escrita à mão e o relatório mostra quais estão nos dados.
METRO = frozenset({
    "ARUJA", "BARUERI", "BIRITIBA-MIRIM", "BIRITIBA MIRIM", "CAIEIRAS", "CAJAMAR", "CARAPICUIBA", "COTIA",
    "DIADEMA", "EMBU DAS ARTES", "EMBU-GUACU", "EMBU GUACU", "FERRAZ DE VASCONCELOS", "FRANCISCO MORATO",
    "FRANCO DA ROCHA", "GUARAREMA", "GUARULHOS", "ITAPECERICA DA SERRA", "ITAPEVI", "ITAQUAQUECETUBA", "JANDIRA",
    "JUQUITIBA", "MAIRIPORA", "MAUA", "MOGI DAS CRUZES", "OSASCO", "PIRAPORA DO BOM JESUS", "POA",
    "RIBEIRAO PIRES", "RIO GRANDE DA SERRA", "SALESOPOLIS", "SANTA ISABEL", "SANTANA DE PARNAIBA", "SANTO ANDRE",
    "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL", "SAO LOURENCO DA SERRA", "SUZANO", "TABOAO DA SERRA",
    "VARGEM GRANDE PAULISTA"})
# Litoral: Baixada Santista, Litoral Norte e os municípios costeiros do Vale do Ribeira.
COAST = frozenset({
    "BERTIOGA", "CUBATAO", "GUARUJA", "ITANHAEM", "MONGAGUA", "PERUIBE", "PRAIA GRANDE", "SANTOS", "SAO VICENTE",
    "CARAGUATATUBA", "ILHABELA", "SAO SEBASTIAO", "UBATUBA", "IGUAPE", "ILHA COMPRIDA", "CANANEIA"})
REGIONS = ("capital", "metropolitana", "litoral", "interior")
LABELS = {"capital": "Capital", "metropolitana": "Região metropolitana", "litoral": "Litoral",
          "interior": "Interior"}


def region_of(municipality):
    if municipality == CAPITAL:
        return "capital"
    if municipality in METRO:
        return "metropolitana"
    if municipality in COAST:
        return "litoral"
    return "interior"
