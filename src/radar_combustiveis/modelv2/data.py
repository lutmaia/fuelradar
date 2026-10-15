"""Leitura do banco para a modelagem v2, com o lacre do teste final (protocolo, seção 7).

Sem `read_test`, as linhas param em `VALID_END` e passam por `assert_no_holdout`. Com `read_test`,
uma linha é gravada em `holdout_access` (na mesma transação) antes de os dados serem devolvidos.
"""

from ..forecasting import protocol
from ..forecasting.panel import data_hash, load_rows
from .spec import PRODUCER_OF


def load_panel_rows(conn, uf="SP", read_test=False, purpose=None, code_sha=None):
    rows = load_rows(conn, uf)
    if not read_test:
        rows = [r for r in rows if r[0] <= protocol.VALID_END]
        protocol.assert_no_holdout([r[0] for r in rows])
        return rows
    if not purpose:
        raise ValueError("Ler o teste final exige uma finalidade (`purpose`)")
    weeks = [r[0] for r in rows]
    with conn.transaction():
        conn.execute("""
            INSERT INTO holdout_access (code_sha, purpose, data_hash, row_count, first_week, last_week)
            VALUES (%s, %s, %s, %s, %s, %s)""", (code_sha, purpose, data_hash(rows), len(rows), min(weeks), max(weeks)))
    return rows


def holdout_reads(conn):
    return conn.execute("""SELECT access_id, accessed_at, code_sha, purpose, data_hash, row_count
                           FROM holdout_access ORDER BY access_id""").fetchall()


def load_external(conn):
    """{"usd": [...], "producers": {código: [...]}} com `period_end`, `available_at` e `value`."""
    usd = [dict(period_end=r[0], available_at=r[1], value=float(r[2])) for r in conn.execute("""
        SELECT period_end, available_at, value FROM external_observation
        WHERE source_id = 'bcb_sgs_1' AND product = 'USD_BRL_VENDA' ORDER BY period_end""").fetchall()]
    producers = {}
    for code in sorted(set(PRODUCER_OF.values())):
        producers[code] = [dict(period_end=r[0], available_at=r[1], value=float(r[2])) for r in conn.execute("""
            SELECT period_end, available_at, value FROM external_observation
            WHERE source_id = 'anp_produtores' AND product = %s AND geo = 'SUDESTE' ORDER BY period_end""",
                                                                                                       (code,)).fetchall()]
    return {"usd": usd, "producers": producers}
