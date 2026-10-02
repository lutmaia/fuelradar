# Perfil ANP — resultado gerado

Contagens completas, sem amostragem de linhas. SP inclui GLP para diagnóstico; `automotive_*` exclui GLP.
Datas de agregados são referências, não datas individuais de coleta. Postos únicos só são calculáveis com CNPJ.

| Arquivo / planilha | Tipo | Linhas totais | Linhas SP | Período SP | Municípios SP | CNPJ únicos SP |
|---|---|---:|---:|---|---:|---:|
| Preços semestrais - AUTOMOTIVOS_2026.01.csv / CSV | retail_observation | 422418 | 117616 | 2026-01-01 a 2026-06-30 | 100 | 2599 |
| revendas_lpc_2026-09-06_2026-09-12.xlsx / POSTOS REVENDEDORES | retail_observation | 19516 | 5130 | 2026-09-07 a 2026-09-12 | 87 | 1804 |
| revendas_lpc_2026-09-13_2026-09-19.xlsx / POSTOS REVENDEDORES | retail_observation | 20076 | 5365 | 2026-09-14 a 2026-09-18 | 91 | 1916 |
| revendas_lpc_2026-09-20_2026-09-26.xlsx / POSTOS REVENDEDORES | retail_observation | 20434 | 5458 | 2026-09-21 a 2026-09-25 | 94 | 1928 |

Agregados em diferentes níveis não devem ser somados. `None`/N/D indica dimensão não disponível.

## Esquemas distintos

- retail_observation (16 colunas, 1 planilhas): Regiao - Sigla; Estado - Sigla; Municipio; Revenda; CNPJ da Revenda; Nome da Rua; Numero Rua; Complemento; Bairro; Cep; Produto; Data da Coleta; Valor de Venda; Valor de Compra; Unidade de Medida; Bandeira
- retail_observation (15 colunas, 3 planilhas): CNPJ; RAZÃO; FANTASIA; ENDEREÇO; NÚMERO; COMPLEMENTO; BAIRRO; CEP; MUNICÍPIO; ESTADO; BANDEIRA; PRODUTO; UNIDADE DE MEDIDA; PREÇO DE REVENDA; DATA DA COLETA

## União das observações individuais SP

