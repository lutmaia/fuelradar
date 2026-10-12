"""CSV para download. Formato pensado para o Excel em português: `;` e vírgula decimal, com BOM."""

import csv
import io

from .formatting import decimal_br


def _csv(header, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _num(value, decimals=4):
    return "" if value is None else decimal_br(value, decimals)


def history_csv(history):
    location, product = history["location"], history["product"]
    rows = []
    for item in history["items"]:
        s, sample, change = item["statistics"], item["sample"], item["weekly_change"]
        rows.append([
            item["week_start"], item["week_end"], location["municipality"] or "ESTADO", location["uf"], product,
            _num(s["min"]), _num(s["p25"]), _num(s["median"]), _num(s["mean"]), _num(s["p75"]), _num(s["max"]),
            _num(s["stddev"]), sample["observations"], sample["stations"], sample["coverage_status"],
            _num(change["value"]), change["reason"] or ""])
    return _csv(["semana_inicio", "semana_fim", "municipio", "uf", "produto", "minimo", "p25", "mediana", "media",
                 "p75", "maximo", "desvio_padrao", "observacoes", "postos", "status_cobertura", "variacao_semanal",
                 "motivo_sem_variacao"], rows)


def stations_csv(stations, product):
    rows = [[s["cnpj"], s["name"] or "", s["legal_name"] or "", s["brand"] or "", s["address"] or "",
             s["neighborhood"] or "", s["postal_code"] or "", s["municipality"], s["uf"], product,
             _num(s["latest_price"], 3), s["latest_price_date"] or "", ";".join(s["latest_price_flags"])]
            for s in stations]
    return _csv(["cnpj", "nome", "razao_social", "bandeira", "endereco", "bairro", "cep", "municipio", "uf",
                 "produto", "ultimo_preco", "data_ultimo_preco", "avisos"], rows)
