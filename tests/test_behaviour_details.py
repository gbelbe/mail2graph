"""Tests de précision : valeurs exactes, bornes et comptages. Ils servent aussi de filet pour les mutants (mutmut)."""
from datetime import datetime, timezone

import pytest
from rapidfuzz import fuzz

from mail2graph import Config, Message, build_pipeline
from mail2graph.adapters.extractors import GazetteerExtractor, RegexExtractor
from mail2graph.adapters.linker import FuzzyLinker
from mail2graph.adapters.sources import MemorySource
from mail2graph.domain import (Candidate, EntityRef, GraphContext, Mention, Proposition, clean_body, link_decision,
                               normalize)
from mail2graph.pipeline import MessageFilter

DATE = datetime(2026, 10, 21, tzinfo=timezone.utc)
EX = "https://example.org/dossier/"


def msg(i="<1@x>", body="Bonjour", subject="Sujet", sender="a@mairie.fr", attachments=()):
    return Message(i, subject, sender, DATE, body, tuple(attachments))


def cfg_for(tmp_path, **graph):
    (tmp_path / "g.ttl").write_text("", encoding="utf-8")
    return Config.model_validate({"root": str(tmp_path),
                                  "graph": {"files": ["g.ttl"], "base_uri": EX, **graph}})


class FakeLinker:
    def __init__(self, cands):
        self.cands = cands

    def link(self, mention, ctx):
        return self.cands


class FakeExtractor:
    def __init__(self, mentions):
        self.mentions = mentions

    def extract(self, message, ctx):
        return self.mentions


class RecordingSource:
    def __init__(self, messages):
        self.messages, self.since = messages, []

    def fetch(self, since=None):
        self.since.append(since)
        return list(self.messages)


def entity(i="e", label="Mairie de Plouhinec", names=()):
    return EntityRef(EX + i, label, "https://example.org/C", tuple(names))


# ── domain ─────────────────────────────────────────────────────────────────────

def test_clean_body_exact_outputs():
    assert clean_body("Bonjour\r\n\r\n\r\n\r\nSuite") == "Bonjour\n\nSuite"
    assert clean_body("Texte\nLe lundi 5 octobre 2026, X a écrit :\n> citation") == "Texte"
    assert clean_body("Hello\nOn Mon, Oct 5, 2026, X wrote:\n> quoted") == "Hello"
    assert clean_body("A\n\n\nB") == "A\n\nB"
    assert clean_body("A\n-- \nSignature") == "A"


def test_link_decision_boundaries():
    assert link_decision(0.9, 0.9, 0.7) == "link"
    assert link_decision(0.7, 0.9, 0.7) == "suggest"
    assert link_decision(0.69, 0.9, 0.7) == "none"


def test_proposition_id_is_stable_short_hash():
    a = Proposition("link", "<1@x>", {"k": "v"})
    b = Proposition("link", "<1@x>", {"k": "v"})
    assert a.id == b.id and len(a.id) == 12
    assert Proposition("link", "<2@x>", {"k": "v"}).id != a.id


# ── filtre ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sender,allow,ok", [
    ("Agent@Mairie.FR", ["mairie.fr"], True),
    ("agent@mairie.fr", ["AGENT@MAIRIE.FR"], True),
    ("agent@mairie.fr", ["@mairie.fr"], True),
    ("agent@xmairie.fr", ["mairie.fr"], False),
    ("agent@autre.fr", ["mairie.fr"], False),
    ("agent@mairie.fr", [], True),
])
def test_sender_filter(sender, allow, ok):
    assert MessageFilter(allow).accepts(msg(sender=sender)) is ok


def test_subject_filter_is_case_insensitive():
    assert MessageFilter(subject_regex="dp").accepts(msg(subject="Dossier DP 12"))
    assert not MessageFilter(subject_regex="dp").accepts(msg(subject="Newsletter"))


# ── pipeline.run ───────────────────────────────────────────────────────────────

