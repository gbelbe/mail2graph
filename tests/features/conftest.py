"""Définitions d'étapes pytest-bdd. Aucune connexion réseau : sources en mémoire ou mbox, graphe Turtle minimal."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, parsers, then, when
from rdflib import RDF, Graph, URIRef
from typer.testing import CliRunner

from mail2graph import Config, Message, build_pipeline
from mail2graph.adapters.sources import MemorySource
from mail2graph.cli import app

O = "https://example.org/ontology#"
EX = "https://example.org/dossier/"
TTL = """
@prefix ex: <https://example.org/dossier/> .
@prefix o: <https://example.org/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
o:Mairie a owl:Class ; rdfs:label "Mairie"@fr .
o:Dossier a owl:Class ; rdfs:label "Dossier"@fr .
o:Personne a owl:Class ; rdfs:label "Personne"@fr .
ex:mairie a o:Mairie ; rdfs:label "Mairie de Plonéour-Lanvern"@fr .
ex:dp a o:Dossier ; rdfs:label "Déclaration préalable"@fr ; o:numero "DP 029 174 26 00122" .
ex:jean a o:Personne ; rdfs:label "Jean Dupont"@fr .
"""
DP = "DP 029 174 26 00122"
REGEX = {
    "dp": r"DP\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{5}",
    "organisation": r"Cabinet [A-Z][a-z]+",
    "organisme": r"Mairie de [\w\-]+",
    "autre": r"Société [A-Z][a-z]+",
}


@dataclass
class World:
    tmp: Path
    cfg: Config
    messages: list[Message] = field(default_factory=list)
    report: object = None
    error: Exception | None = None
    cli: object = None
    out_before: int = 0
    sources_hash: dict[str, str] = field(default_factory=dict)
    _n: int = 0

    def add_message(self, body: str, sender: str = "agent@mairie.fr", subject: str = "Instruction", mid: str | None = None) -> Message:
        self._n += 1
        m = Message(mid or f"<{self._n}@x>", subject, sender, datetime(2026, 10, 21, tzinfo=timezone.utc), body)
        self.messages.append(m)
        return m

    def pipeline(self, **override):
        return build_pipeline(self.cfg, source=MemorySource(self.messages), **override)

    def run(self):
        self.p = self.pipeline()
        self.report = self.p.run()
        return self.report

    @property
    def out_path(self) -> Path:
        return self.tmp / self.cfg.graph.output_file

    def out_graph(self) -> Graph:
        g = Graph()
        if self.out_path.exists():
            g.parse(self.out_path)
        return g

    def props(self, kind: str | None = None):
        return [x for x in self.p.queue.pending() if kind is None or x.kind == kind]

    def accept(self, *props):
        for x in props:
            self.p.queue.decide(x.id, True)


@pytest.fixture
def world(tmp_path) -> World:
    (tmp_path / "graphe.ttl").write_text(TTL, encoding="utf-8")
    cfg = Config.model_validate({
        "root": str(tmp_path),
        "graph": {"files": ["graphe.ttl"], "base_uri": EX, "identifier_predicates": [O + "numero"],
                  "mail_class": O + "Courriel", "event_class": O + "Evenement",
                  "link_predicate": O + "mentionne", "date_predicate": O + "dateEvenement"},
        "extract": {"regex": REGEX},
    })
    w = World(tmp_path, cfg)
    w.sources_hash = {"graphe.ttl": hashlib.sha256((tmp_path / "graphe.ttl").read_bytes()).hexdigest()}
    return w


def pytest_collection_modifyitems(config, items):
    for item in items:
        for tag in ("wip", "imap"):
            if item.get_closest_marker(tag):
                item.add_marker(pytest.mark.skip(reason=f"@{tag}"))


# ── contexte commun ────────────────────────────────────────────────────────────

@given(parsers.parse('un graphe contenant la mairie "{mairie}" et le dossier "{dp}"'))
def _graphe(world, mairie, dp):
    assert mairie in TTL and dp in TTL


@given('un passage "run" ayant produit un courriel, deux liens et un événement')
def _passage(world):
    world.add_message(f"Votre {DP} est instruite par la Mairie de Plonéour-Lanvern.")
    world.run()
    assert {x.kind for x in world.props()} == {"message", "link", "event"}
    assert len(world.props("link")) == 2


@when('je lance "run"')
def _run(world):
    world.run()


# ── ingestion ──────────────────────────────────────────────────────────────────

@given(parsers.parse('un message "{mid}" déjà traité lors d\'un passage précédent'))
def _deja_traite(world, mid):
    world.add_message(f"Voir {DP}", mid=mid)
    world.run()


@when('je lance "run" avec ce même message')
def _run_meme(world):
    world.run()


@then(parsers.parse("le rapport indique {n:d} message déjà vu"))
def _deja_vu(world, n):
    assert world.report.skipped_known == n


@then("aucune proposition n'est créée")
def _aucune_proposition(world):
    assert world.report.new_propositions == 0


@given(parsers.parse('un message dont le corps cite "{dp}" uniquement dans une citation précédée de ">"'))
def _citation(world, dp):
    world.add_message(f"Bonjour,\n> Votre {dp} est en cours.\n")


@then(parsers.parse('aucun lien vers le dossier "{dp}" n\'est proposé'))
def _pas_de_lien_dossier(world, dp):
    assert not [x for x in world.props("link") if x.payload["entity_uri"] == EX + "dp"]


@given(parsers.parse('la configuration n\'autorise que le domaine "{dom}"'))
def _allow(world, dom):
    world.cfg.filter.senders_allow = [dom]


@given(parsers.parse('un message envoyé par "{sender}"'))
def _envoye_par(world, sender):
    world.add_message(f"Votre {DP} est instruite.", sender=sender)


@then(parsers.parse("le rapport indique {n:d} message filtré"))
def _filtre(world, n):
    assert world.report.skipped_filtered == n


@then("le message est tout de même marqué comme traité")
def _marque(world):
    assert world.p.state.seen(world.messages[0].id)


@given(parsers.parse('la configuration exige un objet contenant "{motif}"'))
def _subject(world, motif):
    world.cfg.filter.subject_regex = motif


@given(parsers.parse('un message d\'objet "{objet}"'))
def _objet(world, objet):
    world.add_message(f"Voir {DP}", subject=objet)


# ── liaison ────────────────────────────────────────────────────────────────────

@given(parsers.parse('un message qui cite "{texte}"'))
def _cite(world, texte):
    world.add_message(f"Bonjour, voir {texte}.")


@given(parsers.parse('un message qui cite "{texte}" au libellé approchant'))
def _cite_faute(world, texte):
    world.add_message(f"Bonjour, voir {texte}.")


@given(parsers.parse('un message qui cite "{texte}", absent du graphe'))
def _cite_absent(world, texte):
    world.add_message(f"Voir le {texte} pour le recours.")


@given(parsers.parse('un message qui cite "{texte}" détecté avec la nature "{nature}"'))
def _cite_nature(world, texte, nature):
    world.add_message(f"Voir la {texte}.")


@given(parsers.parse('un message qui cite deux fois "{texte}"'))
def _cite_deux(world, texte):
    world.add_message(f"{texte} puis encore {texte}.")


@then(parsers.parse('une proposition "link" vers l\'entité du dossier est créée avec un score de 1,00'))
def _lien_dossier(world):
    links = [x for x in world.props("link") if x.payload["entity_uri"] == EX + "dp"]
    assert links and links[0].payload["score"] == 1.0


@then('une proposition "link" vers l\'entité de la mairie est créée')
def _lien_mairie(world):
    assert [x for x in world.props("link") if x.payload["entity_uri"] == EX + "mairie"]


@then(parsers.parse('la proposition "link" porte la note "{note}"'))
def _note(world, note):
    links = world.props("link")
    assert links, "aucune proposition link"
    assert note in links[0].note and links[0].confidence < world.cfg.link.link_threshold


@given(parsers.parse('la nature "{nature}" est configurée pour la classe "{classe}"'))
def _nature(world, nature, classe):
    world.cfg.graph.new_entity_kinds[nature] = O + classe


@then(parsers.parse('une proposition "new_entity" "{label}" de classe "{classe}" est créée'))
def _new_entity(world, label, classe):
    ne = world.props("new_entity")
    assert [(x.payload["label"], x.payload["class_uri"]) for x in ne] == [(label, O + classe)]


@then(parsers.parse('aucune proposition "new_entity" n\'est créée'))
def _pas_new_entity(world):
    assert not world.props("new_entity")


@then(parsers.parse('une seule proposition "link" vers cette entité est créée'))
def _un_seul_lien(world):
    assert len([x for x in world.props("link") if x.payload["entity_uri"] == EX + "dp"]) == 1


# ── relecture et écriture ──────────────────────────────────────────────────────

def _head(w):
    return w.props("message")[0]


@when('je lance "commit" sans avoir rien accepté')
def _commit_rien(world):
    world.p.commit()


@then("le fichier de sortie ne contient aucun triplet")
def _sortie_vide(world):
    assert len(world.out_graph()) == 0


@when('j\'accepte le courriel et un lien puis je lance "commit"')
def _accepte_courriel_lien(world):
    world.accept(_head(world), world.props("link")[0])
    world.written = world.p.commit()


@then("le fichier de sortie contient le courriel typé avec sa date et son hachage")
def _courriel_ecrit(world):
    g, mail = world.out_graph(), URIRef(_head_uri(world))
    assert (mail, RDF.type, URIRef(O + "Courriel")) in g
    assert any(g.objects(mail, URIRef(O + "dateEvenement")))
    assert any(g.objects(mail, URIRef("https://example.org/mail2graph#messageHash")))


def _head_uri(w):
    return [x for x in w.p.queue._read() if x.kind == "message"][0].payload["uri"]


@then("il contient le lien vers l'entité accepté".replace("accepté", "acceptée"))
def _lien_ecrit(world):
    g = world.out_graph()
    assert len(list(g.triples((URIRef(_head_uri(world)), URIRef(O + "mentionne"), None)))) == 1


@then("il n'est pas modifié dans les fichiers sources du graphe")
def _sources_intactes(world):
    now = hashlib.sha256((world.tmp / "graphe.ttl").read_bytes()).hexdigest()
    assert now == world.sources_hash["graphe.ttl"]


@when('je rejette un lien puis je lance "commit"')
def _rejette_lien(world):
    links = world.props("link")
    world.accept(_head(world), links[0])
    world.p.queue.decide(links[1].id, False)
    world.rejected_uri = links[1].payload["entity_uri"]
    world.p.commit()


@then("ce lien n'apparaît pas dans le fichier de sortie")
def _lien_absent(world):
    g = world.out_graph()
    assert (None, URIRef(O + "mentionne"), URIRef(world.rejected_uri)) not in g
    assert len(list(g.triples((None, URIRef(O + "mentionne"), None)))) == 1


@when('j\'accepte un lien sans accepter son courriel puis je lance "commit"')
def _lien_sans_courriel(world):
    world.accept(world.props("link")[0])
    world.written = world.p.commit()


@then("aucun triplet n'est écrit")
def _aucun_triplet(world):
    assert world.written == 0 and len(world.out_graph()) == 0


@when('je relance "run" avec les mêmes messages')
def _relance(world):
    world.before = len(world.props())
    world.run()


@then("le nombre de propositions en attente est inchangé")
def _inchange(world):
    assert len(world.props()) == world.before


@when('j\'accepte le courriel, je lance "commit" puis je relance "commit"')
def _double_commit(world):
    world.accept(_head(world))
    world.p.commit()
    world.n1 = len(world.out_graph())
    world.second = world.p.commit()


@then("la deuxième écriture n'ajoute aucun triplet")
def _deuxieme(world):
    assert world.second == 0 and len(world.out_graph()) == world.n1


@when('je lance "review --accept-all" puis "commit"')
def _accept_all(world):
    res = CliRunner().invoke(app, ["review", "-c", str(_cli_config(world)), "--accept-all"])
    assert res.exit_code == 0, res.output
    res = CliRunner().invoke(app, ["commit", "-c", str(_cli_config(world))])
    assert res.exit_code == 0, res.output


@then('toutes les propositions sont au statut "committed"')
def _tout_committed(world):
    data = yaml.safe_load((world.tmp / world.cfg.paths.queue).read_text())
    assert data and {d["status"] for d in data} == {"committed"}


# ── confidentialité ────────────────────────────────────────────────────────────

@given(parsers.parse('un message dont le corps contient la phrase "{phrase}"'))
def _phrase(world, phrase):
    world.add_message(f"Voir {DP}. {phrase}")


@when('j\'accepte tout et que je lance "commit"')
def _accepte_tout(world):
    world.run()
    world.accept(*world.props())
    world.p.commit()


@then(parsers.parse('le fichier de sortie ne contient pas "{texte}"'))
def _sortie_sans(world, texte):
    assert texte not in world.out_path.read_text(encoding="utf-8")


@then(parsers.parse('il contient le domaine "{dom}"'))
def _sortie_domaine(world, dom):
    assert dom in world.out_path.read_text(encoding="utf-8")


@given(parsers.parse('un message dont le corps demande "{consigne}"'))
def _consigne(world, consigne):
    world.add_message(f"{consigne}. Voir {DP}.")


@then("aucune proposition n'est acceptée automatiquement")
def _rien_accepte(world):
    statuts = {x.status for x in world.p.queue._read()}
    assert statuts == {"pending"}


@then("aucune action externe n'est déclenchée")
def _aucune_action(world):
    assert not world.out_path.exists()


@then(parsers.parse('le dossier "{dossier}" est listé dans ".gitignore"'))
def _gitignore(world, dossier):
    root = Path(__file__).resolve().parents[2]
    assert dossier in (root / ".gitignore").read_text().split()


@given(parsers.parse('la classe "{classe}" est exclue de la configuration'))
def _exclue(world, classe):
    world.cfg.graph.exclude_classes = [O + classe]


@when('je lance "run" avec un message citant une personne du graphe')
def _run_personne(world):
    world.add_message("Merci à Jean Dupont pour son aide.")
    world.run()


@then("aucun lien vers cette personne n'est proposé")
def _pas_personne(world):
    assert not [x for x in world.props("link") if x.payload["entity_uri"] == EX + "jean"]


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_config(w: World) -> Path:
    path = w.tmp / "cli.yaml"
    if not path.exists():
        mbox = (w.tmp / "c.mbox")
        mbox.write_text("From a@b.fr Tue Oct 20 10:00:00 2026\nMessage-ID: <m1@x>\nFrom: agent@mairie.fr\nSubject: Instruction\n"
                        "Date: Tue, 20 Oct 2026 10:00:00 +0000\nContent-Type: text/plain; charset=utf-8\n\n"
                        f"Voir {DP}.\n")
        path.write_text(yaml.safe_dump({
            "source": {"type": "mbox", "path": "c.mbox"}, "extract": {"regex": {"dp": REGEX["dp"]}},
            "graph": {"files": ["graphe.ttl"], "base_uri": EX, "identifier_predicates": [O + "numero"],
                      "mail_class": O + "Courriel", "event_class": O + "Evenement",
                      "link_predicate": O + "mentionne", "date_predicate": O + "dateEvenement"},
        }))
    return path


def _invoke(w, *args):
    w.cli = CliRunner().invoke(app, list(args))
    return w.cli


@when('je lance "check" avec un fichier de configuration absent')
def _check_absent(world):
    _invoke(world, "check", "-c", str(world.tmp / "absent.yaml"))


@when('je lance "check" avec une configuration valide')
def _check_ok(world):
    _invoke(world, "check", "-c", str(_cli_config(world)))


@then("la sortie indique le nombre de classes et d'entités liables")
def _check_sortie(world):
    assert re.search(r"\d+ classes, \d+ entités", world.cli.output)


@then(parsers.parse("le code de sortie est {n:d}"))
def _exit(world, n):
    assert world.cli.exit_code == n, world.cli.output


@then("le code de sortie est différent de 0")
def _exit_ko(world):
    assert world.cli.exit_code != 0


@when('je lance "run --json"')
def _run_json(world):
    _invoke(world, "run", "-c", str(_cli_config(world)), "--json")


@then('la sortie est un objet JSON avec "fetched", "new_propositions" et "pending"')
def _json(world):
    assert world.cli.exit_code == 0, world.cli.output
    assert {"fetched", "new_propositions", "pending"} <= set(json.loads(world.cli.output))


@given("il reste des propositions en attente")
def _reste(world):
    res = _invoke(world, "run", "-c", str(_cli_config(world)))
    assert res.exit_code == 0, res.output
    world.pending_before = _pending(world)
    assert world.pending_before


def _pending(w):
    data = yaml.safe_load((w.tmp / "staging/propositions.yaml").read_text())
    return [d for d in data if d["status"] == "pending"]


@when('je lance "run --fail-if-pending"')
def _fail_if_pending(world):
    _invoke(world, "run", "-c", str(_cli_config(world)), "--fail-if-pending")


@when('je lance "review --json"')
def _review_json(world):
    _invoke(world, "review", "-c", str(_cli_config(world)), "--json")


@then("la sortie liste les propositions en attente")
def _liste(world):
    assert len(json.loads(world.cli.output)["pending"]) == len(world.pending_before)


@then("aucune décision n'est enregistrée")
def _aucune_decision(world):
    assert len(_pending(world)) == len(world.pending_before)


@when('je lance "review --accept inconnu"')
def _accept_inconnu(world):
    _invoke(world, "review", "-c", str(_cli_config(world)), "--accept", "inconnu")


# ── extensibilité ──────────────────────────────────────────────────────────────

class _EP:
    def __init__(self, name, obj):
        self.name, self._obj = name, obj

    def load(self):
        return self._obj


def _patch_entry_points(monkeypatch, group, name, obj):
    import mail2graph.factory as factory

    def fake(group: str):
        return [_EP(name, obj)] if group == target else []
    target = group
    monkeypatch.setattr(factory, "entry_points", fake)


@given(parsers.parse('un paquet déclarant une source dans le groupe "{groupe}"'))
def _plugin_source(world, monkeypatch, groupe):
    msgs = [Message("<p@x>", "Plugin", "a@b.fr", datetime(2026, 10, 21, tzinfo=timezone.utc), f"Voir {DP}")]
    _patch_entry_points(monkeypatch, groupe, "fake", lambda cfg: MemorySource(msgs))


@when("la configuration indique ce type de source")
def _type_source(world):
    world.cfg.source.type = "fake"


@then("le pipeline lit les messages de ce plugin")
def _lit_plugin(world):
    p = build_pipeline(world.cfg)
    assert p.run().fetched == 1


class _FakeExtractor:
    def extract(self, message, ctx):
        from mail2graph.domain import Mention
        return [Mention(message.id, "organisation", "Cabinet Durand", 0.9)]


@given(parsers.parse('un extracteur de plugin renvoyant la mention "{texte}"'))
def _plugin_extracteur(world, monkeypatch):
    _patch_entry_points(monkeypatch, "mail2graph.extractors", "fake", lambda cfg: _FakeExtractor())
    world.cfg.extract.regex = {}
    world.cfg.graph.new_entity_kinds = {"organisation": O + "Organisme"}
    world.add_message("Un message sans rien de reconnaissable.")


@when(parsers.parse('je l\'active dans "{cle}"'))
def _active(world, cle):
    world.cfg.extract.plugins = ["fake"]
    world.run()


@then("ses mentions sont liées comme celles des extracteurs intégrés")
def _mentions_plugin(world):
    assert [x.payload["label"] for x in world.props("new_entity")] == ["Cabinet Durand"]


@when("la configuration nomme un plugin inexistant")
def _inexistant(world):
    world.cfg.extract.plugins = ["inconnu"]
    try:
        build_pipeline(world.cfg)
    except Exception as e:  # noqa: BLE001 - on vérifie le message
        world.error = e


@then("l'erreur indique le nom du plugin et son groupe")
def _erreur(world):
    assert world.error is not None and "inconnu" in str(world.error) and "mail2graph.extractors" in str(world.error)


@given("une source et un extracteur construits par l'appelant")
def _adaptateurs_appelant(world):
    world.add_message("Rien à voir.")
    world.my_extractor = _FakeExtractor()


@when('j\'appelle "build_pipeline" avec ces adaptateurs')
def _appelle(world):
    world.p = build_pipeline(world.cfg, source=MemorySource(world.messages), extractors=[world.my_extractor])


@then("le pipeline les utilise à la place de ceux de la configuration")
def _utilise(world):
    assert world.p.extractors == [world.my_extractor]
    assert world.p.run().fetched == 1


@then('"domain.py", "ports.py" et "pipeline.py" n\'importent rien de "mail2graph.adapters"')
def _coeur_pur(world):
    src = Path(__file__).resolve().parents[2] / "src" / "mail2graph"
    for name in ("domain.py", "ports.py", "pipeline.py"):
        for node in ast.walk(ast.parse((src / name).read_text())):
            mods = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            assert not any("adapters" in m for m in mods), f"{name} importe {mods}"


# ── qualité du graphe ──────────────────────────────────────────────────────────

@when('je lance "commit"')
def _commit_simple(world):
    world.snapshot = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in world.tmp.iterdir() if p.is_file()}
    world.p.commit()


@then("seuls le fichier de sortie configuré et la file de relecture changent")
def _seuls_sortie(world):
    now = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in world.tmp.iterdir() if p.is_file()}
    changed = {n for n in now if now[n] != world.snapshot.get(n)}
    assert changed <= {world.cfg.graph.output_file}


@when("j'accepte un événement")
def _accepte_evenement(world):
    world.accept(_head(world), world.props("event")[0])
    world.p.commit()


@then("il porte la date du message et une provenance vers le courriel")
def _evenement(world):
    g = world.out_graph()
    ev = URIRef(_head_uri(world) + "-evenement")
    assert (ev, RDF.type, URIRef(O + "Evenement")) in g
    assert str(next(g.objects(ev, URIRef(O + "dateEvenement")))) == "2026-10-21"
    assert (ev, URIRef("http://www.w3.org/ns/prov#wasDerivedFrom"), URIRef(_head_uri(world))) in g
