"""Janelas do estudo e da modelagem v2, fixadas antes de qualquer resultado (docs/estudo/protocolo.md).

As datas são domingos (início da semana da ANP) e valem para `week_start`. O teste final só é lido
uma vez, no fim do Marco 10; o estudo exploratório (Marco 8) usa apenas desenvolvimento e validação.
Mudar qualquer constante daqui exige registrar o desvio no protocolo.
"""

from datetime import date

DEV_START = date(2022, 11, 13)    # primeira semana com dado no banco
DEV_END = date(2025, 6, 29)       # última origem de desenvolvimento
VALID_START = date(2025, 7, 6)
VALID_END = date(2026, 3, 29)     # última origem de validação
TEST_START = date(2026, 4, 5)     # teste final: lacrado

# Estudo exploratório (Q1 a Q3): desenvolvimento + validação; nenhuma semana do teste final.
STUDY_START = DEV_START
STUDY_END = VALID_END
# Subperíodos para a checagem de estabilidade dos achados.
SUBPERIODS = ((date(2022, 11, 13), date(2024, 6, 30)), (date(2024, 7, 7), date(2026, 3, 29)))

SEED = 20261013
BOOTSTRAP_REPS = 2000
BOOTSTRAP_BLOCK_WEEKS = 4


class HoldoutViolation(RuntimeError):
    """Uma semana do teste final chegou a um caminho de código que não pode vê-la."""


def window_of(week_start):
    """'dev', 'valid' ou 'test' para uma semana; antes do início dos dados é um erro."""
    if week_start < DEV_START:
        raise ValueError(f"semana {week_start} anterior ao início dos dados ({DEV_START})")
    if week_start <= DEV_END:
        return "dev"
    if week_start <= VALID_END:
        return "valid"
    return "test"


def study_weeks(weeks):
    """Mantém só as semanas do estudo exploratório (até `STUDY_END`), na ordem recebida."""
    return [w for w in weeks if STUDY_START <= w <= STUDY_END]


def assert_no_holdout(weeks):
    """Falha se alguma semana pertence ao teste final. Usado na saída dos carregadores do estudo."""
    leaked = sorted({w for w in weeks if w >= TEST_START})
    if leaked:
        raise HoldoutViolation(f"{len(leaked)} semana(s) do teste final, a primeira em {leaked[0]}")
