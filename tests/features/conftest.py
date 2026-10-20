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

K_COURRIEL = "Courriel"
K_DATEEVENEMENT = "dateEvenement"
K_ENTITY_URI = "entity_uri"
K_EVENEMENT = "Evenement"
K_GRAPHE_TTL = "graphe.ttl"
K_INCONNU = "inconnu"
K_MENTIONNE = "mentionne"
K_MESSAGE = "message"
K_NEW_ENTITY = "new_entity"
K_ORGANISATION = "organisation"
K_PENDING = "pending"
K_REVIEW = "review"
K_UTF_8 = "utf-8"

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
VOIR_DP = f"Voir {DP}"
LINKS_PER_PASS = 2
REGEX = {
    "dp": r"DP\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{5}",
    K_ORGANISATION: r"Cabinet [A-Z][a-z]+",
    "organisme": r"Mairie de [\w\-]+",
    "autre": r"Société [A-Z][a-z]+",
}


@dataclass
class World:  # pylint: disable=too-many-instance-attributes  # contexte partagé entre les étapes d'un scénario
    tmp: Path
    cfg: Config
    messages: list[Message] = field(default_factory=list)
    report: object = None
    error: Exception | None = None
    cli: object = None
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
    (tmp_path / K_GRAPHE_TTL).write_text(TTL, encoding=K_UTF_8)
    cfg = Config.model_validate({
        "root": str(tmp_path),
        "graph": {"files": [K_GRAPHE_TTL], "base_uri": EX, "identifier_predicates": [O + "numero"],
                  "mail_class": O + K_COURRIEL, "event_class": O + K_EVENEMENT,
                  "link_predicate": O + K_MENTIONNE, "date_predicate": O + K_DATEEVENEMENT},
        "extract": {"regex": REGEX},
    })
    w = World(tmp_path, cfg)
    w.sources_hash = {K_GRAPHE_TTL: hashlib.sha256((tmp_path / K_GRAPHE_TTL).read_bytes()).hexdigest()}
    return w


def pytest_collection_modifyitems(config, items):  # noqa: V103
    for item in items:
        for tag in ("wip", "imap"):
            if item.get_closest_marker(tag):
                item.add_marker(pytest.mark.skip(reason=f"@{tag}"))


# ── contexte commun ────────────────────────────────────────────────────────────

@given(parsers.parse('un graphe contenant la mairie "{mairie}" et le dossier "{dp}"'))  # noqa: V103
def _graphe(world, mairie, dp):
    assert mairie in TTL and dp in TTL


@given('un passage "run" ayant produit un courriel, deux liens et un événement')  # noqa: V103
def _passage(world):
    world.add_message(f"Votre {DP} est instruite par la Mairie de Plonéour-Lanvern.")
    world.run()
    assert {x.kind for x in world.props()} == {K_MESSAGE, "link", "event"}
    assert len(world.props("link")) == LINKS_PER_PASS


@when('je lance "run"')  # noqa: V103
def _run(world):
    world.run()


# ── ingestion ──────────────────────────────────────────────────────────────────

@given(parsers.parse('un message "{mid}" déjà traité lors d\'un passage précédent'))  # noqa: V103
def _deja_traite(world, mid):
    world.add_message(VOIR_DP, mid=mid)
    world.run()


@when('je lance "run" avec ce même message')  # noqa: V103
def _run_meme(world):
    world.run()


@then(parsers.parse("le rapport indique {n:d} message déjà vu"))  # noqa: V103
def _deja_vu(world, n):
    assert world.report.skipped_known == n


@then("aucune proposition n'est créée")  # noqa: V103
def _aucune_proposition(world):
    assert world.report.new_propositions == 0


@given(parsers.parse('un message dont le corps cite "{dp}" uniquement dans une citation précédée de ">"'))  # noqa: V103
def _citation(world, dp):
    world.add_message(f"Bonjour,\n> Votre {dp} est en cours.\n")


@then(parsers.parse('aucun lien vers le dossier "{dp}" n\'est proposé'))  # noqa: V103
def _pas_de_lien_dossier(world, dp):
    assert not [x for x in world.props("link") if x.payload[K_ENTITY_URI] == EX + "dp"]


@given(parsers.parse('la configuration n\'autorise que le domaine "{dom}"'))  # noqa: V103
def _allow(world, dom):
    world.cfg.filter.senders_allow = [dom]


@given(parsers.parse('un message envoyé par "{sender}"'))  # noqa: V103
def _envoye_par(world, sender):
    world.add_message(f"Votre {DP} est instruite.", sender=sender)


