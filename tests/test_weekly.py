"""Rotina semanal (Marco 12, etapa B3) com página, pacote e etapas falsos; nada acessa a internet ou o banco."""

from contextlib import redirect_stderr, redirect_stdout
import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scripts import weekly_refresh  # noqa: E402
from radar_combustiveis import weekly  # noqa: E402
from radar_combustiveis.ingestion.download import DownloadError  # noqa: E402
from tests.test_download import PAGE_SNIPPET  # noqa: E402

ENV = {"DATABASE_URL": "postgresql://x", "API_DATABASE_URL": "postgresql://y"}


def write_snapshot(path, week):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump({"latest_week_start": week}, stream)


class HelperTests(unittest.TestCase):
    def test_latest_page_week(self):
        self.assertEqual(weekly.latest_page_week(PAGE_SNIPPET), "2026-09-20")
        self.assertIsNone(weekly.latest_page_week("<html>página nova, sem links</html>"))

    def test_snapshot_week(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pacote.json.gz"
            self.assertIsNone(weekly.snapshot_week(path))
            path.write_bytes(b"corrompido")
            self.assertIsNone(weekly.snapshot_week(path))
            write_snapshot(path, "2026-10-04")
            self.assertEqual(weekly.snapshot_week(path), "2026-10-04")

    def test_run_stops_at_first_failure(self):
        calls = []
        codes = {"qualidade": 1}
        report = weekly.run(weekly.STAGES, lambda s: calls.append(s.name) or codes.get(s.name, 0), clock=lambda: 0)
        self.assertEqual(calls, ["baixar a ANP", "ingerir", "qualidade"])
        self.assertEqual(report["status"], "falhou")
        self.assertEqual(report["failed_stage"], "qualidade")

    def test_run_all_stages(self):
        report = weekly.run(weekly.STAGES, lambda s: 0, clock=lambda: 0)
        self.assertEqual(report["status"], "concluído")
        self.assertEqual([r["stage"] for r in report["stages"]], [s.name for s in weekly.STAGES])
        self.assertEqual(weekly.STAGES[-1].script, "build_snapshot.py")  # "em dia" depende de o pacote ser o último

    def test_stage_scripts_exist(self):
        for stage in weekly.STAGES:
            self.assertTrue((weekly_refresh.ROOT / "scripts" / stage.script).exists(), stage.script)

    def test_record_appends(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "sub" / "runs.jsonl"
            weekly.record(log, {"status": "em dia"})
            weekly.record(log, {"status": "concluído"})
            lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([line["status"] for line in lines], ["em dia", "concluído"])
            self.assertIn("finished_at", lines[0])


class ScriptTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        self.snapshot, self.log = self.dir / "pacote.json.gz", self.dir / "runs.jsonl"
        self.ran = []
        for name, value in (("SNAPSHOT", self.snapshot), ("LOG", self.log)):
            patcher = mock.patch.object(weekly_refresh, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def main(self, page=PAGE_SNIPPET, runner=None, argv=(), env=ENV):
        read = mock.Mock(side_effect=page) if isinstance(page, Exception) else mock.Mock(return_value=page)
        runner = runner or (lambda stage: self.ran.append(stage.name) or 0)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(weekly_refresh, "read_page", read), \
                mock.patch.object(weekly_refresh, "run_script", runner), \
                mock.patch.dict(os.environ, env, clear=True), redirect_stdout(out), redirect_stderr(err):
            code = weekly_refresh.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def runs(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_up_to_date_does_nothing(self):
        write_snapshot(self.snapshot, "2026-09-20")
        code, output = self.main()
        self.assertEqual(code, 0)
        self.assertEqual(self.ran, [])
        self.assertIn("Em dia", output)
        self.assertEqual(self.runs()[-1]["status"], "em dia")

    def test_new_week_runs_every_stage(self):
        write_snapshot(self.snapshot, "2026-09-13")

        def runner(stage):
            self.ran.append(stage.name)
            if stage.script == "build_snapshot.py":
                write_snapshot(self.snapshot, "2026-09-20")
            return 0

        code, output = self.main(runner=runner)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran, [s.name for s in weekly.STAGES])
        self.assertEqual(self.runs()[-1]["status"], "concluído")
        self.assertEqual(self.runs()[-1]["page_week"], "2026-09-20")

    def test_failure_names_the_stage_and_next_run_retries(self):
        write_snapshot(self.snapshot, "2026-09-13")
        code, output = self.main(runner=lambda s: self.ran.append(s.name) or (1 if s.script == "run_live.py" else 0))
        self.assertEqual(code, 1)
        self.assertIn("FALHOU em: previsão ao vivo e placar", output)
        self.assertNotIn("pacote do demonstrativo", self.ran)
        self.assertEqual(self.runs()[-1]["failed_stage"], "previsão ao vivo e placar")
        # O pacote ficou na semana antiga: a próxima execução refaz tudo.
        self.ran.clear()
        self.main(runner=lambda s: self.ran.append(s.name) or 0)
        self.assertEqual(self.ran[0], "baixar a ANP")

    def test_package_not_updated_is_a_failure(self):
        write_snapshot(self.snapshot, "2026-09-13")
        code, output = self.main()
        self.assertEqual(code, 1)
        self.assertIn("conferência final", self.runs()[-1]["failed_stage"])

    def test_page_unreachable(self):
        code, output = self.main(page=DownloadError("HTTP 403"))
        self.assertEqual(code, 1)
        self.assertIn("HTTP 403", output)
        self.assertEqual(self.runs()[-1]["failed_stage"], "ler a página da ANP")

    def test_page_without_links(self):
        code, _ = self.main(page="<html></html>")
        self.assertEqual(code, 1)
        self.assertEqual(self.ran, [])

    def test_dry_run_and_missing_configuration(self):
        write_snapshot(self.snapshot, "2026-09-13")
        code, output = self.main(argv=["--dry-run"])
        self.assertEqual((code, self.ran), (0, []))
        self.assertIn("Há semana nova", output)
        self.assertFalse(self.log.exists())
        code, output = self.main(env={})
        self.assertEqual((code, self.ran), (1, []))
        self.assertIn("API_DATABASE_URL", output)

    def test_force_runs_even_when_up_to_date(self):
        write_snapshot(self.snapshot, "2026-09-20")
        self.main(argv=["--force"])
        self.assertEqual(self.ran, [s.name for s in weekly.STAGES])


if __name__ == "__main__":
    unittest.main()