def test_run_counts_and_passes_cursor_and_attachments(tmp_path):
    cfg = cfg_for(tmp_path)
    cfg.filter.subject_regex = "^ok"
    seen_by_extractor = []

    class Spy:
        def extract(self, message, ctx):
            seen_by_extractor.append(message)
            return []

    first = RecordingSource([msg("<1@x>", subject="ok 1", attachments=("a.pdf",))])
    build_pipeline(cfg, source=first, extractors=[Spy()]).run()
    assert first.since == [None]
    assert seen_by_extractor[0].attachments == ("a.pdf",)

    second = RecordingSource([
        msg("<1@x>", subject="ok 1"),          # déjà vu : ignoré, mais la suite est traitée
        msg("<2@x>", subject="ok 2"),
        msg("<3@x>", subject="ok 3"),
        msg("<4@x>", subject="non"),
        msg("<5@x>", subject="non"),
    ])
    p = build_pipeline(cfg, source=second, extractors=[Spy()])
    rep = p.run()
    assert second.since[0] is not None
    assert (rep.fetched, rep.skipped_known, rep.skipped_filtered) == (5, 1, 2)
    assert rep.propositions == 4 and rep.new_propositions == 4   # (message + événement) x 2 courriels


# ── pipeline.propose ───────────────────────────────────────────────────────────

def propose(tmp_path, cands, mentions, **graph):
    cfg = cfg_for(tmp_path, **graph)
    p = build_pipeline(cfg, source=MemorySource([]), linker=FakeLinker(cands), extractors=[FakeExtractor(mentions)])
    m = msg("<9@x>", subject="Objet du mail")
    return m, p.propose(m, p.store.context())


def test_message_and_event_propositions_exact(tmp_path):
    m, props = propose(tmp_path, [], [])
    head, event = props
    assert head.kind == "message" and head.message_id == m.id
    assert head.payload == {"uri": f"{EX}courriel-{m.digest}", "subject": "Objet du mail", "date": "2026-10-21",
                            "sender_domain": "mairie.fr", "hash": m.digest}
    assert event.kind == "event" and event.message_id == m.id and event.parent == head.id
    assert event.payload == {"mail_uri": head.payload["uri"], "label": "Objet du mail", "date": "2026-10-21"}
    assert event.note == "Un événement daté de la réception du courriel."


def test_no_event_when_disabled(tmp_path):
    _, props = propose(tmp_path, [], [], event_from_message=False)
    assert [p.kind for p in props] == ["message"]


def test_link_payload_confidence_and_notes(tmp_path):
    men = Mention("<9@x>", "x", "Mairie de Plouhinec")
    ent = entity()
    m, props = propose(tmp_path, [Candidate(ent, 0.123456)], [men])      # sous le seuil bas : rien
    assert [p.kind for p in props] == ["message", "event"]

    m, props = propose(tmp_path, [Candidate(ent, 0.8)], [men])           # entre les seuils : incertain
    link = props[1]
    assert link.kind == "link" and link.message_id == m.id and link.parent == props[0].id
    assert link.note == "Correspondance incertaine : à vérifier."
    assert link.confidence == 0.8
    assert link.payload == {"mail_uri": props[0].payload["uri"], "entity_uri": ent.id,
                            "entity_label": ent.label, "mention": "Mairie de Plouhinec", "score": 0.8}

    m, props = propose(tmp_path, [Candidate(ent, 0.987654)], [men])      # au-dessus : sûr, score arrondi à 3 décimales
    link = props[1]
    assert link.note == "" and link.payload["score"] == 0.988


def test_each_entity_is_linked_once(tmp_path):
    ent = entity()
    men = [Mention("<9@x>", "x", "a"), Mention("<9@x>", "x", "b")]
    _, props = propose(tmp_path, [Candidate(ent, 1.0)], men)
    assert [p.kind for p in props].count("link") == 1


def test_new_entity_proposal_exact_and_deduplicated(tmp_path):
    kinds = {"org": "https://example.org/Organisme"}
    men = [Mention("<9@x>", "org", "Cabinet Durand", 0.9), Mention("<9@x>", "org", "cabinet durand", 0.8),
           Mention("<9@x>", "autre", "Société X", 0.7)]
    m, props = propose(tmp_path, [], men, new_entity_kinds=kinds)
    new = [p for p in props if p.kind == "new_entity"]
    assert len(new) == 1
    n = new[0]
    assert n.message_id == m.id and n.parent == props[0].id and n.confidence == 0.9
    assert n.payload == {"label": "Cabinet Durand", "class_uri": "https://example.org/Organisme",
                         "mail_uri": props[0].payload["uri"], "mention": "Cabinet Durand"}
    assert n.note == "Entité absente du graphe : proposée à la création."


def test_low_score_candidate_still_allows_new_entity(tmp_path):
    kinds = {"org": "https://example.org/Organisme"}
    men = [Mention("<9@x>", "org", "Cabinet Durand")]
    _, props = propose(tmp_path, [Candidate(entity(), 0.2)], men, new_entity_kinds=kinds)
    assert [p.kind for p in props].count("new_entity") == 1