@then(parsers.parse("le rapport indique {n:d} message filtré"))  # noqa: V103
def _filtre(world, n):
    assert world.report.skipped_filtered == n


@then("le message est tout de même marqué comme traité")  # noqa: V103
def _marque(world):
    assert world.p.state.seen(world.messages[0].id)


@given(parsers.parse('la configuration exige un objet contenant "{motif}"'))  # noqa: V103
def _subject(world, motif):
    world.cfg.filter.subject_regex = motif


@given(parsers.parse('un message d\'objet "{objet}"'))  # noqa: V103
def _objet(world, objet):
    world.add_message(VOIR_DP, subject=objet)


# ── liaison ────────────────────────────────────────────────────────────────────

@given(parsers.parse('un message qui cite "{texte}"'))  # noqa: V103
def _cite(world, texte):
    world.add_message(f"Bonjour, voir {texte}.")


@given(parsers.parse('un message qui cite "{texte}" au libellé approchant'))  # noqa: V103
def _cite_faute(world, texte):
    world.add_message(f"Bonjour, voir {texte}.")


@given(parsers.parse('un message qui cite "{texte}", absent du graphe'))  # noqa: V103
def _cite_absent(world, texte):
    world.add_message(f"Voir le {texte} pour le recours.")


@given(parsers.parse('un message qui cite "{texte}" détecté avec la nature "{nature}"'))  # noqa: V103
def _cite_nature(world, texte, nature):
    world.add_message(f"Voir la {texte}.")


@given(parsers.parse('un message qui cite deux fois "{texte}"'))  # noqa: V103
def _cite_deux(world, texte):
    world.add_message(f"{texte} puis encore {texte}.")


@then(parsers.parse('une proposition "link" vers l\'entité du dossier est créée avec un score de 1,00'))  # noqa: V103
def _lien_dossier(world):
    links = [x for x in world.props("link") if x.payload[K_ENTITY_URI] == EX + "dp"]
    assert links and links[0].payload["score"] == 1.0


@then('une proposition "link" vers l\'entité de la mairie est créée')  # noqa: V103
def _lien_mairie(world):
    assert [x for x in world.props("link") if x.payload[K_ENTITY_URI] == EX + "mairie"]


@then(parsers.parse('la proposition "link" porte la note "{note}"'))  # noqa: V103
def _note(world, note):
    links = world.props("link")
    assert links, "aucune proposition link"
    assert note in links[0].note and links[0].confidence < world.cfg.link.link_threshold


@given(parsers.parse('la nature "{nature}" est configurée pour la classe "{classe}"'))  # noqa: V103
def _nature(world, nature, classe):
    world.cfg.graph.new_entity_kinds[nature] = O + classe


@then(parsers.parse('une proposition "new_entity" "{label}" de classe "{classe}" est créée'))  # noqa: V103
def _new_entity(world, label, classe):
    ne = world.props(K_NEW_ENTITY)
    assert [(x.payload["label"], x.payload["class_uri"]) for x in ne] == [(label, O + classe)]


@then(parsers.parse('aucune proposition "new_entity" n\'est créée'))  # noqa: V103
def _pas_new_entity(world):
    assert not world.props(K_NEW_ENTITY)


@then(parsers.parse('une seule proposition "link" vers cette entité est créée'))  # noqa: V103
def _un_seul_lien(world):
    assert len([x for x in world.props("link") if x.payload[K_ENTITY_URI] == EX + "dp"]) == 1


# ── relecture et écriture ──────────────────────────────────────────────────────

def _head(w):
    return w.props(K_MESSAGE)[0]


@when('je lance "commit" sans avoir rien accepté')  # noqa: V103
def _commit_rien(world):
    world.p.commit()


@then("le fichier de sortie ne contient aucun triplet")  # noqa: V103
def _sortie_vide(world):
    assert len(world.out_graph()) == 0


@when('j\'accepte le courriel et un lien puis je lance "commit"')  # noqa: V103
def _accepte_courriel_lien(world):
    world.accept(_head(world), world.props("link")[0])
    world.written = world.p.commit()


@then("le fichier de sortie contient le courriel typé avec sa date et son hachage")  # noqa: V103
def _courriel_ecrit(world):
    g, mail = world.out_graph(), URIRef(_head_uri(world))
    assert (mail, RDF.type, URIRef(O + K_COURRIEL)) in g
    assert any(g.objects(mail, URIRef(O + K_DATEEVENEMENT)))
    assert any(g.objects(mail, URIRef("https://example.org/mail2graph#messageHash")))


def _head_uri(w):
    return [x for x in w.p.queue._read() if x.kind == K_MESSAGE][0].payload["uri"]


