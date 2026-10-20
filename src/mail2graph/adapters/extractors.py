"""Extracteurs : expressions régulières configurables et gazetteer construit à partir du graphe.

D'autres extracteurs (GLiNER, spaCy, agent LLM) s'ajoutent par plugin sans toucher au cœur.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from ..domain import GraphContext, Mention, Message, normalize


class RegexExtractor:
    def __init__(self, patterns: Mapping[str, str]):
        self._p = {k: re.compile(v, re.IGNORECASE) for k, v in patterns.items()}

    def extract(self, message: Message, ctx: GraphContext) -> Sequence[Mention]:
        text = f"{message.subject}\n{message.body}"
        out, seen = [], set()
        for kind, rx in self._p.items():
            for m in rx.finditer(text):
                t = re.sub(r"\s+", " ", m.group(0)).strip()
                if (kind, t.lower()) not in seen:
                    seen.add((kind, t.lower()))
                    out.append(Mention(message.id, kind, t))
        return out


class GazetteerExtractor:
    """Repère dans le texte les libellés des entités déjà présentes dans le graphe."""

    def __init__(self, min_len: int = 5):
        self.min_len = min_len

    def extract(self, message: Message, ctx: GraphContext) -> Sequence[Mention]:
        hay = f" {normalize(message.subject + ' ' + message.body)} "
        out, seen = [], set()
        for e in ctx.entities:
            for name in e.names or (e.label,):
                n = normalize(name)
                if len(n) >= self.min_len and f" {n} " in hay and e.id not in seen:
                    seen.add(e.id)
                    out.append(Mention(message.id, "gazetteer", name, 1.0, entity_id=e.id))
                    break
        return out
