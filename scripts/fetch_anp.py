"""Descobre e baixa as semanas por revenda da ANP para data/raw/downloads/.

Uso:
  python scripts/fetch_anp.py --since 2026-07-01 --dry-run   # só lista o que seria baixado
  python scripts/fetch_anp.py --since 2026-07-01 --ingest    # baixa e roda a ingestão local

Só baixa conteúdo novo (SHA-256 desconhecido) e nunca sobrescreve. Sem --force, não repete
URLs já obtidas, exceto quando a data "Atualizado em" da página mudou (possível revisão).
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
# Sem instalação do pacote, o script enxerga `src` por este caminho (docs/decisions/0001).
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.config import load_target_ufs  # noqa: E402
from radar_combustiveis.ingestion.download import (  # noqa: E402
    ALLOWED_HOST_SUFFIX, DEFAULT_PAGE, DownloadError, WeeklyLink, download_links, fetch_to_file,
    known_files, needs_fetch, parse_iso_date, parse_weekly_links, read_log, select_links,
)
from radar_combustiveis.ingestion.manifest import load_manifest  # noqa: E402
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402


def explicit_link(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(ALLOWED_HOST_SUFFIX):
        raise argparse.ArgumentTypeError(f"Use uma URL https de {ALLOWED_HOST_SUFFIX}: {url}")
    name = Path(parsed.path).name
    if not name:
        raise argparse.ArgumentTypeError(f"URL sem nome de arquivo: {url}")
    return WeeklyLink(url, name, "", "", None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page", default=DEFAULT_PAGE, help="Página da ANP com os links semanais")
    parser.add_argument("--since", type=parse_iso_date, help="Início da semana mínimo (AAAA-MM-DD)")
    parser.add_argument("--until", type=parse_iso_date, help="Início da semana máximo (AAAA-MM-DD)")
    parser.add_argument("--url", action="append", type=explicit_link, default=[],
                        help="URL direta (repetível); alternativa manual quando a página mudar")
    parser.add_argument("--force", action="store_true", help="Baixar de novo mesmo URLs já obtidas")
    parser.add_argument("--dry-run", action="store_true", help="Só listar; não baixar nem gravar")
    parser.add_argument("--ingest", action="store_true", help="Rodar a ingestão local depois do download")
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--quarantine", type=Path, default=ROOT / "data" / "quarantine")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)

    log_path = args.out / "downloads.jsonl"
    if args.url:
        links = args.url
    else:
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "pagina.html"
            try:
                fetch_to_file(args.page, page, timeout=args.timeout, retries=args.retries)
            except DownloadError as exc:
                print(f"ERRO ao ler a página da ANP: {exc}\nUse --url para informar os arquivos manualmente.",
                      file=sys.stderr)
                return 1
            html = page.read_text(encoding="utf-8", errors="replace")
        links = select_links(parse_weekly_links(html), args.since, args.until)
        if not links:
            print("ERRO: nenhum link de revendas_lpc encontrado (a página pode ter mudado). "
                  "Use --url para informar os arquivos manualmente.", file=sys.stderr)
            return 1

    records = read_log(log_path)
    pending = [link for link in links if args.force or needs_fetch(link, records)]
    print(f"{len(links)} arquivo(s) selecionado(s); {len(pending)} a baixar.")
    if args.dry_run:
        for link in pending:
            print(f"  {link.filename}  (atualizado em {link.page_updated_on or 'N/D'})")
        return 0

    manifest = load_manifest(args.out / "manifest.json")
    known = known_files(manifest["files"], records)
    report = download_links(links, args.raw, log_path, known, now=datetime.now(timezone.utc),
                            force=args.force, timeout=args.timeout, retries=args.retries)
    for item in report["saved"]:
        print(f"  salvo {item['raw_path']} ({item['size_bytes']} bytes)")
    print(f"Salvos: {len(report['saved'])} | idênticos a arquivos já existentes: {len(report['duplicate'])} | "
          f"ignorados: {len(report['skipped'])} | erros: {len(report['errors'])}")
    for error in report["errors"]:
        print(f"  ERRO {error['url']}: {error['error']}", file=sys.stderr)

    code = 1 if report["errors"] else 0
    if args.ingest:
        ingestion = run_ingestion(args.raw, args.out, args.quarantine, load_target_ufs())
        for event in ingestion["events"]:
            print(f"  {event['event']}: {event['paths'][0]} (revisão {event['revision']})")
        for item in ingestion["ingested"]:
            print(f"  ingerido {item['path']}: lidas {item['rows_read']}, aceitas {item['rows_accepted']}, "
                  f"rejeitadas {item['rows_rejected']}, chaves repetidas {item['duplicate_keys']}")
        for error in ingestion["errors"]:
            print(f"  ERRO ({error['stage']}) {error['path']}: {error['error']}", file=sys.stderr)
        code = code or (1 if ingestion["errors"] else 0)
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
