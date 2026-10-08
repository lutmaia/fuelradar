"""Leitura de CSV, XLSX e ZIP da ANP, somente leitura, com cabeçalho identificado por conteúdo."""

import csv
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import tempfile
from typing import Iterator
from zipfile import ZipFile

from openpyxl import load_workbook

from .normalize import normalize_text


class SourceFormatError(ValueError):
    """Arquivo ou esquema não interpretável com as regras conhecidas."""


ALIASES = {
    "UF": "uf", "ESTADO": "uf", "ESTADOS": "uf", "ESTADO - SIGLA": "uf",
    "MUNICIPIO": "municipality", "PRODUTO": "product", "BANDEIRA": "brand",
    "UNIDADE DE MEDIDA": "unit", "CNPJ": "cnpj", "CNPJ DA REVENDA": "cnpj",
    "DATA DA COLETA": "collection_date", "DATA DE COLETA": "collection_date",
    "PRECO DE REVENDA": "sale_price", "VALOR DE VENDA": "sale_price",
    "MES": "reference_month", "DATA INICIAL": "period_start", "DATA FINAL": "period_end",
    "REGIAO": "region", "BRASIL": "country", "PRECO MEDIO REVENDA": "mean_sale_price",
    "NUMERO DE POSTOS PESQUISADOS": "reported_station_count",
    "REGIAO - SIGLA": "region", "CEP": "postal_code",
    "REVENDA": "legal_name", "RAZAO": "legal_name", "FANTASIA": "trade_name",
    "NOME DA RUA": "address", "ENDERECO": "address",
    "NUMERO RUA": "address_number", "NUMERO": "address_number",
    "COMPLEMENTO": "address_complement", "BAIRRO": "neighborhood",
    "VALOR DE COMPRA": "purchase_price",
}


def identify_header(rows):
    """Consome até o cabeçalho e devolve linha, nomes, mapeamento e tipo."""
    for number, row in enumerate(rows, 1):
        if number > 50:
            break
        names = list(row)
        while names and names[-1] is None:
            names.pop()
        keys = [ALIASES.get(normalize_text(v)) for v in names]
        if "product" not in keys:
            continue
        if "cnpj" in keys or "sale_price" in keys or "collection_date" in keys:
            required = {"product", "uf", "municipality", "cnpj", "unit", "sale_price", "collection_date"}
            kind = "retail_observation"
        elif "reference_month" in keys:
            required = {"product", "unit", "mean_sale_price", "reference_month", "reported_station_count"}
            kind = "monthly_aggregate"
        elif "period_start" in keys:
            required = {"product", "unit", "mean_sale_price", "period_start", "period_end", "reported_station_count"}
            kind = "weekly_aggregate"
        else:
            raise SourceFormatError("Cabeçalho com PRODUTO, mas sem data/preço reconhecíveis")
        missing = required - set(keys)
        if missing:
            raise SourceFormatError(f"Cabeçalho na linha {number}: colunas obrigatórias ausentes: {sorted(missing)}")
        if kind != "retail_observation" and not set(keys) & {"uf", "region", "country", "municipality"}:
            raise SourceFormatError("Agregado sem dimensão geográfica reconhecida")
        if any(v is None for v in names) or len(set(map(normalize_text, names))) != len(names):
            raise SourceFormatError("Cabeçalho com coluna sem nome ou nome duplicado")
        return number, [str(v) for v in names], {k: i for i, k in enumerate(keys) if k}, kind
    raise SourceFormatError("Cabeçalho ANP não identificado nas primeiras 50 linhas")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


CSV_DELIMITERS = ";,\t|"


def detect_csv_format(stream):
    """Devolve (codificação, dialeto) a partir dos primeiros 64 KiB e reposiciona o fluxo."""
    sample = stream.read(65536)
    stream.seek(0)
    try:
        decoded = sample.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        decoded = sample.decode("cp1252")
        encoding = "cp1252"
    # O Sniffer falha em amostras pequenas ou irregulares: o delimitador é o mais frequente no cabeçalho.
    header = next((line for line in decoded.splitlines() if line.strip()), "")
    delimiter = max(CSV_DELIMITERS, key=header.count)
    if header.count(delimiter) == 0:
        raise SourceFormatError("Delimitador CSV não identificado")
    return encoding, type("Dialect", (csv.excel,), {"delimiter": delimiter})


def iter_zip_members(path):
    """Gera (nome, fluxo) de cada CSV/XLSX do ZIP, sem extrair para disco nem aninhar ZIPs."""
    with ZipFile(path) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if not members or any(Path(m.filename).suffix.lower() not in {".csv", ".xlsx"} for m in members):
            raise SourceFormatError("ZIP com conteúdo inesperado: esperado somente CSV ou XLSX, sem ZIP aninhado")
        for member in members:
            with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as stream:
                with archive.open(member) as source:
                    while chunk := source.read(1024 * 1024):
                        stream.write(chunk)
                stream.seek(0)
                yield member.filename, stream


@dataclass
class Table:
    """Uma tabela de dados de um arquivo. `rows` gera (número, valores) já alinhados ao cabeçalho.

    O número é a linha física no XLSX e o registro lógico no CSV. Linhas vazias são omitidas.
    Consuma `rows` por completo antes de pedir a próxima tabela de `iter_tables`.
    """

    member: str | None
    sheet: str | None
    kind: str
    header_row: int
    headers: list
    mapping: dict
    rows: Iterator


def _aligned_rows(rows, first_number, width):
    for number, row in enumerate(rows, first_number):
        if all(v is None or v == "" for v in row):
            continue
        if len(row) > width and any(v is not None and v != "" for v in row[width:]):
            raise SourceFormatError(f"Linha {number}: valores fora das colunas nomeadas")
        yield number, tuple(row[:width]) + (None,) * max(0, width - len(row))


def _table(rows, member, sheet):
    rows = iter(rows)
    header_row, headers, mapping, kind = identify_header(rows)
    return Table(member, sheet, kind, header_row, headers, mapping,
                 _aligned_rows(rows, header_row + 1, len(headers)))


def _xlsx_tables(source, member):
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        for sheet in workbook:
            # Não confiar em dimensões Excel, que podem conter somente formatação.
            sheet.reset_dimensions()
            try:
                yield _table(sheet.iter_rows(values_only=True), member, sheet.title)
            except (ValueError, TypeError) as exc:
                raise SourceFormatError(f"Planilha {sheet.title}: {exc}") from exc
    finally:
        workbook.close()


def _csv_tables(stream, member):
    encoding, dialect = detect_csv_format(stream)
    wrapper = io.TextIOWrapper(stream, encoding=encoding, newline="")
    try:
        yield _table(csv.reader(wrapper, dialect), member, None)
    finally:
        wrapper.detach()


def iter_tables(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        yield from _xlsx_tables(path, None)
    elif suffix == ".csv":
        with path.open("rb") as stream:
            yield from _csv_tables(stream, None)
    elif suffix == ".zip":
        for name, stream in iter_zip_members(path):
            if name.lower().endswith(".xlsx"):
                yield from _xlsx_tables(stream, name)
            else:
                yield from _csv_tables(stream, name)
    else:
        raise SourceFormatError(f"Formato não suportado: {suffix}; use XLSX, CSV ou ZIP")
