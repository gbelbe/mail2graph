from datetime import datetime, timezone

from rdflib import RDF, Graph, URIRef

from mail2graph import Config, Message, build_pipeline
from mail2graph.adapters.sources import MemorySource
from mail2graph.domain import clean_body, link_decision, normalize

TTL = """
@prefix ex: <https://example.org/dossier/> .
@prefix o: <https://example.org/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
o:Mairie a owl:Class ; rdfs:label "Mairie"@fr .
o:Dossier a owl:Class ; rdfs:label "Dossier"@fr .
ex:mairie a o:Mairie ; rdfs:label "Mairie de Plonéour-Lanvern"@fr .
ex:dp a o:Dossier ; rdfs:label "Déclaration préalable"@fr ; o:numero "DP 029 174 26 00122" .
"""


def make_cfg(tmp_path):
    (tmp_path / "graphe.ttl").write_text(TTL, encoding="utf-8")
    return Config.model_validate({
        "root": str(tmp_path),
        "graph": {"files": ["graphe.ttl"], "base_uri": "https://example.org/dossier/",
                  "identifier_predicates": ["https://example.org/ontology#numero"],
                  "new_entity_kinds": {"organisation": "https://example.org/ontology#Organisme"}},
        "extract": {"regex": {"dp": r"DP\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{5}",
                              "organisation": r"Cabinet [A-Z][a-z]+"}},
    })


def msg(i="<1@x>", body="Votre DP 029 174 26 00122 est instruite par la Mairie de Plonéour-Lanvern.\n> citation\n-- \nsignature"):
    return Message(i, "Instruction", "agent@mairie.fr", datetime(2026, 10, 21, tzinfo=timezone.utc), body)


def test_clean_body_and_helpers():
    assert clean_body("Bonjour\n> ancien\n-- \nSig") == "Bonjour"
    assert normalize("Plonéour-Lanvern") == "ploneour lanvern"
    assert link_decision(0.95, 0.9, 0.7) == "link"
    assert link_decision(0.8, 0.9, 0.7) == "suggest"
    assert link_decision(0.5, 0.9, 0.7) == "none"


def test_run_links_known_entities_and_is_idempotent(tmp_path):
    cfg = make_cfg(tmp_path)
    p = build_pipeline(cfg, source=MemorySource([msg()]))
    r1 = p.run()
    assert r1.new_propositions >= 3
    kinds = {x.kind for x in p.queue.pending()}
    assert {"message", "link", "event"} <= kinds
    links = {x.payload["entity_uri"] for x in p.queue.pending() if x.kind == "link"}
    assert links == {"https://example.org/dossier/mairie", "https://example.org/dossier/dp"}
    r2 = build_pipeline(cfg, source=MemorySource([msg()])).run()
    assert r2.skipped_known == 1 and r2.new_propositions == 0


def test_unknown_organisation_becomes_new_entity_proposal(tmp_path):
    cfg = make_cfg(tmp_path)
    p = build_pipeline(cfg, source=MemorySource([msg("<2@x>", "Voir le Cabinet Durand pour le recours.")]))
    p.run()
    ne = [x for x in p.queue.pending() if x.kind == "new_entity"]
    assert [x.payload["label"] for x in ne] == ["Cabinet Durand"]


def test_filter_skips_other_senders(tmp_path):
    cfg = make_cfg(tmp_path)
    cfg.filter.senders_allow = ["autre.fr"]
    p = build_pipeline(cfg, source=MemorySource([msg()]))
    rep = p.run()
    assert rep.skipped_filtered == 1 and not p.queue.pending()


def test_commit_only_writes_accepted(tmp_path):
    cfg = make_cfg(tmp_path)
    p = build_pipeline(cfg, source=MemorySource([msg()]))
    p.run()
    head = next(x for x in p.queue.pending() if x.kind == "message")
    link = next(x for x in p.queue.pending() if x.kind == "link")
    p.queue.decide(head.id, True)
    p.queue.decide(link.id, True)
    assert p.commit() == 2
    g = Graph().parse(tmp_path / cfg.graph.output_file)
    mail = URIRef(head.payload["uri"])
    assert (mail, RDF.type, URIRef(cfg.graph.mail_class)) in g
    assert (mail, URIRef(cfg.graph.link_predicate), URIRef(link.payload["entity_uri"])) in g
    assert not any(g.triples((None, RDF.type, URIRef(cfg.graph.event_class))))  # événement non accepté


def test_child_without_accepted_parent_is_not_written(tmp_path):
    cfg = make_cfg(tmp_path)
    p = build_pipeline(cfg, source=MemorySource([msg()]))
    p.run()
    link = next(x for x in p.queue.pending() if x.kind == "link")
    p.queue.decide(link.id, True)
    assert p.commit() == 0


def test_no_body_or_address_in_graph(tmp_path):
    cfg = make_cfg(tmp_path)
    p = build_pipeline(cfg, source=MemorySource([msg()]))
    p.run()
    for x in p.queue.pending():
        p.queue.decide(x.id, True)
    p.commit()
    text = (tmp_path / cfg.graph.output_file).read_text(encoding="utf-8")
    assert "agent@mairie.fr" not in text and "signature" not in text and "citation" not in text


def test_mbox_source_reads_messages(tmp_path):
    from mail2graph.adapters.sources import MboxSource
    p = tmp_path / "c.mbox"
    p.write_text("From a@b.fr Tue Oct 20 10:00:00 2026\nMessage-ID: <m1@x>\nFrom: a@b.fr\nSubject: Test\n"
                 "Date: Tue, 20 Oct 2026 10:00:00 +0000\nContent-Type: text/plain; charset=utf-8\n\nBonjour DP 029 174 26 00122\n")
    ms = list(MboxSource(str(p)).fetch())
    assert len(ms) == 1 and ms[0].id == "<m1@x>" and "DP 029" in ms[0].body and ms[0].sender_domain == "b.fr"
