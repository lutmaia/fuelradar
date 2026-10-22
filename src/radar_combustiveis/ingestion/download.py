"""Descoberta e download das semanas por revenda da ANP, só com a biblioteca padrão.

O arquivo baixado vai primeiro para uma pasta temporária fora de data/raw. Só entra em
data/raw/downloads/<recebimento>/ se for conteúdo novo (SHA-256 ainda desconhecido) e tiver
o formato esperado; nunca sobrescreve nada. Falhas não publicam nada e ficam no registro
data/processed/downloads.jsonl (um evento por tentativa, só acrescenta).
"""

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request

USER_AGENT = "radar-combustiveis/0.1 (projeto de portfolio; leitura de dados abertos da ANP)"
DEFAULT_PAGE = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/"
                "levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas")
ALLOWED_HOST_SUFFIX = ".gov.br"
MAX_BYTES = 300 * 1024 * 1024
RETRY_STATUS = {429, 500, 502, 503, 504}
ZIP_MAGIC = b"PK\x03\x04"

# A ANP usa revendas_lpc_2026-10-04_2026-10-10.xlsx e, desde out/2026, também
# revendas_lpc_2026_10_11-2026_10_17.xlsx; as datas saem sempre em ISO.
_WEEKLY_LINK = re.compile(
    r'href="(https://[^"/]+/[^"]*?/arquivos-lpc/\d{4}/'
    r'(revendas_lpc_(\d{4}[-_]\d{2}[-_]\d{2})[-_](\d{4}[-_]\d{2}[-_]\d{2})\.xlsx))"[^>]*>[^<]*</a>'
    r'\s*(?:<em>\s*\(Atualizado em (\d{1,2})/(\d{1,2})/(\d{4})\)\s*</em>)?')


class DownloadError(Exception):
    """Falha definitiva ou esgotamento das tentativas; nada foi publicado."""


class RetryableError(Exception):
    pass


@dataclass(frozen=True)
class WeeklyLink:
    url: str
    filename: str
    week_start: str
    week_end: str
    page_updated_on: str | None


def parse_weekly_links(html):
    """Extrai os links `revendas_lpc_*.xlsx` (com a data "Atualizado em", se houver) da página."""
    links = {}
    for match in _WEEKLY_LINK.finditer(html):
        url, filename, start, end, day, month, year = match.groups()
        host = url.split("/")[2]
        if not host.endswith(ALLOWED_HOST_SUFFIX):
            continue
        updated = None
        if day:
            try:
                updated = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                updated = None
        links[url] = WeeklyLink(url, filename, start.replace("_", "-"), end.replace("_", "-"), updated)
    return sorted(links.values(), key=lambda link: (link.week_start, link.url))


def select_links(links, since=None, until=None):
    """Filtra pelo início da semana (datas ISO, inclusivas)."""
    return [link for link in links
            if (since is None or link.week_start >= since) and (until is None or link.week_start <= until)]


def fetch_to_file(url, dest, *, timeout=60, retries=3, backoff=2.0, sleep=time.sleep, max_bytes=MAX_BYTES):
    """Baixa `url` para `dest` com tentativas e espera exponencial. Devolve dados do conteúdo."""
    last = None
    for attempt in range(1, retries + 1):
        try:
            return _fetch_once(url, dest, timeout, max_bytes)
        except RetryableError as exc:
            last = exc
            if attempt < retries:
                sleep(backoff * 2 ** (attempt - 1))
    raise DownloadError(f"{last} (após {retries} tentativas)")


