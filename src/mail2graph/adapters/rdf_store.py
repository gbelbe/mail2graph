"""Graphe RDF sur fichiers Turtle (rdflib). Lit le graphe existant, écrit les ajouts validés dans un fichier à part."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, PROV, SKOS

from ..config import GraphCfg
from ..domain import ClassInfo, EntityRef, GraphContext, Proposition

M2G = Namespace("https://example.org/mail2graph#")


def _label(g: Graph, s) -> str:
    for p in (SKOS.prefLabel, RDFS.label):
        vals = sorted(g.objects(s, p), key=lambda l: (getattr(l, "language", "") != "fr", str(l)))
        if vals:
            return str(vals[0])
    return ""


class RdfGraphStore:
    def __init__(self, cfg: GraphCfg, root: Path):
        self.cfg, self.root = cfg, root
        self.out_path = root / cfg.output_file

    def _load(self) -> Graph:
        g = Graph()
        out = self.out_path.resolve()
        for pat in self.cfg.files:
            for f in sorted(self.root.glob(pat)):
                if f.is_file() and f.resolve() != out and f.suffix in (".ttl", ".nt", ".rdf", ".jsonld"):
                    g.parse(f)
        return g

    def context(self) -> GraphContext:
        g = self._load()
        classes = tuple(ClassInfo(str(c), _label(g, c) or str(c)) for c in sorted(set(g.subjects(RDF.type, OWL.Class))) if isinstance(c, URIRef))
        skip = {URIRef(c) for c in self.cfg.exclude_classes} | {URIRef(self.cfg.mail_class)}
        idp = [URIRef(p) for p in self.cfg.identifier_predicates]
        ents: dict[str, EntityRef] = {}
        for s, t in g.subject_objects(RDF.type):
            if not isinstance(s, URIRef) or t in skip or str(t).startswith(str(OWL)) or str(t).startswith(str(SKOS)):
                continue
            names = {str(o) for p in (RDFS.label, SKOS.prefLabel, SKOS.altLabel) for o in g.objects(s, p)}
            names |= {str(o) for p in idp for o in g.objects(s, p)}
            if names and str(s) not in ents:
                ents[str(s)] = EntityRef(str(s), _label(g, s) or sorted(names)[0], str(t), tuple(sorted(names)))
        return GraphContext(classes, tuple(ents.values()))

    def commit(self, accepted: Sequence[Proposition]) -> int:
        out = Graph()
        if self.out_path.exists():
            out.parse(self.out_path)
        out.bind("m2g", M2G)
        out.bind("prov", PROV)
        cfg = self.cfg
        done = 0
        by_id = {p.id: p for p in accepted}
        for p in sorted(accepted, key=lambda p: p.kind != "message"):
            d = p.payload
            if p.parent and p.parent not in by_id and (URIRef(d["mail_uri"]), RDF.type, URIRef(cfg.mail_class)) not in out:
                continue                          # l'enfant d'un courriel non validé n'entre pas
            if p.kind == "message":
                m = URIRef(d["uri"])
                out.add((m, RDF.type, URIRef(cfg.mail_class)))
                out.add((m, RDFS.label, Literal(d["subject"], lang="fr")))
                out.add((m, URIRef(cfg.date_predicate), Literal(d["date"], datatype=XSD.date)))
                out.add((m, M2G.messageHash, Literal(d["hash"])))
                if d.get("sender_domain"):
                    out.add((m, M2G.expediteurDomaine, Literal(d["sender_domain"])))
            elif p.kind == "link":
                out.add((URIRef(d["mail_uri"]), URIRef(cfg.link_predicate), URIRef(d["entity_uri"])))
            elif p.kind == "new_entity":
                uri = URIRef(cfg.base_uri + "mail-" + hashlib.sha1((d["label"] + d["mail_uri"]).encode()).hexdigest()[:10])
                if d.get("class_uri"):
                    out.add((uri, RDF.type, URIRef(d["class_uri"])))
                out.add((uri, RDFS.label, Literal(d["label"], lang="fr")))
                out.add((uri, PROV.wasDerivedFrom, URIRef(d["mail_uri"])))
                out.add((URIRef(d["mail_uri"]), URIRef(cfg.link_predicate), uri))
            elif p.kind == "event":
                ev = URIRef(d["mail_uri"] + "-evenement")
                out.add((ev, RDF.type, URIRef(cfg.event_class)))
                out.add((ev, RDFS.label, Literal(d["label"], lang="fr")))
                out.add((ev, URIRef(cfg.date_predicate), Literal(d["date"], datatype=XSD.date)))
                out.add((ev, PROV.wasDerivedFrom, URIRef(d["mail_uri"])))
            else:
                continue
            done += 1
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        out.serialize(self.out_path, format="turtle")
        return done
