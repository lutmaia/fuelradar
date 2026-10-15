"""Fontes externas (Marco 9): dólar do BCB, preços de produtores e de distribuição da ANP.

Triagem e licenças em docs/estudo/triagem-fontes-externas.md; decisões no ADR 0010. Mesma
disciplina da ingestão da ANP: brutos intactos em data/raw/external/, hash, qualidade e carga
idempotente. Cada valor guarda `available_at`, a data a partir da qual ele podia ser conhecido.
"""
