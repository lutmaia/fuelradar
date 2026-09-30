# Perfil ANP — resultado gerado

Contagens completas, sem amostragem de linhas. SP inclui GLP para diagnóstico; `automotive_*` exclui GLP.
Datas de agregados são referências, não datas individuais de coleta. Postos únicos só são calculáveis com CNPJ.

| Arquivo / planilha | Tipo | Linhas totais | Linhas SP | Período SP | Municípios SP | CNPJ únicos SP |
|---|---|---:|---:|---|---:|---:|
| mensal-municipios-desde-jan2026.xlsx / MUNICÍPIOS - JAN 26 EM DIANTE | monthly_aggregate | 20438 | 4901 | 2026-01-01 a 2026-08-01 | 100 | None |
| mensal-municipios-jan2022-2025.xlsx / MUNICÍPIOS - JAN 22 A DEZ 25 | monthly_aggregate | 118444 | 29185 | 2022-01-01 a 2025-12-01 | 108 | None |
| mensal-regioes-desde-jan2013.xlsx / REGIÕES - DESDE JANEIRO DE 2013 | monthly_aggregate | 5247 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx / CAPITAIS | weekly_aggregate | 156 | 7 | 2026-09-06 a 2026-09-12 | 1 | None |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx / MUNICIPIOS | weekly_aggregate | 2353 | 536 | 2026-09-06 a 2026-09-12 | 87 | None |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx / ESTADOS | weekly_aggregate | 176 | 7 | 2026-09-06 a 2026-09-12 | None | None |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx / REGIOES | weekly_aggregate | 35 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-06_2026-09-12.xlsx / BRASIL | weekly_aggregate | 7 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx / CAPITAIS | weekly_aggregate | 165 | 7 | 2026-09-13 a 2026-09-19 | 1 | None |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx / MUNICIPIOS | weekly_aggregate | 2383 | 565 | 2026-09-13 a 2026-09-19 | 91 | None |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx / ESTADOS | weekly_aggregate | 177 | 7 | 2026-09-13 a 2026-09-19 | None | None |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx / REGIOES | weekly_aggregate | 35 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-13_2026-09-19.xlsx / BRASIL | weekly_aggregate | 7 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx / CAPITAIS | weekly_aggregate | 162 | 7 | 2026-09-20 a 2026-09-26 | 1 | None |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx / MUNICIPIOS | weekly_aggregate | 2461 | 585 | 2026-09-20 a 2026-09-26 | 94 | None |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx / ESTADOS | weekly_aggregate | 178 | 7 | 2026-09-20 a 2026-09-26 | None | None |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx / REGIOES | weekly_aggregate | 35 | N/D | N/D a N/D | None | None |
| resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx / BRASIL | weekly_aggregate | 7 | N/D | N/D a N/D | None | None |
| revendas_lpc_2026-09-06_2026-09-12.xlsx / POSTOS REVENDEDORES | retail_observation | 19516 | 5130 | 2026-09-07 a 2026-09-12 | 87 | 1804 |
| revendas_lpc_2026-09-13_2026-09-19.xlsx / POSTOS REVENDEDORES | retail_observation | 20076 | 5365 | 2026-09-14 a 2026-09-18 | 91 | 1916 |
| revendas_lpc_2026-09-20_2026-09-26.xlsx / POSTOS REVENDEDORES | retail_observation | 20434 | 5458 | 2026-09-21 a 2026-09-25 | 94 | 1928 |

Agregados em diferentes níveis não devem ser somados. `None`/N/D indica dimensão não disponível.

## Esquemas distintos