def _fetch_once(url, dest, timeout, max_bytes):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest, size, head = hashlib.sha256(), 0, b""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as stream:
            expected = response.headers.get("Content-Length")
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise DownloadError(f"Resposta maior que o limite de {max_bytes} bytes")
                if not head:
                    head = chunk[:8]
                digest.update(chunk)
                stream.write(chunk)
            if expected is not None and expected.isdigit() and int(expected) != size:
                raise RetryableError(f"Download incompleto: {size} de {expected} bytes")
            content_type, status = response.headers.get("Content-Type"), response.status
    except urllib.error.HTTPError as exc:
        exc.close()  # libera a conexão; o corpo do erro não é usado
        if exc.code in RETRY_STATUS:
            raise RetryableError(f"HTTP {exc.code}") from exc
        raise DownloadError(f"HTTP {exc.code} em {url}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
        raise RetryableError(f"{type(exc).__name__}: {exc}") from exc
    if size == 0:
        raise DownloadError("Resposta vazia")
    return {"sha256": digest.hexdigest(), "size_bytes": size, "content_type": content_type,
            "http_status": status, "head": head}


def check_expected_content(filename, head):
    """Rejeita páginas de erro com status 200: XLSX/ZIP começam com PK; CSV não pode ser HTML."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".xlsx", ".zip"} and not head.startswith(ZIP_MAGIC):
        raise DownloadError(f"Conteúdo não parece {suffix.upper()[1:]} (início {head[:4]!r})")
    if suffix == ".csv" and head.lstrip().startswith(b"<"):
        raise DownloadError("Conteúdo parece HTML, não CSV")


def read_log(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_log(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def needs_fetch(link, records):
    """Baixa se a URL nunca foi obtida com sucesso ou se a data "Atualizado em" da página mudou."""
    done = [r for r in records if r["url"] == link.url and r["action"] in {"saved", "duplicate"}]
    return not done or (link.page_updated_on is not None and done[-1].get("page_updated_on") != link.page_updated_on)


def known_files(manifest_files, records):
    """sha256 -> caminho relativo a raw, do manifesto e dos downloads já salvos."""
    known = {e["sha256"]: e["paths"][0] for e in manifest_files}
    for record in records:
        if record["action"] == "saved":
            known.setdefault(record["sha256"], record["raw_path"])
    return known


def download_links(links, raw_dir, log_path, known, *, now, force=False, **fetch_options):
    """Baixa os links necessários e devolve um relatório. `now` é injetado para testes."""
    raw_dir = Path(raw_dir).resolve()
    if not raw_dir.is_dir():
        raise ValueError(f"Pasta raw inexistente: {raw_dir}")
    records = read_log(log_path)
    known = {**known_files([], records), **known}  # inclui o que downloads anteriores já guardaram
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    report = {"retrieved_at": now.isoformat(timespec="seconds"), "saved": [], "duplicate": [],
              "skipped": [], "errors": []}
    for link in links:
        if not force and not needs_fetch(link, records):
            report["skipped"].append(link.url)
            continue
        record = {"url": link.url, "retrieved_at": now.isoformat(timespec="seconds"),
                  "page_updated_on": link.page_updated_on}
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / link.filename
            try:
                info = fetch_to_file(link.url, temp, **fetch_options)
                check_expected_content(link.filename, info["head"])
            except DownloadError as exc:
                record.update(action="error", error=str(exc))
                report["errors"].append({"url": link.url, "error": str(exc)})
            else:
                record.update(sha256=info["sha256"], size_bytes=info["size_bytes"],
                              content_type=info["content_type"], http_status=info["http_status"])
                if info["sha256"] in known:
                    record.update(action="duplicate", raw_path=known[info["sha256"]])
                    report["duplicate"].append(link.url)
                else:
                    destination = raw_dir / "downloads" / f"retrieved_at={stamp}" / link.filename
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    problem = None
                    try:
                        with open(temp, "rb") as source, open(destination, "xb") as target:  # 'x': nunca sobrescreve
                            shutil.copyfileobj(source, target)
                    except FileExistsError:
                        problem = f"Destino já existe e não será sobrescrito: {destination.name}"
                    else:
                        if hashlib.sha256(destination.read_bytes()).hexdigest() != info["sha256"]:
                            destination.unlink()
                            problem = "Cópia para raw divergiu do download"
                    if problem:
                        record.update(action="error", error=problem)
                        report["errors"].append({"url": link.url, "error": problem})
                    else:
                        raw_path = destination.relative_to(raw_dir).as_posix()
                        known[info["sha256"]] = raw_path
                        record.update(action="saved", raw_path=raw_path)
                        report["saved"].append({"url": link.url, "raw_path": raw_path,
                                                "size_bytes": info["size_bytes"]})
        append_log(log_path, record)
        records.append(record)
    return report


def parse_iso_date(text):
    return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