# ── extracteurs ────────────────────────────────────────────────────────────────

def test_regex_extractor_case_whitespace_and_dedup():
    ex = RegexExtractor({"dp": r"DP\s?\d{3}\s+\d{3}"})
    ments = ex.extract(msg("<7@x>", body="vu dp 029   174 puis DP 029 174"), GraphContext())
    assert [(x.message_id, x.kind, x.text) for x in ments] == [("<7@x>", "dp", "dp 029 174")]


def test_gazetteer_default_min_len_and_fields():
    ex = GazetteerExtractor()
    ctx = GraphContext(entities=(entity("a", "Mairi"), entity("b", "Pont"), entity("c", "Trolimon", names=("Trolimon", "Saint-Jean-Trolimon"))))
    ments = ex.extract(msg("<7@x>", subject="Objet", body="La Mairi et le Pont, à Saint-Jean-Trolimon."), ctx)
    assert [(x.message_id, x.kind, x.text, x.confidence, x.entity_id) for x in ments] == [
        ("<7@x>", "gazetteer", "Mairi", 1.0, EX + "a"),
        ("<7@x>", "gazetteer", "Trolimon", 1.0, EX + "c"),
    ]


def test_gazetteer_uses_label_when_no_names_and_reads_subject():
    ex = GazetteerExtractor()
    ctx = GraphContext(entities=(entity("a", "Mairie de Plouhinec", names=()),))
    assert len(ex.extract(msg(subject="Mairie de Plouhinec", body="rien"), ctx)) == 1
    assert ex.extract(msg(subject="Autre", body="rien"), ctx) == []


# ── liaison floue ──────────────────────────────────────────────────────────────

def test_linker_known_entity_and_unknown_entity():
    ctx = GraphContext(entities=(entity("a"), entity("b", "Autre")))
    lk = FuzzyLinker()
    c = lk.link(Mention("m", "gazetteer", "x", entity_id=EX + "b"), ctx)
    assert [(x.entity.id, x.score) for x in c] == [(EX + "b", 1.0)]
    assert lk.link(Mention("m", "gazetteer", "x", entity_id=EX + "zzz"), ctx) == []


def test_linker_fuzzy_score_is_ratio_and_normalised_to_one():
    ctx = GraphContext(entities=(entity("a", "Mairie de Plouhinec"),))
    lk = FuzzyLinker()
    exact = lk.link(Mention("m", "x", "mairie de plouhinec"), ctx)[0]
    assert exact.score == 1.0
    near = lk.link(Mention("m", "x", "Mairie de Plouhinek"), ctx)[0]
    assert near.score == pytest.approx(fuzz.ratio(normalize("Mairie de Plouhinek"), normalize("Mairie de Plouhinec")) / 100)


def test_linker_returns_top_three_best_per_entity_and_ignores_empty_query():
    ents = tuple(entity(f"e{i}", f"Commune {chr(97 + i)}bcdef") for i in range(12))
    ctx = GraphContext(entities=ents)
    lk = FuzzyLinker()
    assert len(lk.link(Mention("m", "x", "Commune abcdef"), ctx)) == 3
    assert lk.link(Mention("m", "x", "!!!"), ctx) == []
    multi = GraphContext(entities=(entity("a", "Zzz", names=("Zzz", "Mairie de Plouhinec")),))
    got = lk.link(Mention("m", "x", "Mairie de Plouhinec"), multi)
    assert len(got) == 1 and got[0].score == 1.0


def test_linker_reuses_its_index_for_the_same_context():
    ctx = GraphContext(entities=(entity("a"),))
    lk = FuzzyLinker()
    lk.link(Mention("m", "x", "Mairie"), ctx)
    names = lk._names
    lk.link(Mention("m", "x", "Mairie"), ctx)
    assert lk._names is names
    other = GraphContext(entities=(entity("b", "Autre nom"),))
    assert lk.link(Mention("m", "x", "Autre nom"), other)[0].entity.id == EX + "b"


def test_run_counts_every_known_message(tmp_path):
    cfg = cfg_for(tmp_path)
    build_pipeline(cfg, source=MemorySource([msg("<1@x>"), msg("<2@x>")]), extractors=[]).run()
    rep = build_pipeline(cfg, source=MemorySource([msg("<1@x>"), msg("<2@x>")]), extractors=[]).run()
    assert rep.skipped_known == 2 and rep.new_propositions == 0
