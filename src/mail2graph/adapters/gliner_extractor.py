"""Reconnaissance d'entités zéro-shot avec GLiNER (extra `[ner]`).

Les étiquettes viennent de la configuration (`extract.gliner.labels`, nature -> étiquette) ou, à défaut, des classes
du graphe : le même module sert alors à n'importe quelle ontologie. Le modèle est chargé à la première utilisation ;
on peut aussi en injecter un (tests, modèle déjà chargé).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..config import GlinerCfg
from ..domain import GraphContext, Mention, Message


class GlinerExtractor:
    def __init__(self, labels: Mapping[str, str] | None = None, threshold: float = 0.5,
                 model_name: str = "urchade/gliner_multi-v2.1", model: Any = None, max_chars: int = 4000):
        self.labels = dict(labels or {})
        self.threshold = threshold
        self.model_name = model_name
        self.max_chars = max_chars
        self._model = model

    @classmethod
    def from_config(cls, cfg: GlinerCfg) -> "GlinerExtractor":
        return cls(cfg.labels, cfg.threshold, cfg.model, max_chars=cfg.max_chars)

    def _load(self) -> Any:
        if self._model is None:
            try:
                from gliner import GLiNER
            except ImportError as e:
                raise RuntimeError("Installer l'extra : pip install 'mail2graph[ner]'") from e
            self._model = GLiNER.from_pretrained(self.model_name)
        return self._model

    def _labels(self, ctx: GraphContext) -> dict[str, str]:
        """nature -> étiquette ; sans configuration, chaque classe du graphe devient une nature (son URI)."""
        return self.labels or {c.id: c.label for c in ctx.classes}

    def extract(self, message: Message, ctx: GraphContext) -> Sequence[Mention]:
        labels = self._labels(ctx)
        if not labels:
            return []
        text = f"{message.subject}\n{message.body}"[: self.max_chars]
        found = self._load().predict_entities(text, list(labels.values()), threshold=self.threshold)
        kind_of = {label: kind for kind, label in labels.items()}
        return _mentions(message.id, found, kind_of)


def _mentions(message_id: str, found: Sequence[Mapping[str, Any]], kind_of: Mapping[str, str]) -> list[Mention]:
    out: list[Mention] = []
    seen: set[tuple[str, str]] = set()
    for ent in found:
        text = str(ent["text"]).strip()
        kind = kind_of.get(ent["label"])
        if text and kind and (kind, text.lower()) not in seen:
            seen.add((kind, text.lower()))
            out.append(Mention(message_id, kind, text, float(ent["score"])))
    return out
