import sys
import types
from datetime import datetime, timezone

import pytest

from mail2graph import Config, Message, build_pipeline
from mail2graph.adapters.gliner_extractor import GlinerExtractor
from mail2graph.adapters.sources import MemorySource
from mail2graph.config import GlinerCfg
from mail2graph.domain import ClassInfo, GraphContext, Mention

MSG_G = "<g@x>"
K_CABINET_DURAND = "Cabinet Durand"
K_GLINER = "gliner"
K_MAIRIE = "Mairie"
K_ORGANISATION = "organisation"
K_PERSONNE = "personne"

DATE = datetime(2026, 10, 21, tzinfo=timezone.utc)
MAX_CHARS_SMALL = 10
DEFAULT_THRESHOLD = 0.5


def message(subject="Objet", body="Corps du message"):
    return Message(MSG_G, subject, "a@b.fr", DATE, body)


class FakeModel:
    def __init__(self, found):
        self.found, self.calls = found, []

    def predict_entities(self, text, labels, threshold):
        self.calls.append((text, labels, threshold))
        return self.found


def ent(text, label=K_ORGANISATION, score=0.9):
    return {"text": text, "label": label, "score": score}


def test_maps_labels_back_to_kinds_and_keeps_scores():
    model = FakeModel([ent(K_CABINET_DURAND, K_ORGANISATION, 0.91), ent("Jean Dupont", K_PERSONNE, 0.7)])
    ex = GlinerExtractor({"org": K_ORGANISATION, "pers": K_PERSONNE}, threshold=0.4, model=model)
    got = ex.extract(message(), GraphContext())
    assert got == [Mention(MSG_G, "org", K_CABINET_DURAND, 0.91), Mention(MSG_G, "pers", "Jean Dupont", 0.7)]
    assert model.calls == [("Objet\nCorps du message", [K_ORGANISATION, K_PERSONNE], 0.4)]


def test_ignores_unknown_labels_blank_texts_and_duplicates():
    model = FakeModel([ent("  "), ent("Autre", "inconnue"), ent(K_CABINET_DURAND), ent("cabinet durand", score=0.5), ent(" Cabinet Durand ")])
    got = GlinerExtractor({"org": K_ORGANISATION}, model=model).extract(message(), GraphContext())
    assert [(m.kind, m.text) for m in got] == [("org", K_CABINET_DURAND)]


def test_text_is_truncated_to_max_chars():
    model = FakeModel([])
    GlinerExtractor({"org": K_ORGANISATION}, model=model, max_chars=MAX_CHARS_SMALL).extract(message(body="x" * 100), GraphContext())
    assert len(model.calls[0][0]) == MAX_CHARS_SMALL and model.calls[0][0].startswith("Objet\nxxxx")


def test_graph_classes_are_the_default_labels():
    classes = (ClassInfo("https://ex/Organisme", "Organisme"), ClassInfo("https://ex/Mairie", K_MAIRIE))
    model = FakeModel([ent("Mairie de X", K_MAIRIE)])
    got = GlinerExtractor(model=model).extract(message(), GraphContext(classes=classes))
    assert model.calls[0][1] == ["Organisme", K_MAIRIE]
    assert [(m.kind, m.text) for m in got] == [("https://ex/Mairie", "Mairie de X")]


def test_no_labels_means_no_model_call():
    model = FakeModel([ent("X")])
    assert GlinerExtractor(model=model).extract(message(), GraphContext()) == []
    assert model.calls == []


def test_model_is_loaded_lazily_once_by_name(monkeypatch):
    loaded = []

    class Fake:
        @classmethod
        def from_pretrained(cls, name):
            loaded.append(name)
            return FakeModel([])

    monkeypatch.setitem(sys.modules, K_GLINER, types.SimpleNamespace(GLiNER=Fake))
    ex = GlinerExtractor({"org": K_ORGANISATION}, model_name="mon/modele")
    assert loaded == []
    ex.extract(message(), GraphContext())
    ex.extract(message(), GraphContext())
    assert loaded == ["mon/modele"]


def test_missing_extra_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, K_GLINER, None)
    with pytest.raises(RuntimeError, match=r"mail2graph\[ner\]"):
        GlinerExtractor({"org": K_ORGANISATION}).extract(message(), GraphContext())


def test_from_config_and_factory_wiring(tmp_path):
    (tmp_path / "g.ttl").write_text("", encoding="utf-8")
    cfg = Config.model_validate({"root": str(tmp_path), "graph": {"files": ["g.ttl"]},
                                 "extract": {"gazetteer": False, K_GLINER: {"labels": {"org": K_ORGANISATION}, "threshold": 0.3, "model": "m/x", "max_chars": 50}}})
    ex = GlinerExtractor.from_config(cfg.extract.gliner)
    assert (ex.labels, ex.threshold, ex.model_name, ex.max_chars) == ({"org": K_ORGANISATION}, 0.3, "m/x", 50)
    pipeline = build_pipeline(cfg, source=MemorySource([]))
    assert len(pipeline.extractors) == 1 and isinstance(pipeline.extractors[0], GlinerExtractor)
    assert GlinerCfg().threshold == DEFAULT_THRESHOLD and GlinerCfg().labels == {}


def test_constructor_defaults():
    ex = GlinerExtractor()
    assert (ex.labels, ex.threshold, ex.model_name, ex.max_chars) == ({}, 0.5, "urchade/gliner_multi-v2.1", 4000)
