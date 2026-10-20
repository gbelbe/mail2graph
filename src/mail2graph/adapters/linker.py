"""Liaison mention -> entité : identifiant déjà connu, sinon correspondance floue (rapidfuzz) sur les libellés."""
from __future__ import annotations

from typing import Sequence

from rapidfuzz import fuzz, process

from ..domain import Candidate, EntityRef, GraphContext, Mention, normalize


class FuzzyLinker:
    def __init__(self, top: int = 3):
        self.top = top
        self._ctx_id: int | None = None
        self._names: list[str] = []
        self._owners: list[EntityRef] = []

    def _index(self, ctx: GraphContext) -> None:
        if self._ctx_id == id(ctx):
            return
        self._names, self._owners = [], []
        for e in ctx.entities:
            for n in set(e.names or (e.label,)):
                nn = normalize(n)
                if nn:
                    self._names.append(nn)
                    self._owners.append(e)
        self._ctx_id = id(ctx)

    def link(self, mention: Mention, ctx: GraphContext) -> Sequence[Candidate]:
        if mention.entity_id:
            for e in ctx.entities:
                if e.id == mention.entity_id:
                    return [Candidate(e, 1.0)]
            return []
        self._index(ctx)
        q = normalize(mention.text)
        if not q or not self._names:
            return []
        best: dict[str, Candidate] = {}
        for _name, score, idx in process.extract(q, self._names, scorer=fuzz.ratio, limit=self.top * 3):
            e = self._owners[idx]
            if e.id not in best or score / 100 > best[e.id].score:
                best[e.id] = Candidate(e, score / 100)
        return sorted(best.values(), key=lambda c: -c.score)[: self.top]
