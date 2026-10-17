"""Ficha do conjunto de dados: números calculados no banco, nunca digitados à mão.

`collect(conn)` devolve um dicionário só com contagens e agregados (sem CNPJ, razão social nem
endereço); `sources(conn)` lista os arquivos de origem com SHA-256, para um terceiro conferir que
baixou os mesmos dados. Os textos em português e inglês são montados a partir desse dicionário.
"""

from datetime import date, timedelta
import re

from .db.connection import SCHEMA
from .regions import LABELS, region_of

CURRENT = "is_current_source_revision"


def _rows(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def gaps(weeks, defective=frozenset()):
    """Semanas (domingos) sem dado entre a primeira e a última, em intervalos [início, fim, causa].

    Causa "defeito" quando o arquivo da semana está na lista de exclusão (ADR 0006); senão
    "sem_arquivo" (a ANP não publicou a semana na página)."""
    have = sorted(set(weeks))
    if not have:
        return []
    missing, week = [], have[0]
    present = set(have)
    while week <= have[-1]:
        if week not in present:
            cause = "defeito" if week in defective else "sem_arquivo"
            if missing and missing[-1][1] == week - timedelta(weeks=1) and missing[-1][2] == cause:
                missing[-1][1] = week
            else:
                missing.append([week, week, cause])
        week += timedelta(weeks=1)
    return missing


def defective_weeks(excluded):
    """Inícios de semana dos arquivos semanais da lista de exclusão (pelo nome revendas_lpc_AAAA-MM-DD_...)."""
    weeks = set()
    for item in excluded.values():
        match = re.match(r"revendas_lpc_(\d{4}-\d{2}-\d{2})_", item["file"])
        if match:
            weeks.add(date.fromisoformat(match.group(1)))
    return weeks


def _share(part, whole):
    return round(part / whole, 4) if whole else None


def collect(conn, excluded=None):
    """`excluded`: lista de exclusão {sha256: item} (ADR 0006), para dizer a causa de cada lacuna."""
    s = SCHEMA
    weeks = [r[0] for r in _rows(conn, f"SELECT DISTINCT week_start FROM {s}.fact_price_observation WHERE {CURRENT}")]
    (total, warnings, stations, locations), = _rows(conn, f"""
        SELECT count(*), count(*) FILTER (WHERE quality_status = 'warning'), count(DISTINCT station_id),
               count(DISTINCT location_id)
        FROM {s}.fact_price_observation WHERE {CURRENT}""")
    by_product = [{"product": p, "observations": n, "stations": st, "municipalities": m, "weeks": w}
                  for p, n, st, m, w in _rows(conn, f"""
        SELECT p.canonical_name, count(*), count(DISTINCT f.station_id), count(DISTINCT f.location_id),
               count(DISTINCT f.week_start)
        FROM {s}.fact_price_observation f JOIN {s}.dim_product p USING (product_id)
        WHERE f.{CURRENT} GROUP BY 1 ORDER BY 2 DESC""")]
    by_year = [{"year": int(y), "observations": n, "weeks": w} for y, n, w in _rows(conn, f"""
        SELECT extract(year FROM week_start), count(*), count(DISTINCT week_start)
        FROM {s}.fact_price_observation WHERE {CURRENT} GROUP BY 1 ORDER BY 1""")]
    municipalities = _rows(conn, f"""
        SELECT l.municipality_name_normalized, count(DISTINCT f.week_start)
        FROM {s}.fact_price_observation f JOIN {s}.dim_location l USING (location_id)
        WHERE f.{CURRENT} GROUP BY 1""")
    regions = {}
    for name, n_weeks in municipalities:
        region = LABELS[region_of(name)]
        regions.setdefault(region, {"municipalities": 0, "weeks_median": []})
        regions[region]["municipalities"] += 1
        regions[region]["weeks_median"].append(n_weeks)
    for value in regions.values():
        ordered = sorted(value["weeks_median"])
        value["weeks_median"] = ordered[len(ordered) // 2]
    (cells, thin, med_st, p10_st, p90_st), = _rows(conn, f"""
        SELECT count(*), count(*) FILTER (WHERE station_count < 3),
               percentile_disc(0.5) WITHIN GROUP (ORDER BY station_count),
               percentile_disc(0.1) WITHIN GROUP (ORDER BY station_count),
               percentile_disc(0.9) WITHIN GROUP (ORDER BY station_count)
        FROM {s}.mart_weekly_city_price""")
    brands = _rows(conn, f"""
        SELECT coalesce(st.brand, 'SEM BANDEIRA'), count(*) FROM {s}.fact_price_observation f
        JOIN {s}.dim_station st USING (station_id) WHERE f.{CURRENT} GROUP BY 1 ORDER BY 2 DESC""")
    flags = dict(_rows(conn, f"""
        SELECT flag, count(*) FROM (SELECT unnest(quality_flags) flag FROM {s}.fact_price_observation
        WHERE {CURRENT}) x GROUP BY 1"""))
    quarantine = dict(_rows(conn, f"""
        SELECT reason, count(*) FROM (SELECT unnest(reasons) reason FROM {s}.quarantine_observation
        WHERE is_current) x GROUP BY 1"""))
    (superseded,), = _rows(conn, f"SELECT count(*) FROM {s}.fact_price_observation WHERE NOT {CURRENT}")
    files = [{"kinds": "+".join(k) or "sem_tabela", "files": n, "revised": r}
             for k, n, r in _rows(conn, f"""
        SELECT kinds, count(*), count(*) FILTER (WHERE revision > 1) FROM {s}.source_file WHERE is_current
        GROUP BY 1 ORDER BY 2 DESC""")]
    external = [{"source_id": sid, "publisher": pub, "license": lic, "rows": n,
                 "first_period": a.isoformat(), "last_period": b.isoformat()}
                for sid, pub, lic, n, a, b in _rows(conn, f"""
        SELECT e.source_id, src.publisher, src.license, count(*), min(e.period_start), max(e.period_end)
        FROM {s}.external_observation e JOIN {s}.external_source src USING (source_id) GROUP BY 1, 2, 3 ORDER BY 1""")]
    top = brands[:6]
    return {
        "coverage": {"first_week": min(weeks).isoformat(), "last_week": max(weeks).isoformat(),
                     "weeks_with_data": len(weeks),
                     "weeks_in_range": (max(weeks) - min(weeks)).days // 7 + 1,
                     "gaps": [[a.isoformat(), b.isoformat(), cause]
                              for a, b, cause in gaps(weeks, defective_weeks(excluded or {}))],
                     "municipalities": locations, "stations": stations, "uf": "SP"},
        "observations": {"current": total, "with_warning": warnings, "warning_share": _share(warnings, total),
                         "flags": flags, "superseded_by_revision": superseded, "quarantined": quarantine},
        "by_product": by_product, "by_year": by_year, "regions": regions,
        "sample": {"municipality_weeks": cells, "stations_median": med_st, "stations_p10": p10_st,
                   "stations_p90": p90_st, "thin_cells_lt3": thin, "thin_share": _share(thin, cells)},
        "brands": {"top": [{"brand": b, "observations": n, "share": _share(n, total)} for b, n in top],
                   "other_share": _share(total - sum(n for _, n in top), total)},
        "source_files": files, "external": external,
    }


def sources(conn, excluded=None):
    """Arquivos de origem (ANP e externos): caminho em raw, SHA-256, tamanho, URL e data do download.

    Os arquivos da lista de exclusão que nunca entraram no banco aparecem com vigente = "excluido"."""
    s = SCHEMA
    rows = [("anp_lpc", period, rev, current, sha, size, url or "", retrieved.isoformat() if retrieved else "", uri)
            for period, rev, current, sha, size, url, retrieved, uri in _rows(conn, f"""
        SELECT period_key, revision, is_current, sha256, size_bytes, source_url, retrieved_at, storage_uri
        FROM {s}.source_file ORDER BY period_key, revision""")]
    rows += [(sid, name, "", True, sha, "", url, retrieved.isoformat(), "raw/" + path)
             for sid, name, sha, url, retrieved, path in _rows(conn, f"""
        SELECT source_id, name, sha256, url, retrieved_at, raw_path FROM {s}.external_file
        ORDER BY source_id, name, retrieved_at""")]
    listed = {row[4] for row in rows}
    rows += [("anp_lpc", item["file"], "", "excluido", sha, "", "", "", "")
             for sha, item in sorted((excluded or {}).items(), key=lambda kv: kv[1]["file"]) if sha not in listed]
    header = ("fonte", "periodo_ou_nome", "revisao", "vigente", "sha256", "bytes", "url", "baixado_em", "caminho")
    return header, rows


def _n(value, lang):
    text = f"{value:,}"
    return text.replace(",", ".") if lang == "pt" else text


def _pct(value, lang):
    text = f"{100 * value:.1f}%"
    return text.replace(".", ",") if lang == "pt" else text


def _date(iso, lang):
    d = date.fromisoformat(iso)
    return d.strftime("%d/%m/%Y") if lang == "pt" else d.isoformat()


TEXT = {
    "pt": {
        "title": "Ficha do conjunto de dados",
        "intro": "Gerada por `scripts/dataset_card.py` a partir do banco; os números não são digitados à mão. "
                 "Dados detalhados em `reports/dataset/ficha.json`; arquivos de origem com SHA-256 em "
                 "`reports/dataset/fontes.csv`.",
        "origin_h": "Origem",
        "origin": "Levantamento de Preços de Combustíveis (LPC) da ANP, arquivos semanais por posto revendedor, "
                  "mais os históricos publicados pela ANP para o período anterior. Fontes externas: dólar (Banco "
                  "Central, SGS 1) e preços de produtores e de distribuição da ANP.",
        "coverage_h": "Cobertura",
        "coverage": "Estado de São Paulo, de {first} a {last}: {weeks} semanas com dado de {range} no intervalo, "
                    "{municipalities} municípios e {stations} postos. {current} observações vigentes.",
        "gaps": "Semanas sem dado, nunca preenchidas: {missing} semanas sem arquivo na página da ANP ({no_file}) e "
                "{defect} semanas com arquivo da ANP com defeito, fora por decisão registrada em "
                "`config/excluded_sources.json`, com o motivo de cada um: planilhas que o leitor não abre ou que "
                "trazem resumos no lugar dos postos ({bad}).",
        "no_gaps": "Nenhuma semana sem dado no intervalo.",
        "product_h": "Por combustível",
        "product_cols": "| Combustível | Observações | Postos | Municípios | Semanas |",
        "year_h": "Por ano",
        "year_cols": "| Ano | Observações | Semanas |",
        "region_h": "Por região",
        "region_cols": "| Região | Municípios | Semanas com dado (mediana) |",
        "sample_h": "Tamanho da amostra",
        "sample": "Em cada município e semana, a mediana é de {median} postos pesquisados (10% dos casos com até "
                  "{p10}, 10% com {p90} ou mais). {thin} das {cells} combinações de município e semana "
                  "({share}) têm menos de 3 postos e são tratadas como série fraca.",
        "quality_h": "Qualidade",
        "quality": "{warn} observações ({warn_share}) têm aviso ({flags}); "
                   "ficam no banco e entram nas medianas. {superseded} linhas não são vigentes porque outro "
                   "arquivo da ANP traz o mesmo dado (revisão ou precedência entre fontes, ADR 0002). Em quarentena (fora das contas): {quarantine}.",
        "brands_h": "Bandeiras",
        "brands": "Participação nas observações: {brands}; demais, {other}.",
        "external_h": "Fontes externas",
        "external_cols": "| Fonte | Publicador | Licença | Linhas | Período |",
        "bias_h": "Vieses e limitações",
        "bias": [
            "A ANP pesquisa uma **amostra** de postos, não todos; municípios pequenos têm poucos postos e "
            "séries irregulares.",
            "A amostra muda de semana para semana; a mediana de um município pode variar por troca de postos, "
            "não só de preço.",
            "Preço de venda ao consumidor; o preço de compra é raro e não é usado.",
            "Lacunas de publicação ficam como lacunas: nada é interpolado.",
            "Bandeira é a declarada no arquivo da semana; trocas de bandeira ao longo do tempo não são "
            "reconstruídas.",
        ],
        "privacy_h": "Privacidade e licenças",
        "privacy": [
            "Os arquivos da ANP trazem CNPJ, razão social e endereço. O banco local guarda esses campos; o "
            "pacote público do demonstrativo e os relatórios **não** trazem CNPJ nem razão social.",
            "Dados da ANP reproduzidos sem fins lucrativos, com citação e link, conforme os termos de uso do "
            "portal gov.br. O dólar (ODbL) entra no banco, mas não no pacote público.",
            "Os arquivos brutos não estão no repositório; `fontes.csv` lista o SHA-256 de cada um e a URL dos "
            "baixados pelo projeto (os históricos e agregados obtidos à mão no Marco 1 não têm URL registrada).",
        ],
    },
    "en": {
        "title": "Dataset card",
        "intro": "Generated by `scripts/dataset_card.py` from the database; no number is typed by hand. "
                 "Details in `reports/dataset/ficha.json`; source files with SHA-256 in "
                 "`reports/dataset/fontes.csv`.",
        "origin_h": "Origin",
        "origin": "ANP's fuel price survey (Levantamento de Preços de Combustíveis, LPC), weekly files by retail "
                  "station, plus ANP's historical releases for the earlier period. External sources: US dollar "
                  "rate (Central Bank of Brazil, SGS 1) and ANP producer and distributor prices.",
        "coverage_h": "Coverage",
        "coverage": "State of São Paulo, from {first} to {last}: {weeks} weeks with data out of {range} in the "
                    "range, {municipalities} municipalities and {stations} stations. {current} current "
                    "observations.",
        "gaps": "Weeks without data, never filled: {missing} weeks with no file on ANP's page ({no_file}) and "
                "{defect} weeks whose ANP file is defective, left out by a recorded decision in "
                "`config/excluded_sources.json`, each with its reason: spreadsheets the reader cannot open or that "
                "hold summaries instead of stations ({bad}).",
        "no_gaps": "No week without data in the range.",
        "product_h": "By fuel",
        "product_cols": "| Fuel | Observations | Stations | Municipalities | Weeks |",
        "year_h": "By year",
        "year_cols": "| Year | Observations | Weeks |",
        "region_h": "By region",
        "region_cols": "| Region | Municipalities | Weeks with data (median) |",
        "sample_h": "Sample size",
        "sample": "In each municipality and week, the median is {median} surveyed stations (10% of cases with "
                  "{p10} or fewer, 10% with {p90} or more). {thin} of the {cells} municipality-week cells "
                  "({share}) have fewer than 3 stations and are treated as weak series.",
        "quality_h": "Quality",
        "quality": "{warn} observations ({warn_share}) carry a warning ({flags}); "
                   "they stay in the database and in the medians. {superseded} rows are not current because another "
                   "ANP file holds the same data (revision or precedence between sources, ADR 0002). Quarantined (left out): {quarantine}.",
        "brands_h": "Brands",
        "brands": "Share of observations: {brands}; others, {other}.",
        "external_h": "External sources",
        "external_cols": "| Source | Publisher | License | Rows | Period |",
        "bias_h": "Biases and limitations",
        "bias": [
            "ANP surveys a **sample** of stations, not all of them; small municipalities have few stations and "
            "irregular series.",
            "The sample changes from week to week; a municipality's median can move because the stations "
            "changed, not only the prices.",
            "Retail sale price; purchase price is rare and not used.",
            "Publication gaps stay as gaps: nothing is interpolated.",
            "The brand is the one declared in each week's file; brand changes over time are not "
            "reconstructed.",
        ],
        "privacy_h": "Privacy and licenses",
        "privacy": [
            "ANP files include the station's tax id (CNPJ), legal name and address. The local database keeps "
            "them; the public demo package and the reports do **not** include tax id or legal name.",
            "ANP data reproduced for non-commercial purposes, with citation and link, under the gov.br portal "
            "terms of use. The dollar series (ODbL) is in the database but not in the public package.",
            "Raw files are not in the repository; `fontes.csv` lists each one's SHA-256 and the URL of those "
            "downloaded by the project (historical and aggregate files obtained by hand in milestone 1 have no "
            "recorded URL).",
        ],
    },
}

QUARANTINE_NAMES = {"pt": {"conflito_de_preco_mesma_chave": "preços diferentes para a mesma chave"},
                    "en": {"conflito_de_preco_mesma_chave": "different prices for the same key"}}
FLAG_NAMES = {"pt": {"preco_extremo": "preço extremo para o combustível"},
              "en": {"preco_extremo": "extreme price for the fuel"}}
REGION_NAMES_EN = {"Capital": "Capital", "Região metropolitana": "Metropolitan area", "Litoral": "Coast",
                   "Interior": "Inland"}


def markdown(card, lang):
    t, c, o = TEXT[lang], card["coverage"], card["observations"]
    n, pct, dt = (lambda v: _n(v, lang)), (lambda v: _pct(v, lang)), (lambda v: _date(v, lang))
    lines = [f"# {t['title']}", "", t["intro"], "", f"## {t['origin_h']}", "", t["origin"], "",
             f"## {t['coverage_h']}", "",
             t["coverage"].format(first=dt(c["first_week"]), last=dt(c["last_week"]), weeks=n(c["weeks_with_data"]),
                                  range=n(c["weeks_in_range"]), municipalities=n(c["municipalities"]),
                                  stations=n(c["stations"]), current=n(o["current"])), ""]
    if c["gaps"]:
        def spans(cause):
            return "; ".join(dt(a) if a == b else f"{dt(a)} – {dt(b)}" for a, b, kind in c["gaps"] if kind == cause)

        def count(cause):
            return sum((date.fromisoformat(b) - date.fromisoformat(a)).days // 7 + 1
                       for a, b, kind in c["gaps"] if kind == cause)
        lines += [t["gaps"].format(missing=count("sem_arquivo"), no_file=spans("sem_arquivo"),
                                   defect=count("defeito"), bad=spans("defeito")), ""]
    else:
        lines += [t["no_gaps"], ""]
    lines += [f"### {t['product_h']}", "", t["product_cols"], "|---|---:|---:|---:|---:|"]
    lines += [f"| {p['product']} | {n(p['observations'])} | {n(p['stations'])} | {n(p['municipalities'])} | "
              f"{n(p['weeks'])} |" for p in card["by_product"]]
    lines += ["", f"### {t['year_h']}", "", t["year_cols"], "|---|---:|---:|"]
    lines += [f"| {y['year']} | {n(y['observations'])} | {n(y['weeks'])} |" for y in card["by_year"]]
    lines += ["", f"### {t['region_h']}", "", t["region_cols"], "|---|---:|---:|"]
    for region, r in card["regions"].items():
        name = region if lang == "pt" else REGION_NAMES_EN.get(region, region)
        lines.append(f"| {name} | {n(r['municipalities'])} | {n(r['weeks_median'])} |")
    s = card["sample"]
    lines += ["", f"## {t['sample_h']}", "",
              t["sample"].format(median=s["stations_median"], p10=s["stations_p10"], p90=s["stations_p90"],
                                 thin=n(s["thin_cells_lt3"]), cells=n(s["municipality_weeks"]),
                                 share=pct(s["thin_share"])), ""]
    quarantine = ", ".join(f"{n(v)} ({QUARANTINE_NAMES[lang].get(k, k)})" for k, v in sorted(o["quarantined"].items())) \
        or ("nenhuma" if lang == "pt" else "none")
    lines += [f"## {t['quality_h']}", "",
              t["quality"].format(warn=n(o["with_warning"]), warn_share=pct(o["warning_share"]),
                                  flags=", ".join(f"{FLAG_NAMES[lang].get(k, k)}: {n(v)}" for k, v in sorted(o["flags"].items())),
                                  superseded=n(o["superseded_by_revision"]), quarantine=quarantine), ""]
    brands = ", ".join(f"{b['brand']} {pct(b['share'])}" for b in card["brands"]["top"])
    lines += [f"## {t['brands_h']}", "", t["brands"].format(brands=brands, other=pct(card["brands"]["other_share"])), ""]
    lines += [f"## {t['external_h']}", "", t["external_cols"], "|---|---|---|---:|---|"]
    lines += [f"| {e['source_id']} | {e['publisher']} | {e['license']} | {n(e['rows'])} | "
              f"{dt(e['first_period'])} – {dt(e['last_period'])} |" for e in card["external"]]
    lines += ["", f"## {t['bias_h']}", ""] + [f"- {item}" for item in t["bias"]]
    lines += ["", f"## {t['privacy_h']}", ""] + [f"- {item}" for item in t["privacy"]]
    return "\n".join(lines) + "\n"
