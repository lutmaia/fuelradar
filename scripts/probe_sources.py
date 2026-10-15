"""Testa se as fontes respondem a partir desta máquina, sem guardar nada (Marco 12, etapa B2).

Uso: python scripts/probe_sources.py [--only anp|externas]

Lê a página semanal da ANP, baixa o arquivo por revenda mais recente e cada fonte externa para uma
pasta temporária, confere o formato e imprime tamanho, SHA-256 e tempo. Tudo é apagado no fim: o
objetivo é só saber se o servidor do CI consegue baixar (a ANP pode bloquear faixas de IP). O
SHA-256 permite comparar com o arquivo baixado localmente. Sai com 1 se alguma fonte falhar.
"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radar_combustiveis.external import fetch as external  # noqa: E402
from radar_combustiveis.ingestion.download import (  # noqa: E402
    DEFAULT_PAGE, DownloadError, check_expected_content, fetch_to_file, parse_weekly_links)


def probe(name, url, folder, check):
    start = time.monotonic()
    try:
        info = fetch_to_file(url, Path(folder) / name, timeout=60, retries=3)
        check(name, info["head"])
    except DownloadError as exc:
        print(f"FALHOU  {name}: {exc} ({time.monotonic() - start:.1f} s)")
        return None
    print(f"ok      {name}: {info['size_bytes']} bytes, sha256 {info['sha256']} ({time.monotonic() - start:.1f} s)")
    return info


def anp(folder):
    page = probe("pagina.html", DEFAULT_PAGE, folder, lambda name, head: None)
    if page is None:
        return False
    links = parse_weekly_links((Path(folder) / "pagina.html").read_text(encoding="utf-8", errors="replace"))
    if not links:
        print("FALHOU  nenhum link de revendas_lpc na página (bloqueio ou página mudou)")
        return False
    latest = max(links, key=lambda link: link.week_start)
    print(f"        {len(links)} semanas listadas; mais recente {latest.week_start} (atualizado em {latest.page_updated_on})")
    return probe(latest.filename, latest.url, folder, check_expected_content) is not None


def externals(folder):
    results = [probe(name, url, folder, external.check_content) is not None
               for _, name, url in external.targets(datetime.now(timezone.utc).date())]
    return all(results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["anp", "externas"])
    args = parser.parse_args(argv)
    ok = True
    with tempfile.TemporaryDirectory() as folder:
        if args.only in (None, "anp"):
            ok &= anp(folder)
        if args.only in (None, "externas"):
            ok &= externals(folder)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