@then("il contient le lien vers l'entité accepté".replace("accepté", "acceptée"))  # noqa: V103
def _lien_ecrit(world):
    g = world.out_graph()
    assert len(list(g.triples((URIRef(_head_uri(world)), URIRef(O + K_MENTIONNE), None)))) == 1


@then("il n'est pas modifié dans les fichiers sources du graphe")  # noqa: V103
def _sources_intactes(world):
    now = hashlib.sha256((world.tmp / K_GRAPHE_TTL).read_bytes()).hexdigest()
    assert now == world.sources_hash[K_GRAPHE_TTL]


@when('je rejette un lien puis je lance "commit"')  # noqa: V103
def _rejette_lien(world):
    links = world.props("link")
    world.accept(_head(world), links[0])
    world.p.queue.decide(links[1].id, False)
    world.rejected_uri = links[1].payload[K_ENTITY_URI]
    world.p.commit()


@then("ce lien n'apparaît pas dans le fichier de sortie")  # noqa: V103
def _lien_absent(world):
    g = world.out_graph()
    assert (None, URIRef(O + K_MENTIONNE), URIRef(world.rejected_uri)) not in g
    assert len(list(g.triples((None, URIRef(O + K_MENTIONNE), None)))) == 1


@when('j\'accepte un lien sans accepter son courriel puis je lance "commit"')  # noqa: V103
def _lien_sans_courriel(world):
    world.accept(world.props("link")[0])
    world.written = world.p.commit()


@then("aucun triplet n'est écrit")  # noqa: V103
def _aucun_triplet(world):
    assert world.written == 0 and len(world.out_graph()) == 0


@when('je relance "run" avec les mêmes messages')  # noqa: V103
def _relance(world):
    world.before = len(world.props())
    world.run()


@then("le nombre de propositions en attente est inchangé")  # noqa: V103
def _inchange(world):
    assert len(world.props()) == world.before


@when('j\'accepte le courriel, je lance "commit" puis je relance "commit"')  # noqa: V103
def _double_commit(world):
    world.accept(_head(world))
    world.p.commit()
    world.n1 = len(world.out_graph())
    world.second = world.p.commit()


@then("la deuxième écriture n'ajoute aucun triplet")  # noqa: V103
def _deuxieme(world):
    assert world.second == 0 and len(world.out_graph()) == world.n1


@when('je lance "review --accept-all" puis "commit"')  # noqa: V103
def _accept_all(world):
    res = CliRunner().invoke(app, [K_REVIEW, "-c", str(_cli_config(world)), "--accept-all"])
    assert res.exit_code == 0, res.output
    res = CliRunner().invoke(app, ["commit", "-c", str(_cli_config(world))])
    assert res.exit_code == 0, res.output


@then('toutes les propositions sont au statut "committed"')  # noqa: V103
def _tout_committed(world):
    data = yaml.safe_load((world.tmp / world.cfg.paths.queue).read_text())
    assert data and {d["status"] for d in data} == {"committed"}


# ── confidentialité ────────────────────────────────────────────────────────────

@given(parsers.parse('un message dont le corps contient la phrase "{phrase}"'))  # noqa: V103
def _phrase(world, phrase):
    world.add_message(f"{VOIR_DP}. {phrase}")


@when('j\'accepte tout et que je lance "commit"')  # noqa: V103
def _accepte_tout(world):
    world.run()
    world.accept(*world.props())
    world.p.commit()


@then(parsers.parse('le fichier de sortie ne contient pas "{texte}"'))  # noqa: V103
def _sortie_sans(world, texte):
    assert texte not in world.out_path.read_text(encoding=K_UTF_8)


@then(parsers.parse('il contient le domaine "{dom}"'))  # noqa: V103
def _sortie_domaine(world, dom):
    assert dom in world.out_path.read_text(encoding=K_UTF_8)


@given(parsers.parse('un message dont le corps demande "{consigne}"'))  # noqa: V103
def _consigne(world, consigne):
    world.add_message(f"{consigne}. {VOIR_DP}.")


@then("aucune proposition n'est acceptée automatiquement")  # noqa: V103
def _rien_accepte(world):
    statuts = {x.status for x in world.p.queue._read()}
    assert statuts == {K_PENDING}


@then("aucune action externe n'est déclenchée")  # noqa: V103
def _aucune_action(world):
    assert not world.out_path.exists()


@then(parsers.parse('le dossier "{dossier}" est listé dans ".gitignore"'))  # noqa: V103
def _gitignore(world, dossier):
    root = Path(__file__).resolve().parents[2]
    assert dossier in (root / ".gitignore").read_text().split()


