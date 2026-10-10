"""Download com servidor HTTP local (biblioteca padrão); nada aqui acessa a internet."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scripts import fetch_anp  # noqa: E402
from radar_combustiveis.ingestion.download import (  # noqa: E402
    WeeklyLink, check_expected_content, DownloadError, download_links, fetch_to_file, known_files,
    needs_fetch, parse_weekly_links, read_log, select_links,
)
from radar_combustiveis.ingestion.pipeline import run_ingestion  # noqa: E402
from tests.test_ingestion import WEEKLY_HEADER, digest, weekly_row, write_xlsx  # noqa: E402

PAGE_SNIPPET = """
<p><strong>20/09/2026 a 26/09/2026</strong></p><ul>
<li><a target="_blank" href="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/2026/resumo_semanal_lpc_2026-09-20_2026-09-26.xlsx" class="internal-link">Preços médios semanais</a></li>
<li><a target="_blank" href="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/2026/revendas_lpc_2026-09-20_2026-09-26.xlsx" class="internal-link">Preços por posto revendedor</a> <em>(Atualizado em 25/9/2026)</em></li></ul>
<ul><li><a href="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/2026/revendas_lpc_2026-09-13_2026-09-19.xlsx">Preços por posto</a></li>
<li><a href="https://exemplo.com/arquivos-lpc/2026/revendas_lpc_2026-09-06_2026-09-12.xlsx">Outro domínio</a></li>
<li><a href="https://www.gov.br/anp/arquivos-lpc/2025/revendas_lpc-1.xlsx">Nome irregular</a></li></ul>
"""


class Handler(BaseHTTPRequestHandler):
    routes = {}
    hits = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            self.respond()
        except OSError:
            pass  # o cliente desistiu (teste de timeout); não é falha do servidor de teste

    def respond(self):
        script = self.routes.get(self.path)
        count = self.hits[self.path] = self.hits.get(self.path, 0) + 1
        step = script[min(count, len(script)) - 1] if script else ("status", 404)
        kind = step[0]
        if kind == "ok":
            self.send_response(200)
            self.send_header("Content-Length", str(len(step[1])))
            self.end_headers()
            self.wfile.write(step[1])
        elif kind == "status":
            self.send_response(step[1])
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif kind == "slow":
            time.sleep(step[1])
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"PK")
        elif kind == "truncated":
            self.send_response(200)
            self.send_header("Content-Length", str(len(step[1]) + 100))
            self.end_headers()
            self.wfile.write(step[1])
            self.close_connection = True


def xlsx_bytes(rows):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "x.xlsx"
        write_xlsx(path, WEEKLY_HEADER, rows)
        return path.read_bytes()


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.routes, Handler.hits = {}, {}
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.routes, Handler.hits = {}, {}
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.base = Path(folder.name)
        self.raw, self.out, self.quarantine = self.base / "raw", self.base / "processed", self.base / "quarantine"
        self.raw.mkdir()
        self.log = self.out / "downloads.jsonl"
        self.sleeps = []
        self.name = "revendas_lpc_2026-09-20_2026-09-26.xlsx"
        self.route = "/arquivos-lpc/2026/" + self.name

    def link(self, updated="2026-09-25", name=None):
        name = name or self.name
        return WeeklyLink(self.base_url + "/arquivos-lpc/2026/" + name, name, "2026-09-20", "2026-09-26", updated)

    def download(self, links, known=None, when=(2026, 10, 8, 12, 0, 0), **options):
        options.setdefault("sleep", self.sleeps.append)
        options.setdefault("backoff", 2.0)
        return download_links(links, self.raw, self.log, known or {}, now=datetime(*when, tzinfo=timezone.utc), **options)

    def raw_files(self):
        return sorted(p.relative_to(self.raw).as_posix() for p in self.raw.rglob("*") if p.is_file())

    def ingest(self):
        return run_ingestion(self.raw, self.out, self.quarantine, ("SP",))

    def manifest(self):
        return json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))


class FetchBehaviourTests(ServerCase):
    def test_saves_new_content_under_a_new_receipt_folder(self):
        content = xlsx_bytes([weekly_row()])
        Handler.routes[self.route] = [("ok", content)]
        report = self.download([self.link()])
        self.assertEqual(self.raw_files(), [f"downloads/retrieved_at=2026-10-08T12-00-00Z/{self.name}"])
        self.assertEqual((self.raw / report["saved"][0]["raw_path"]).read_bytes(), content)
        record = read_log(self.log)[0]
        self.assertEqual((record["action"], record["http_status"], record["size_bytes"], record["page_updated_on"]),
                         ("saved", 200, len(content), "2026-09-25"))
        self.assertEqual(record["retrieved_at"], "2026-10-08T12:00:00+00:00")

    def test_retries_server_errors_with_exponential_backoff(self):
        Handler.routes[self.route] = [("status", 500), ("status", 503), ("ok", xlsx_bytes([weekly_row()]))]
        report = self.download([self.link()], retries=3)
        self.assertEqual((len(report["saved"]), report["errors"]), (1, []))
        self.assertEqual(self.sleeps, [2.0, 4.0])
        self.assertEqual(Handler.hits[self.route], 3)

    def test_persistent_failure_keeps_previous_state_and_logs_error(self):
        previous = self.raw / "revendas_lpc_2026-09-13_2026-09-19.xlsx"
        previous.write_bytes(xlsx_bytes([weekly_row()]))
        before = digest(previous)
        Handler.routes[self.route] = [("status", 500)]
        report = self.download([self.link()], retries=3)
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("após 3 tentativas", report["errors"][0]["error"])
        self.assertEqual(Handler.hits[self.route], 3)
        self.assertEqual(self.raw_files(), ["revendas_lpc_2026-09-13_2026-09-19.xlsx"])
        self.assertEqual(digest(previous), before)
        self.assertEqual([r["action"] for r in read_log(self.log)], ["error"])
        # Depois de uma falha, a mesma URL volta a ser tentada.
        self.assertTrue(needs_fetch(self.link(), read_log(self.log)))

    def test_client_error_is_not_retried(self):
        Handler.routes[self.route] = [("status", 404)]
        report = self.download([self.link()], retries=3)
        self.assertIn("HTTP 404", report["errors"][0]["error"])
        self.assertEqual((Handler.hits[self.route], self.sleeps), (1, []))

    def test_timeout_is_an_error_after_retries(self):
        Handler.routes[self.route] = [("slow", 1.0)]
        report = self.download([self.link()], retries=2, timeout=0.2)
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(self.raw_files(), [])
        self.assertEqual(self.sleeps, [2.0])

    def test_html_page_with_status_200_is_rejected(self):
        Handler.routes[self.route] = [("ok", b"<html>Servico indisponivel</html>")]
        report = self.download([self.link()])
        self.assertIn("não parece XLSX", report["errors"][0]["error"])
        self.assertEqual(self.raw_files(), [])

    def test_truncated_download_is_retried_then_rejected(self):
        Handler.routes[self.route] = [("truncated", b"PK\x03\x04" + b"x" * 50)]
        report = self.download([self.link()], retries=2)
        self.assertIn("incompleto", report["errors"][0]["error"])
        self.assertEqual(self.raw_files(), [])

    def test_known_content_is_not_saved_again(self):
        content = xlsx_bytes([weekly_row()])
        Handler.routes[self.route] = [("ok", content)]
        manual = self.raw / "recebido_a_mao.xlsx"
        manual.write_bytes(content)
        self.ingest()
        known = known_files(self.manifest()["files"], [])
        report = self.download([self.link()], known=known)
        self.assertEqual((len(report["duplicate"]), report["saved"]), (1, []))
        self.assertEqual(self.raw_files(), ["recebido_a_mao.xlsx"])
        self.assertEqual(read_log(self.log)[0]["raw_path"], "recebido_a_mao.xlsx")

    def test_skips_url_already_fetched_unless_page_date_changed(self):
        Handler.routes[self.route] = [("ok", xlsx_bytes([weekly_row()]))]
        self.download([self.link()])
        again = self.download([self.link()])
        self.assertEqual((again["skipped"], Handler.hits[self.route]), ([self.link().url], 1))
        refetched = self.download([self.link(updated="2026-10-02")])
        self.assertEqual((len(refetched["duplicate"]), Handler.hits[self.route]), (1, 2))
        forced = self.download([self.link(updated="2026-10-02")], force=True)
        self.assertEqual(len(forced["duplicate"]), 1)
        self.assertEqual(Handler.hits[self.route], 3)

    def test_never_overwrites_an_existing_destination(self):
        Handler.routes[self.route] = [("ok", xlsx_bytes([weekly_row()]))]
        self.download([self.link()])
        Handler.routes[self.route] = [("ok", xlsx_bytes([weekly_row(price=7.77)]))]
        before = {p: (self.raw / p).read_bytes() for p in self.raw_files()}
        report = self.download([self.link(updated="2026-10-03")])  # mesmo instante => mesma pasta
        self.assertIn("não será sobrescrito", report["errors"][0]["error"])
        self.assertEqual({p: (self.raw / p).read_bytes() for p in self.raw_files()}, before)

    def test_fetch_to_file_rejects_oversized_response(self):
        Handler.routes[self.route] = [("ok", b"PK\x03\x04" + b"x" * 5000)]
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(DownloadError, "maior que o limite"):
            fetch_to_file(self.base_url + self.route, Path(folder) / "x", max_bytes=1000, sleep=self.sleeps.append)


class EndToEndRevisionTests(ServerCase):
    def test_download_then_ingest_records_provenance_and_detects_revision(self):
        first = xlsx_bytes([weekly_row()])
        Handler.routes[self.route] = [("ok", first)]
        self.download([self.link()], when=(2026, 10, 8, 12, 0, 0))
        report = self.ingest()
        entry = self.manifest()["files"][0]
        self.assertEqual((entry["source_url"], entry["retrieved_at"]),
                         (self.link().url, "2026-10-08T12:00:00+00:00"))
        self.assertEqual((entry["revision"], report["ingested"][0]["rows_accepted"]), (1, 1))
        # A ANP republica o mesmo nome com conteúdo diferente e muda "Atualizado em".
        second = xlsx_bytes([weekly_row(), weekly_row(cnpj=11111111000111, day=23)])
        Handler.routes[self.route] = [("ok", second)]
        saved = self.download([self.link(updated="2026-10-05")], known=known_files(self.manifest()["files"], read_log(self.log)),
                              when=(2026, 10, 9, 8, 30, 0))
        self.assertEqual(len(saved["saved"]), 1)
        self.assertEqual(len(self.raw_files()), 2)
        report = self.ingest()
        files = self.manifest()["files"]
        self.assertEqual([(f["revision"], f["is_current"]) for f in files], [(1, False), (2, True)])
        self.assertEqual(report["events"][0]["event"], "revision")
        self.assertEqual(files[1]["retrieved_at"], "2026-10-09T08:30:00+00:00")
        self.assertEqual(files[1]["ingestion"]["rows_accepted"], 2)
        self.assertEqual(files[0]["retrieved_at"], "2026-10-08T12:00:00+00:00")

    def test_matching_manual_file_gets_url_but_no_retrieval_time(self):
        content = xlsx_bytes([weekly_row()])
        Handler.routes[self.route] = [("ok", content)]
        (self.raw / self.name).write_bytes(content)
        self.ingest()
        self.assertEqual(self.manifest()["files"][0]["source_url"], None)
        self.download([self.link()], known=known_files(self.manifest()["files"], []))
        report = self.ingest()
        entry = self.manifest()["files"][0]
        self.assertEqual((entry["source_url"], entry["retrieved_at"]), (self.link().url, None))
        self.assertEqual(report["provenance_filled"], 1)
        self.assertEqual(self.raw_files(), [self.name])
        again = self.ingest()
        self.assertEqual((again["provenance_filled"], again["manifest_written"]), (0, False))


class DiscoveryTests(unittest.TestCase):
    def test_parse_weekly_links(self):
        links = parse_weekly_links(PAGE_SNIPPET)
        self.assertEqual([(l.filename, l.week_start, l.week_end, l.page_updated_on) for l in links], [
            ("revendas_lpc_2026-09-13_2026-09-19.xlsx", "2026-09-13", "2026-09-19", None),
            ("revendas_lpc_2026-09-20_2026-09-26.xlsx", "2026-09-20", "2026-09-26", "2026-09-25"),
        ])
        self.assertTrue(all(l.url.startswith("https://www.gov.br/") for l in links))

    def test_select_links_by_week_start(self):
        links = parse_weekly_links(PAGE_SNIPPET)
        self.assertEqual(len(select_links(links)), 2)
        self.assertEqual([l.week_start for l in select_links(links, since="2026-09-20")], ["2026-09-20"])
        self.assertEqual([l.week_start for l in select_links(links, until="2026-09-13")], ["2026-09-13"])

    def test_expected_content_checks(self):
        check_expected_content("a.xlsx", b"PK\x03\x04abcd")
        check_expected_content("a.csv", b"Regiao;Estado")
        for name, head in [("a.xlsx", b"<html>"), ("a.zip", b"%PDF"), ("a.csv", b"  <html>")]:
            with self.subTest(name=name), self.assertRaises(DownloadError):
                check_expected_content(name, head)

    def test_cli_rejects_non_gov_urls_and_reports_missing_links(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            fetch_anp.main(["--url", "http://www.gov.br/x/a.xlsx"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            fetch_anp.main(["--url", "https://exemplo.com/a.xlsx"])
        with tempfile.TemporaryDirectory() as folder:
            Handler.routes, Handler.hits = {"/pagina": [("ok", b"<html>sem links</html>")]}, {}
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                error = io.StringIO()
                with redirect_stderr(error), redirect_stdout(io.StringIO()):
                    code = fetch_anp.main(["--page", f"http://127.0.0.1:{server.server_address[1]}/pagina",
                                           "--out", folder, "--raw", folder])
            finally:
                server.shutdown()
                server.server_close()
            self.assertEqual(code, 1)
            self.assertIn("nenhum link", error.getvalue())


if __name__ == "__main__":
    unittest.main()
