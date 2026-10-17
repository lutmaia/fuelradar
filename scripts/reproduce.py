"""Reprodução dos números publicados: refaz cada relatório numa pasta temporária e compara.

Uso: python scripts/reproduce.py [--only ficha,estudo,descritivo,validacao,teste,backtest]
Lê com DATABASE_URL. Não grava nada em reports/ nem no banco: cada etapa roda o script oficial com
saída numa pasta temporária, e a comparação ignora só o commit e o horário da execução. Os gráficos
HTML não entram (o Plotly gera identificadores novos a cada vez; os números deles estão nos JSON).

O teste final **não é lido de novo** (o lacre é de uma leitura, ADR 0008 e protocolo da modelagem):
a decisão é recalculada a partir dos pontos gravados na leitura única, em data/processed/modelv2/
(fora do Git). Sem esse arquivo, a etapa é marcada como indisponível.
Números em JSON são iguais se a diferença relativa for de até 1e-9 (a gravação em CSV dos pontos muda
a 16ª casa decimal); qualquer número publicado tem muito menos casas. Retorno 0 se tudo bate; 1 se algum
relatório diverge.
"""

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

REPORTS = ROOT / "reports"
SHA = re.compile(r"\b[0-9a-f]{40}(?:-dirty|\+alterado)?\b")
HASH = re.compile(r"`[0-9a-f]{12,64}…?`")  # hashes de dados citados nos textos; comparados no JSON
INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
RUN_KEYS = {"code_sha", "run_at", "protocol_commit", "generated_at"}
DATA_HASH_KEYS = {"data_hash", "data_hashes"}

# etapa: (script e argumentos, com {out} para a pasta temporária; arquivos comparados; pasta publicada)
STEPS = {
    "ficha": (["dataset_card.py", "--report-dir", "{out}", "--docs", "{out}/docs"],
              ["ficha.json", "fontes.csv", "docs/ficha-dados.md", "docs/en/dataset-card.md"], None),
    "estudo": (["run_study.py", "--report-dir", "{out}"],
               ["resultados.json", "resumo.md", "q1.md", "q2.md", "q3.md"], REPORTS / "study"),
    "descritivo": (["run_study.py", "--descritivo", "--report-dir", "{out}"],
                   ["descritivo.json", "descritivo.md"], REPORTS / "study"),
    "validacao": (["run_modelv2.py", "--report-dir", "{out}", "--points-dir", "{out}/pontos"],
                  ["validacao.json", "validacao.md"], REPORTS / "modelv2"),
    "backtest": (["run_forecasts.py", "--no-store", "--report-dir", "{out}"], ["backtest.json", "backtest.md"],
                 REPORTS / "forecasting"),
}
PUBLISHED = {"ficha": {"ficha.json": REPORTS / "dataset" / "ficha.json",
                       "fontes.csv": REPORTS / "dataset" / "fontes.csv",
                       "docs/ficha-dados.md": ROOT / "docs" / "ficha-dados.md",
                       "docs/en/dataset-card.md": ROOT / "docs" / "en" / "dataset-card.md"}}


def normalize_text(text):
    return HASH.sub("<hash>", INSTANT.sub("<instante>", SHA.sub("<commit>", text)))


def normalize_json(value, drop=frozenset()):
    if isinstance(value, dict):
        return {k: normalize_json(v, drop) for k, v in value.items() if k not in RUN_KEYS | drop}
    if isinstance(value, list):
        return [normalize_json(v, drop) for v in value]
    return value


def close(a, b):
    """Estruturas iguais, com números de ponto flutuante iguais até 1e-9 relativo."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def same(published, produced):
    """(igual?, detalhe). JSON comparado como estrutura, sem os campos da execução; texto sem commit,
    horário e hashes citados. Números iguais com hash de dados diferente devolve None (aviso): o
    resultado se reproduz, mas a entrada não é byte a byte a mesma (ver o detalhe)."""
    if not published.exists():
        return False, "relatório publicado não existe"
    if not produced.exists():
        return False, "a execução não gerou o arquivo"
    a, b = published.read_text(encoding="utf-8"), produced.read_text(encoding="utf-8")
    if published.suffix == ".json":
        x, y = json.loads(a), json.loads(b)
        equal = close(normalize_json(x), normalize_json(y))
        if not equal and close(normalize_json(x, DATA_HASH_KEYS), normalize_json(y, DATA_HASH_KEYS)):
            return None, "números iguais, mas o hash dos dados de entrada difere"
    else:
        equal = normalize_text(a) == normalize_text(b)
    if equal:
        return True, ""
    first = next((i for i, (x, y) in enumerate(zip(normalize_text(a).splitlines(), normalize_text(b).splitlines()))
                  if x != y), None)
    return False, f"diverge (primeira linha diferente: {first + 1 if first is not None else 'fim do arquivo'})"


def run_step(name, folder):
    command, files, published_dir = STEPS[name]
    out = folder / name
    args = [arg.replace("{out}", str(out)) for arg in command]
    started = time.monotonic()
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / args[0]), *args[1:]], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    seconds = time.monotonic() - started
    if result.returncode != 0:
        return [(name, args[0], False, f"o script falhou: {result.stderr.strip().splitlines()[-1:]}")], seconds
    rows = []
    for file in files:
        published = PUBLISHED.get(name, {}).get(file) or published_dir / file
        ok, detail = same(published, out / file)
        rows.append((name, file, ok, detail))
    return rows, seconds


def check_test():
    """Decisão da modelagem v2 recalculada dos pontos da leitura única, sem novo acesso ao teste."""
    points_file = ROOT / "data" / "processed" / "modelv2" / "teste.csv.gz"
    if not points_file.exists():
        return [("teste", "final.json", None, "aviso: pontos da leitura única não estão neste computador")]
    import pandas as pd
    from radar_combustiveis.modelv2 import decision
    final = json.loads((REPORTS / "modelv2" / "final.json").read_text(encoding="utf-8"))
    recorded = final["decision"]
    redone = decision.decide(pd.read_csv(points_file), final["candidate"], recorded["checks"]["e_reprodutivel"])
    keys = ("approved", "checks", "ece", "groups", "test")
    ok = close(json.loads(json.dumps({k: redone[k] for k in keys})), {k: recorded[k] for k in keys})
    return [("teste", "final.json (decisão)", ok, "" if ok else "a decisão recalculada difere da publicada")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="etapas separadas por vírgula: " + ",".join([*STEPS, "teste"]))
    args = parser.parse_args(argv)
    chosen = args.only.split(",") if args.only else [*STEPS, "teste"]
    unknown = set(chosen) - {*STEPS, "teste"}
    if unknown:
        parser.error(f"etapa desconhecida: {', '.join(sorted(unknown))}")
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        for name in chosen:
            if name == "teste":
                rows += check_test()
                continue
            print(f"… {name}", flush=True)
            step_rows, seconds = run_step(name, Path(folder))
            print(f"  {seconds:.0f} s", flush=True)
            rows += step_rows
    print()
    for name, file, ok, detail in rows:
        mark = "ok  " if ok else ("AVISO" if ok is None else "DIFERENTE")
        print(f"{mark} {name:11s} {file}{'  ' + detail if detail else ''}")
    failed = [r for r in rows if r[2] is False]
    warned = [r for r in rows if r[2] is None]
    print(f"\n{len(rows) - len(failed) - len(warned)} de {len(rows)} idênticas; {len(warned)} com aviso; "
          f"{len(failed)} divergentes.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