@given(parsers.parse('la classe "{classe}" est exclue de la configuration'))  # noqa: V103
def _exclue(world, classe):
    world.cfg.graph.exclude_classes = [O + classe]


@when('je lance "run" avec un message citant une personne du graphe')  # noqa: V103
def _run_personne(world):
    world.add_message("Merci à Jean Dupont pour son aide.")
    world.run()


@then("aucun lien vers cette personne n'est proposé")  # noqa: V103
def _pas_personne(world):
    assert not [x for x in world.props("link") if x.payload[K_ENTITY_URI] == EX + "jean"]


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_config(w: World) -> Path:
    path = w.tmp / "cli.yaml"
    if not path.exists():
        mbox = (w.tmp / "c.mbox")
        mbox.write_text("From a@b.fr Tue Oct 20 10:00:00 2026\nMessage-ID: <m1@x>\nFrom: agent@mairie.fr\nSubject: Instruction\n"
                        "Date: Tue, 20 Oct 2026 10:00:00 +0000\nContent-Type: text/plain; charset=utf-8\n\n"
                        f"{VOIR_DP}.\n")
        path.write_text(yaml.safe_dump({
            "source": {"type": "mbox", "path": "c.mbox"}, "extract": {"regex": {"dp": REGEX["dp"]}},
            "graph": {"files": [K_GRAPHE_TTL], "base_uri": EX, "identifier_predicates": [O + "numero"],
                      "mail_class": O + K_COURRIEL, "event_class": O + K_EVENEMENT,
                      "link_predicate": O + K_MENTIONNE, "date_predicate": O + K_DATEEVENEMENT},
        }))
    return path


def _invoke(w, *args):
    w.cli = CliRunner().invoke(app, list(args))
    return w.cli


@when('je lance "check" avec un fichier de configuration absent')  # noqa: V103
def _check_absent(world):
    _invoke(world, "check", "-c", str(world.tmp / "absent.yaml"))


@when('je lance "check" avec une configuration valide')  # noqa: V103
def _check_ok(world):
    _invoke(world, "check", "-c", str(_cli_config(world)))


@then("la sortie indique le nombre de classes et d'entités liables")  # noqa: V103
def _check_sortie(world):
    assert re.search(r"\d+ classes, \d+ entités", world.cli.output)


@then(parsers.parse("le code de sortie est {n:d}"))  # noqa: V103
def _exit(world, n):
    assert world.cli.exit_code == n, world.cli.output


@then("le code de sortie est différent de 0")  # noqa: V103
def _exit_ko(world):
    assert world.cli.exit_code != 0


@when('je lance "run --json"')  # noqa: V103
def _run_json(world):
    _invoke(world, "run", "-c", str(_cli_config(world)), "--json")


@then('la sortie est un objet JSON avec "fetched", "new_propositions" et "pending"')  # noqa: V103
def _json(world):
    assert world.cli.exit_code == 0, world.cli.output
    assert {"fetched", "new_propositions", K_PENDING} <= set(json.loads(world.cli.output))


@given("il reste des propositions en attente")  # noqa: V103
def _reste(world):
    res = _invoke(world, "run", "-c", str(_cli_config(world)))
    assert res.exit_code == 0, res.output
    world.pending_before = _pending(world)
    assert world.pending_before


def _pending(w):
    data = yaml.safe_load((w.tmp / "staging/propositions.yaml").read_text())
    return [d for d in data if d["status"] == K_PENDING]


@when('je lance "run --fail-if-pending"')  # noqa: V103
def _fail_if_pending(world):
    _invoke(world, "run", "-c", str(_cli_config(world)), "--fail-if-pending")


@when('je lance "review --json"')  # noqa: V103
def _review_json(world):
    _invoke(world, K_REVIEW, "-c", str(_cli_config(world)), "--json")


@then("la sortie liste les propositions en attente")  # noqa: V103
def _liste(world):
    assert len(json.loads(world.cli.output)[K_PENDING]) == len(world.pending_before)


@then("aucune décision n'est enregistrée")  # noqa: V103
def _aucune_decision(world):
    assert len(_pending(world)) == len(world.pending_before)


@when('je lance "review --accept inconnu"')  # noqa: V103
def _accept_inconnu(world):
    _invoke(world, K_REVIEW, "-c", str(_cli_config(world)), "--accept", K_INCONNU)


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