```json
{
  "sp": {
    "rows": 133569,
    "date_range": {
      "min": "2026-01-01",
      "max": "2026-09-25"
    },
    "municipality_count": 100,
    "municipalities": [
      "ADAMANTINA",
      "AMERICANA",
      "ARACATUBA",
      "ARARAQUARA",
      "ARARAS",
      "ASSIS",
      "ATIBAIA",
      "AVARE",
      "BARRETOS",
      "BARUERI",
      "BAURU",
      "BEBEDOURO",
      "BIRIGUI",
      "BOTUCATU",
      "BRAGANCA PAULISTA",
      "CACAPAVA",
      "CAMPINAS",
      "CARAGUATATUBA",
      "CARAPICUIBA",
      "CATANDUVA",
      "COSMOPOLIS",
      "COTIA",
      "CRUZEIRO",
      "CUBATAO",
      "DIADEMA",
      "EMBU DAS ARTES",
      "FRANCA",
      "GARCA",
      "GUARATINGUETA",
      "GUARUJA",
      "GUARULHOS",
      "HORTOLANDIA",
      "IBITINGA",
      "INDAIATUBA",
      "ITANHAEM",
      "ITAPECERICA DA SERRA",
      "ITAPETININGA",
      "ITAPEVA",
      "ITAPIRA",
      "ITAPOLIS",
      "ITAQUAQUECETUBA",
      "ITATIBA",
      "ITU",
      "JABOTICABAL",
      "JACAREI",
      "JALES",
      "JAU",
      "JOSE BONIFACIO",
      "JUNDIAI",
      "LEME",
      "LIMEIRA",
      "LINS",
      "LORENA",
      "MARILIA",
      "MATAO",
      "MAUA",
      "MOCOCA",
      "MOGI DAS CRUZES",
      "MOGI GUACU",
      "MOGI MIRIM",
      "MONTE ALTO",
      "OLIMPIA",
      "OSASCO",
      "OURINHOS",
      "PARAGUACU PAULISTA",
      "PAULINIA",
      "PIRACICABA",
      "PIRASSUNUNGA",
      "POA",
      "PORTO FERREIRA",
      "PRAIA GRANDE",
      "PRESIDENTE PRUDENTE",
      "RIBEIRAO PIRES",
      "RIBEIRAO PRETO",
      "RIO CLARO",
      "SALTO",
      "SANTO ANDRE",
      "SANTOS",
      "SAO BERNARDO DO CAMPO",
      "SAO CAETANO DO SUL",
      "SAO CARLOS",
      "SAO JOAO DA BOA VISTA",
      "SAO JOSE DO RIO PRETO",
      "SAO JOSE DOS CAMPOS",
      "SAO PAULO",
      "SAO VICENTE",
      "SERTAOZINHO",
      "SOROCABA",
      "SUMARE",
      "SUZANO",
      "TABOAO DA SERRA",
      "TATUI",
      "TAUBATE",
      "TUPA",
      "UBATUBA",
      "VALINHOS",
      "VARZEA PAULISTA",
      "VINHEDO",
      "VOTORANTIM",
      "VOTUPORANGA"
    ],
    "unique_cnpj_count": 3392,
    "products": {
      "DIESEL_NAO_ESPECIFICADO": 10508,
      "DIESEL_S10": 22764,
      "DIESEL_S500": 1288,
      "ETANOL_HIDRATADO": 34209,
      "GASOLINA_ADITIVADA": 26893,
      "GASOLINA_COMUM": 34519,
      "GLP": 2111,
      "GNV": 1277
    },
    "automotive_rows": 131458,
    "automotive_unique_cnpj_count": 2667,
    "automotive_municipality_count": 100
  },
  "jundiai": {
    "rows": 1855,
    "date_range": {
      "min": "2026-01-07",
      "max": "2026-09-24"
    },
    "municipality_count": 1,
    "municipalities": [
      "JUNDIAI"
    ],
    "unique_cnpj_count": 64,
    "products": {
      "DIESEL_NAO_ESPECIFICADO": 162,
      "DIESEL_S10": 311,
      "DIESEL_S500": 12,
      "ETANOL_HIDRATADO": 448,
      "GASOLINA_ADITIVADA": 408,
      "GASOLINA_COMUM": 460,
      "GLP": 16,
      "GNV": 38
    },
    "automotive_rows": 1839,
    "automotive_unique_cnpj_count": 56,
    "automotive_municipality_count": 1
  },
  "candidate_key_duplicates_across_inputs": 0
}
```

## Sobreposições entre fontes individuais (SP)

```json
[
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/historicos/Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "table": "Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "sheet": null
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "table": "revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  },
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/historicos/Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "table": "Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "sheet": null
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "table": "revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  },
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/historicos/Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "table": "Preços semestrais - AUTOMOTIVOS_2026.01.csv",
      "sheet": null
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "table": "revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  },
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "table": "revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "table": "revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  },
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "table": "revendas_lpc_2026-09-06_2026-09-12.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "table": "revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  },
  {
    "left": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "table": "revendas_lpc_2026-09-13_2026-09-19.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "right": {
      "input_path": "C:/Users/Pichau/OneDrive/Desktop/projeto_postos_sp/data/raw/revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "table": "revendas_lpc_2026-09-20_2026-09-26.xlsx",
      "sheet": "POSTOS REVENDEDORES"
    },
    "shared_collection_dates": 0,
    "shared_date_range": null,
    "shared_candidate_keys": 0,
    "shared_keys_same_price_set": 0,
    "shared_keys_conflicting_price_sets": 0
  }
]
```

Consulte profile.json para cabeçalhos, tipos, ausências, domínios originais/normalizados, preços, identificadores ambíguos, duplicidades e hashes.