- monthly_aggregate (18 colunas, 2 planilhas): MÊS; PRODUTO; REGIÃO; ESTADO; MUNICÍPIO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; MARGEM MÉDIA REVENDA; COEF DE VARIAÇÃO REVENDA; PREÇO MÉDIO DISTRIBUIÇÃO; DESVIO PADRÃO DISTRIBUIÇÃO; PREÇO MÍNIMO DISTRIBUIÇÃO; PREÇO MÁXIMO DISTRIBUIÇÃO; COEF DE VARIAÇÃO DISTRIBUIÇÃO
- monthly_aggregate (16 colunas, 1 planilhas): MÊS; PRODUTO; REGIÃO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; COEF DE VARIAÇÃO REVENDA; MARGEM MÉDIA REVENDA; PREÇO MÉDIO DISTRIBUIÇÃO; DESVIO PADRÃO DISTRIBUIÇÃO; PREÇO MÍNIMO DISTRIBUIÇÃO; PREÇO MÁXIMO DISTRIBUIÇÃO; COEF DE VARIAÇÃO DISTRIBUIÇÃO
- weekly_aggregate (12 colunas, 6 planilhas): DATA INICIAL; DATA FINAL; ESTADO; MUNICÍPIO; PRODUTO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; COEF DE VARIAÇÃO REVENDA
- weekly_aggregate (12 colunas, 3 planilhas): DATA INICIAL; DATA FINAL; REGIAO; ESTADOS; PRODUTO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; COEF DE VARIAÇÃO REVENDA
- weekly_aggregate (11 colunas, 3 planilhas): DATA INICIAL; DATA FINAL; REGIAO; PRODUTO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; COEF DE VARIAÇÃO REVENDA
- weekly_aggregate (11 colunas, 3 planilhas): DATA INICIAL; DATA FINAL; BRASIL; PRODUTO; NÚMERO DE POSTOS PESQUISADOS; UNIDADE DE MEDIDA; PREÇO MÉDIO REVENDA; DESVIO PADRÃO REVENDA; PREÇO MÍNIMO REVENDA; PREÇO MÁXIMO REVENDA; COEF DE VARIAÇÃO REVENDA
- retail_observation (15 colunas, 3 planilhas): CNPJ; RAZÃO; FANTASIA; ENDEREÇO; NÚMERO; COMPLEMENTO; BAIRRO; CEP; MUNICÍPIO; ESTADO; BANDEIRA; PRODUTO; UNIDADE DE MEDIDA; PREÇO DE REVENDA; DATA DA COLETA

## União das observações semanais SP

```json
{
  "sp": {
    "rows": 15953,
    "date_range": {
      "min": "2026-09-07",
      "max": "2026-09-25"
    },
    "municipality_count": 97,
    "municipalities": [
      "ADAMANTINA",
      "AMERICANA",
      "ARACATUBA",
      "ARARAQUARA",
      "ARARAS",
      "ASSIS",
      "ATIBAIA",
      "BARRETOS",
      "BARUERI",
      "BAURU",
      "BEBEDOURO",
      "BIRIGUI",
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
    "unique_cnpj_count": 2380,
    "products": {
      "DIESEL_S10": 2493,
      "DIESEL_S500": 1288,
      "ETANOL_HIDRATADO": 3571,
      "GASOLINA_ADITIVADA": 2754,
      "GASOLINA_COMUM": 3606,
      "GLP": 2111,
      "GNV": 130
    },
    "automotive_rows": 13842,
    "automotive_unique_cnpj_count": 1635,
    "automotive_municipality_count": 97
  },
  "jundiai": {
    "rows": 156,
    "date_range": {
      "min": "2026-09-15",
      "max": "2026-09-24"
    },
    "municipality_count": 1,
    "municipalities": [
      "JUNDIAI"
    ],
    "unique_cnpj_count": 28,
    "products": {
      "DIESEL_S10": 26,
      "DIESEL_S500": 12,
      "ETANOL_HIDRATADO": 34,
      "GASOLINA_ADITIVADA": 32,
      "GASOLINA_COMUM": 34,
      "GLP": 16,
      "GNV": 2
    },
    "automotive_rows": 140,
    "automotive_unique_cnpj_count": 20,
    "automotive_municipality_count": 1
  },
  "candidate_key_duplicates_across_inputs": 0
}
```

Consulte profile.json para cabeçalhos, tipos, ausências, domínios, preços, duplicidades e hashes.
