"""Comparação da reprodução (Marco 13): ignora só commit e horário; números com tolerância mínima."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import reproduce  # noqa: E402

SHA_A, SHA_B = "a" * 40, "b" * 40


class CompareTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)

    def pair(self, name, published, produced):
        a, b = self.dir / f"publicado-{name}", self.dir / f"refeito-{name}"
        a.write_text(published, encoding="utf-8")
        b.write_text(produced, encoding="utf-8")
        return a, b

    def test_markdown_ignores_commit_and_instant(self):
        a, b = self.pair("r.md", f"Código `{SHA_A}` em 2026-10-15T15:31:50+00:00, hash `1c7b8e52107be9a9…`\nBSS +0,164\n",
                         f"Código `{SHA_B}-dirty` em 2026-10-16T09:00:00Z, hash `7737732912e95be3…`\nBSS +0,164\n")
        self.assertEqual(reproduce.same(a, b), (True, ""))
        a, b = self.pair("s.md", "linha\nBSS +0,164\n", "linha\nBSS +0,165\n")
        self.assertEqual(reproduce.same(a, b), (False, "diverge (primeira linha diferente: 2)"))

    def test_json_ignores_run_fields_and_rounding_noise(self):
        published = {"meta": {"code_sha": SHA_A, "run_at": "x", "data_hash": "h"}, "bss": 0.16376261366223588}
        produced = {"meta": {"code_sha": SHA_B, "run_at": "y", "data_hash": "h"}, "bss": 0.16376261366223577}
        a, b = self.pair("r.json", json.dumps(published), json.dumps(produced))
        self.assertTrue(reproduce.same(a, b)[0])
        produced["bss"] = 0.1638
        a, b = self.pair("s.json", json.dumps(published), json.dumps(produced))
        self.assertFalse(reproduce.same(a, b)[0])
        produced["bss"], produced["meta"]["data_hash"] = published["bss"], "outro"  # mesmo número, entrada diferente
        a, b = self.pair("t.json", json.dumps(published), json.dumps(produced))
        self.assertEqual(reproduce.same(a, b), (None, "números iguais, mas o hash dos dados de entrada difere"))
        produced["bss"] = 0.2  # entrada e número diferentes: divergência
        a, b = self.pair("u.json", json.dumps(published), json.dumps(produced))
        self.assertFalse(reproduce.same(a, b)[0])

    def test_missing_files(self):
        a, _ = self.pair("r.json", "{}", "{}")
        self.assertEqual(reproduce.same(self.dir / "nao-existe", a), (False, "relatório publicado não existe"))
        self.assertEqual(reproduce.same(a, self.dir / "nao-existe"), (False, "a execução não gerou o arquivo"))

    def test_close(self):
        self.assertTrue(reproduce.close({"a": [1, 2.0]}, {"a": [1, 2.0000000000000004]}))
        self.assertFalse(reproduce.close({"a": 1}, {"b": 1}))
        self.assertFalse(reproduce.close([1, 2], [1, 2, 3]))
        self.assertFalse(reproduce.close("0.1", 0.1))


if __name__ == "__main__":
    unittest.main()