@given(parsers.parse('un paquet déclarant une source dans le groupe "{groupe}"'))  # noqa: V103
def _plugin_source(world, monkeypatch, groupe):
    msgs = [Message("<p@x>", "Plugin", "a@b.fr", datetime(2026, 10, 21, tzinfo=timezone.utc), VOIR_DP)]
    _patch_entry_points(monkeypatch, groupe, "fake", lambda cfg: MemorySource(msgs))


@when("la configuration indique ce type de source")  # noqa: V103
def _type_source(world):
    world.cfg.source.type = "fake"


@then("le pipeline lit les messages de ce plugin")  # noqa: V103
def _lit_plugin(world):
    p = build_pipeline(world.cfg)
    assert p.run().fetched == 1


class _FakeExtractor:
    def extract(self, message, ctx):
        from mail2graph.domain import Mention
        return [Mention(message.id, K_ORGANISATION, "Cabinet Durand", 0.9)]


@given(parsers.parse('un extracteur de plugin renvoyant la mention "{texte}"'))  # noqa: V103
def _plugin_extracteur(world, monkeypatch):
    _patch_entry_points(monkeypatch, "mail2graph.extractors", "fake", lambda cfg: _FakeExtractor())
    world.cfg.extract.regex = {}
    world.cfg.graph.new_entity_kinds = {K_ORGANISATION: O + "Organisme"}
    world.add_message("Un message sans rien de reconnaissable.")


@when(parsers.parse('je l\'active dans "{cle}"'))  # noqa: V103
def _active(world, cle):
    assert cle == "extract.plugins"
    world.cfg.extract.plugins = ["fake"]
    world.run()


@then("ses mentions sont liées comme celles des extracteurs intégrés")  # noqa: V103
def _mentions_plugin(world):
    assert [x.payload["label"] for x in world.props(K_NEW_ENTITY)] == ["Cabinet Durand"]


@when("la configuration nomme un plugin inexistant")  # noqa: V103
def _inexistant(world):
    world.cfg.extract.plugins = [K_INCONNU]
    try:
        build_pipeline(world.cfg)
    except Exception as e:  # noqa: BLE001 - on vérifie le message
        world.error = e


@then("l'erreur indique le nom du plugin et son groupe")  # noqa: V103
def _erreur(world):
    assert world.error is not None and K_INCONNU in str(world.error) and "mail2graph.extractors" in str(world.error)


@given("une source et un extracteur construits par l'appelant")  # noqa: V103
def _adaptateurs_appelant(world):
    world.add_message("Rien à voir.")
    world.my_extractor = _FakeExtractor()


@when('j\'appelle "build_pipeline" avec ces adaptateurs')  # noqa: V103
def _appelle(world):
    world.p = build_pipeline(world.cfg, source=MemorySource(world.messages), extractors=[world.my_extractor])


@then("le pipeline les utilise à la place de ceux de la configuration")  # noqa: V103
def _utilise(world):
    assert world.p.extractors == [world.my_extractor]
    assert world.p.run().fetched == 1


@then('"domain.py", "ports.py" et "pipeline.py" n\'importent rien de "mail2graph.adapters"')  # noqa: V103
def _coeur_pur(world):
    src = Path(__file__).resolve().parents[2] / "src" / "mail2graph"
    for name in ("domain.py", "ports.py", "pipeline.py"):
        for node in ast.walk(ast.parse((src / name).read_text())):
            mods = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            assert not any("adapters" in m for m in mods), f"{name} importe {mods}"


# ── qualité du graphe ──────────────────────────────────────────────────────────

@when('je lance "commit"')  # noqa: V103
def _commit_simple(world):
    world.snapshot = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in world.tmp.iterdir() if p.is_file()}
    world.p.commit()


@then("seuls le fichier de sortie configuré et la file de relecture changent")  # noqa: V103
def _seuls_sortie(world):
    now = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in world.tmp.iterdir() if p.is_file()}
    changed = {n for n in now if now[n] != world.snapshot.get(n)}
    assert changed <= {world.cfg.graph.output_file}


@when("j'accepte un événement")  # noqa: V103
def _accepte_evenement(world):
    world.accept(_head(world), world.props("event")[0])
    world.p.commit()


@then("il porte la date du message et une provenance vers le courriel")  # noqa: V103
def _evenement(world):
    g = world.out_graph()
    ev = URIRef(_head_uri(world) + "-evenement")
    assert (ev, RDF.type, URIRef(O + K_EVENEMENT)) in g
    assert str(next(g.objects(ev, URIRef(O + K_DATEEVENEMENT)))) == "2026-10-21"
    assert (ev, URIRef("http://www.w3.org/ns/prov#wasDerivedFrom"), URIRef(_head_uri(world))) in g
